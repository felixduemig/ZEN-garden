# Aufbau & Interpretation von `capacity_addition_analysis.csv`

Diese Datei beschreibt **Spalten, Kennzahlen und Fallunterscheidungen** der
RC-Analyse-Ausgabe `capacity_addition_analysis.csv`, erzeugt von
[`save_capacity_addition_analysis()`](../zen_garden/postprocess/postprocess.py) in
`zen_garden/postprocess/postprocess.py`.

Das **Warum** der Reduced Costs steht in
[`rc_reduced_cost_methodology.md`](rc_reduced_cost_methodology.md), die
RHS-Perturbation in [`rc_lifetime_rhs_perturbation.md`](rc_lifetime_rhs_perturbation.md),
die Degeneriertheits-Probleme in [`rc_analysis_known_issues.md`](rc_analysis_known_issues.md).

> Alle Beispiele unten stammen aus einem realen Crystal-Ball-Lauf (1-Jahres-Snapshot,
> $\delta = 10^{-3}$ GW).

---

## 1. Spalten

| Spalte | Bedeutung |
|---|---|
| `set_technologies`, `set_capacity_types`, `set_location`, `set_time_steps_yearly` | Index (Technologie, Kapazitätstyp, Knoten, Jahr) |
| `unit` | Basiseinheit der Kapazität (z. B. `gigawatt`) |
| `value` | **Zubau** dieses Jahres = `capacity_addition` [GW] |
| `capacity` | **installierte Gesamtkapazität** = `existing + Zubau (+ Phantom δ)` [GW] |
| `capacity_ceiling` | **bindende Obergrenze** = `min(capacity.upper, capacity_limit)` [GW]; `inf` = unbeschränkt |
| `vbasis` | Gurobi-Basisstatus (0 = basisch, −1/−2 = nicht-basisch). **Kein** Wirtschaftlichkeitssignal — nur Buchhaltung. |
| `rc_capex_equivalent` | dual-basierter RC [Modelleinheiten] |
| `rc_capex_equivalent_input_units` | **Primärergebnis**: dual-basierter RC [€/kW] = „um wie viel muss CAPEX sinken, damit die Technologie gebaut wird" |

### `capacity.upper` vs. `capacity_limit` (woraus `capacity_ceiling` besteht)
- **`capacity_limit`** — Input-Parameter (Default `inf`), als **Constraint**
  `capacity ≤ capacity_limit` für *jede* Technologie durchgesetzt
  ([technology.py:1242](../zen_garden/model/technology/technology.py)).
- **`capacity.upper`** — obere Schranke der `capacity`-**Variable**, nur bei
  **On/Off-Techs** endlich: `min(capacity_addition_max + existing, capacity_limit + existing)`
  ([capacity_bounds(), technology.py:759](../zen_garden/model/technology/technology.py));
  sonst `inf`.
- Keine allein ist die wahre Decke → `capacity_ceiling = min(beide)`.

---

## 2. Kennzahlen-Beziehungen (zum Selbst-Prüfen)

$$\text{capacity} \;=\; \underbrace{\text{value}}_{\text{Zubau}} \;+\; \underbrace{\text{existing}}_{\text{Bestand}} \;+\; \underbrace{\delta_{\text{applied}}}_{\text{Phantom (nur Greenfield)}}$$

Daraus zwei nützliche Größen:

| Ausdruck | verrät |
|---|---|
| `capacity − value` | effektive Lifetime-RHS = `existing + δ_applied` |
| `capacity ≤ capacity_ceiling` | **muss immer gelten** (sonst wäre etwas infeasible) |

`capacity − value` trennt die Welt sauber:

| `capacity − value` | Bedeutung |
|---|---|
| `≈ δ` (0.001) | **Greenfield, perturbiert** (existing = 0, Phantom gesetzt) |
| `≈ 0` | **Greenfield, übersprungen** (kein Platz, ceiling < δ) |
| `> δ` (= existing) | **Brownfield** (Bestand vorhanden; wird nie perturbiert) |

---

## 3. Die Fälle (mit echten Beispielen)

| # | `value` | `capacity` | `capacity_ceiling` | `rc` | Fall | Beispiel |
|---|---|---|---|---|---|---|
| 1 | > 0 | > 0 | ≥ capacity | ≈ 0 | **gebaut** — lohnt sich, RC erwartungsgemäß 0 | `BEV, AT`: value 13.90, cap 13.90 |
| 2 | 0 | **≈ δ** | ≥ δ | **> 0** | **Greenfield, ungebaut, perturbiert** → ehrlicher Abstand | `BF_BOF, AT`: cap 0.001, rc **1707** |
| 3 | 0 | = existing > 0 | > capacity | > 0 | **Brownfield mit Platz** → ehrlicher Abstand | `district_heating_grid, DK`: cap 2.51, ceiling 11.6, rc 483 |
| 4 | 0 | **= ceiling** | = capacity | 0 (o. >0) | **Brownfield am Limit** — Ausbau unmöglich | `reservoir_hydro, SK`: cap 0.8044 = ceiling, rc **0** |
| 5 | 0 | ≈ 0 | **< δ (z. B. 0)** | beliebig | **nicht baubar** (verboten/On-Off-Block) | `reservoir_hydro, NL`: ceiling 0, cap 0 |

Häufigkeiten im Beispiel-Lauf (2952 Zeilen): 952 gebaut · 1675 Greenfield-perturbiert ·
123 Brownfield-mit-Platz · 92 Brownfield-am-Limit · 110 nicht-baubar.

---

## 4. Sonderfall **`value = 0` UND `rc ≈ 0`** — drei verschiedene Ursachen

Das ist der **interpretationskritische** Fall. Eine 0 im RC heißt **nicht** automatisch
„steht knapp vor dem Bau". Anhand von `capacity` und `capacity_ceiling` unterscheidbar:

| Diagnose | Erkennungsmerkmal | Bedeutung | RC verwertbar? |
|---|---|---|---|
| **a) Ceiling erreicht** | `capacity ≈ capacity_ceiling` (und `> δ`) | Bestand schon am Limit → **kein Zubau möglich**, egal wie billig | RC = 0 ist **legitim** („kein Hebel"), aber *kein* Break-even |
| **b) Nicht baubar** | `capacity ≈ 0` **und** `capacity_ceiling < δ` (meist 0) | Technologie am Knoten **verboten**/blockiert | RC bedeutungslos (auch ein ≠0-Wert) — **ignorieren** |
| **c) Echtes Break-even / Rest-Degeneriertheit** | `capacity ≈ δ` (perturbiert) **aber** `rc ≈ 0` | Entweder *exakt* an der Schwelle, oder eine Dual-Nicht-Eindeutigkeit, die die Perturbation nicht aufgelöst hat | **RC nicht verlässlich** → wahre Schwelle per CAPEX-Bisektion/Jitter messen ([Known Issues §3](rc_analysis_known_issues.md)) |

Im Beispiel-Lauf verteilen sich die `value=0 ∧ rc≈0`-Zeilen auf: **35 (a) ceiling erreicht**,
**10 (b) nicht baubar**, **111 (c) echtes Break-even / Rest**.

> **Genau dein Punkt:** Fall **(a)** — `reservoir_hydro, SK` mit
> `capacity = capacity_ceiling = 0.8044` — meldet `rc = 0`, **weil kein Zubau möglich
> ist** (die Bestands-Wasserkraft ist bereits am `capacity_limit`), nicht weil sie
> marginal rentabel wäre.

**Erkennungs-Flag** für die unsicheren Fälle (c):
```
rc_unreliable = (|value| < 1e-9) ∧ (|rc_capex_equivalent| < 1e-6) ∧ NICHT (capacity ≈ ceiling) ∧ NICHT (ceiling < δ)
```

---

## 5. Marginale Effekte des Perturbations-Terms (das δ)

Die RHS-Perturbation ([Doku](rc_lifetime_rhs_perturbation.md)) addiert ein winziges
$\delta$ (hier $10^{-3}$ GW) als „Phantom-Bestandskapazität" auf **Greenfield**-Einträge.
Das hinterlässt **sichtbare, aber harmlose** Spuren:

- **`capacity` trägt das δ, `value` nicht.** Für *jede* perturbierte Greenfield-Zeile
  (gebaut **wie** ungebaut) gilt `capacity = value + δ`:
  - ungebaut: `value = 0`, `capacity = 0.001` (reines Phantom).
  - gebaut: z. B. `BEV, AT` `value = 13.902`, `capacity = 13.903`.
  → Willst du die „physische" Kapazität, nutze `value` (Zubau) bzw. ziehe δ von
  `capacity` ab. Der **Zubau (`value`) ist unverzerrt**.
- **`rc` ist um $O(\delta)$ verschoben.** Das Phantom verändert den marginalen Wert
  minimal, daher weicht der RC um < 1 % vom $\delta\!\to\!0$-Ideal ab (Beispiel:
  PV DK 78,4 vs. Referenz 77,7). Für die ökonomische Aussage irrelevant.
- **`capacity_ceiling` ist δ-unabhängig** (Schranke/Limit, nicht Lösung).
- **Brownfield-Zeilen sind δ-frei** (werden nicht perturbiert) → dort ist
  `capacity = value + existing` exakt.

Faustregel: δ macht sich nur in der 4. Nachkommastelle von `capacity`/`rc` bemerkbar;
es ist ein numerischer Tie-Break, **keine** Modelländerung.

---

## 6. Schnell-Interpretation (Entscheidungsbaum)

```
value > 0 ?
├─ ja  → gebaut, rc ≈ 0                                        (Fall 1)
└─ nein (value = 0):
   capacity ≈ ceiling  und  capacity > δ ?
   ├─ ja  → Brownfield am Limit: kein Ausbau möglich           (Fall 4 / §4a)
   └─ nein:
      capacity ≈ 0  und  ceiling < δ ?
      ├─ ja  → nicht baubar: RC ignorieren                     (Fall 5 / §4b)
      └─ nein (capacity hat Platz / Phantom):
         rc > 0 ?
         ├─ ja  → ehrlicher Abstand zum Bau  [€/kW]            (Fall 2/3)  ✅
         └─ nein (rc ≈ 0) → Break-even/Rest-Degeneriertheit:
                            RC NICHT verlässlich, nachmessen    (§4c)
```

---

## 7. Vertrauens-Checkliste

1. Gebaute Techs (`value > 0`) → `rc_capex_equivalent ≈ 0`.
2. `capacity ≤ capacity_ceiling` in **jeder** Zeile (sonst Feasibility-Problem).
3. Perturbierte Greenfield-Zeilen erkennbar an `capacity − value ≈ δ`.
4. Eine **0 im RC** immer mit `capacity`/`capacity_ceiling` gegenchecken (§4) —
   ceiling-reached und nicht-baubar sind *erwartete* Nullen, nur Fall (c) ist unsicher.
5. δ um eine Größenordnung variieren → `rc`-Werte bleiben stabil (Beleg für
   strukturelle Selektion, nicht Tie-Break).

---

> **Hinweis:** Vereinzelt treten **negative** `rc_capex_equivalent` auf (z. B. blockierte,
> aber rechnerisch profitable Technologien). Das ist ein **separates** Thema und wird an
> anderer Stelle behandelt — in dieser Doku bewusst ausgeklammert.
