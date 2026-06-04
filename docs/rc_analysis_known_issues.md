# Known Issues der RC-Analyse (Reduced-Cost-Analyse)

Kontext: greenfield-Snapshot des Crystal-Ball-Modells (`optimized_years=1`,
`reference_year=2050`, 28 Knoten, ~70 Conversion-Technologien), gelöst mit
linopy + Gurobi. Ziel der RC-Analyse: pro Technologie/Knoten bestimmen, um
wie viel die CAPEX sinken muss, damit die Technologie optimal wird
(`rc_capex_equivalent_input_units` in €/kW).

Dieses Dokument hält die drei strukturellen Probleme fest, die bei der
Interpretation der Outputs auftreten — mit Begründung, Herleitung, Beispiel
und Behebungsansätzen.

**Kernunterscheidung vorab:** Problem 1 und Problem 3 sind *zwei verschiedene
Arten von Degeneriertheit*:

- **Problem 1 = primale Degeneriertheit** — die *Primal-Variablen* sind
  degeneriert, die *Duale* bleiben aber verlässlich. Macht nur den **nativen
  Gurobi-RC** kaputt; das eigene dual-basierte Skript rettet es. → **gelöst**.
- **Problem 3 = duale Degeneriertheit** — die *Duale selbst* sind nicht
  eindeutig. Trifft sogar das eigene Skript. → **offen**, braucht
  Symmetriebrechung/Perturbation.

Problem 2 (Presolve) ist die Randbedingung, die das eigene Skript überhaupt
erst ermöglicht — und verschärft als Nebenwirkung 1 und 3.

---

## Problem 1 — Primale Degeneriertheit durch die Kapazitäts-Übersetzungs-Gleichung

### Symptom
Der native Gurobi-`reduced_cost`-Output von `capacity_addition` ist an fast
allen relevanten Knoten **0** — auch dort, wo die Technologie klar unrentabel
ist. Als Wirtschaftlichkeitsmaß unbrauchbar.

### Ursache / Herleitung
`constraint_technology_lifetime` koppelt Kapazität und Zubau als **Gleichung**
(`zen_garden/model/technology/technology.py:1536`, `lhs == rhs`):

```
capacity[n,y] − Σ capacity_addition[n, ỹ ∈ Lebensdauer] = capacity_existing
                                                          (greenfield: = 0)
```

LP-Grundregeln:

1. Eine Basis hat exakt `m` basische Variablen (`m` = Anzahl Constraint-Zeilen);
   die Basismatrix muss invertierbar sein.
2. Jede Gleichungs-Zeile muss aufgespannt sein → **mindestens eine** ihrer
   Variablen muss basisch sein (sonst Null-Zeile → singulär → ungültig).
3. **Basische Variable ⇒ reduced cost = 0**, immer und per Definition.

Es gibt eine solche Gleichung **pro (Technologie, Knoten, Jahr)** — tausende.
Jede zwingt eine ihrer Variablen in die Basis. Der Crossover greift meist
`capacity_addition`; ist nichts gebaut, ist sie eine **degenerierte
Basisvariable bei Wert 0** → reduced cost 0.

### Beispiel
Aus `outputs_20260603-151742`: global **2789 `capacity_addition` basisch
(`vbasis=0`), nur 163 nonbasic (`vbasis=-1`)**. Alle 28 PV-Knoten — gebaut (DE)
wie ungebaut (DK) — stehen auf `vbasis=0`, daher `reduced_cost=0` überall,
obwohl DK rechnerisch 77.69 €/kW vom Bau entfernt ist.

### Auswirkung
Nativer RC nutzlos. **Aber:** der Dual der Lifetime-Gleichung bleibt
verlässlich, weil die *wirtschaftliche* Information dort steckt (nicht im
Basis-Status). Daraus lässt sich der RC korrekt rekonstruieren:

```
rc_capex_equivalent = capex_specific − (Σ −dual_lifetime) / (annuity × Σ discount_factors)
```

### Behebung — ✅ gelöst
Eigenes Skript `_compute_rc_capex_equivalent` in
`zen_garden/postprocess/postprocess.py` berechnet den dual-basierten RC statt
des nativen Gurobi-RC. Voraussetzungen: `Crossover=1` (für exakte Duale) und
`Presolve=0` (siehe Problem 2).

### Wichtig
`vbasis` auf `capacity_addition` ist nur ein **Buchhaltungs-Tie-Break** (welche
Seite der Gleichung der Crossover in die Basis steckt), **kein**
Wirtschaftlichkeitssignal — es kann Problem 3 nicht isolieren. Bei PV steht es
deshalb fast überall auf 0.

---

## Problem 2 — Presolve zerstört die für die RC-Analyse nötigen Duale

### Symptom
Mit aktivem Presolve sind die Duale von `constraint_technology_lifetime` (und
der Diffusions-Constraints) nicht mehr sinnvoll auslesbar → die
RC-Rekonstruktion bricht. Deshalb läuft das Modell mit **`Presolve = 0`**
(bestätigt in `solver.log`).

### Ursache / Herleitung
Presolve transformiert das Modell vor dem Solve:

- **Substitution von Gleichungs-Variablen:** Genau die Kopplung aus Problem 1
  (`capacity = Σ capacity_addition + existing`) ist ein idealer
  Presolve-Kandidat — `capacity` wird wegsubstituiert.
- **Zeilen-/Spalten-Aggregation & Eliminierung** redundanter/leerer Constraints.

Folge: Die Constraint, deren Dual wir brauchen, existiert im presolvten Modell
evtl. gar nicht mehr oder ist mit anderen verschmolzen. linopy liest Duale
**per Constraint-Label** zurück — für wegoptimierte Zeilen gibt es keinen (oder
einen verzerrten) Dual → `dual_lifetime` wird NaN/falsch →
`rc_capex_equivalent` unbrauchbar.

### Beispiel / Abgrenzung
Wichtig fürs Protokoll: Beim SK-Fall (Problem 3) war Presolve **bereits aus**
(`Presolve 0` im Log). Die dortige Null war **also kein** Presolve-Artefakt —
die Hypothese „Presolve hat etwas gedroppt" wurde überprüft und **verworfen**.
Presolve ist kein Verursacher falscher Optima, sondern verhindert (wenn an)
lediglich das Auslesen korrekter Duale.

### Auswirkung
Ohne `Presolve=0` ist die gesamte dual-basierte RC-Analyse nicht durchführbar.
Kosten des Abschaltens: größeres/langsameres Modell und — weil Presolve sonst
viel Symmetrie wegräumt — **stärker exponierte Degeneriertheit** (verschärft
Problem 1 & 3, erhöht Crossover-Zeit).

### Behebung — ✅ Workaround etabliert
`Presolve=0` fix in der Solver-Config. Zusätzlich `use_scaling=0` (bzw.
Skalierungs-Rückkorrektur `D_r_inv` im Skript), damit Duale in
Originaleinheiten bleiben. Trade-off (Laufzeit, Degeneriertheit) bewusst in
Kauf genommen.

---

## Problem 3 — Echte (duale) Degeneriertheit: nicht-eindeutige Duale (SK-Fall)

### Symptom
An Knoten *genau an der Rentabilitätsgrenze* ist selbst der dual-basierte
`rc_capex_equivalent` **basisabhängig** und kann eine irreführende **0**
liefern, obwohl der Knoten nicht gebaut wird.

### Ursache / Herleitung
Mehrere Knoten haben (bei uniformer CAPEX) **denselben Break-even** → das
Optimum ist nicht eindeutig, es gibt **mehrere optimale Dual-Ecken**. Für einen
marginalen Knoten kann der Lifetime-Dual dann verschiedene Werte annehmen:

- liegt er bit-genau auf `dual = −capex × CRF`, folgt
  `rc = capex − (capex·CRF)/CRF = 0`;
- liegt er weniger negativ, folgt `rc > 0`.

Welche Ecke der Solver greift, ist Numerik-Tie-Break, **keine** Ökonomie.
(Unterschied zu Problem 1: dort sind die *Primal*-Variablen degeneriert, die
Duale aber eindeutig/gut; hier sind die *Duale selbst* nicht eindeutig.)

### Herleitung der bit-genauen Null
Mit `CRF = r(1+r)ⁿ / ((1+r)ⁿ − 1)`, PV: `r=5%`, `n=30` → `CRF=0.0650513`. Im
1-Jahres-Snapshot ist der Discount-Faktor des einzigen Jahres = 1, also
`scaling = CRF`. SK/DE/AT teilten den **bit-identischen** Dual:

```
−316.98548777525 × 0.0650513 = −20.62036088
→ rc_capex_equivalent = 0 (exakt)
```

### Beispiel + Beweis der Degeneriertheit
- **Run A** (`outputs_20260603-125010`): SK `value=0, rc=0` (Schein-Null),
  während FI `value=0, rc=66.76` (ehrlich).
- **Perturbation** (SK CAPEX −1): `rc` springt auf **+1.15** (statt ≤0) —
  Kosten senken macht den Knoten scheinbar *unrentabler* → **nicht-monoton** →
  klassischer Wechsel zwischen degenerierten Ecken. Beweist: die 0 war kein
  echter Break-even.
- **Run B** (`outputs_20260603-151742`): jetzt ist **SK gebaut**
  (`value=0.778`) und **CZ=0** — der „auf 0 sitzende" Knoten ist **gewandert**.
  Genau der Fingerabdruck von Alternativ-Optima.

### Auswirkung
Der `rc_capex_equivalent` eines Knotens mit `value≈0 ∧ rc≈0` ist **nicht
interpretierbar**. Das eigene Skript (Problem 1) hilft hier *nicht*, weil das
Problem in den Dualen selbst sitzt. Auch `vbasis` hilft nicht (siehe Problem 1).

### Behebung / Ansätze — ⚠️ offen, kein In-Solver-Fix
1. **Erkennen:** Flag
   `rc_unreliable = (|value| < 1e-9) ∧ (|rc_capex_equivalent| < 1e-6)` — der
   einzige zuverlässige Diskriminator für den Schein-Null-Fall.
2. **Eliminieren (empfohlen):** **Symmetrie brechen** via Mini-Jitter auf die
   node-resolved CAPEX, z. B. `±0.01 €/kW` deterministisch je Knoten →
   eindeutiges Optimum → eindeutige Duale → belastbarer RC überall. Physikalisch
   irrelevant (≪ 317 €/kW), numerisch genug.
3. **Wahre Schwelle messen:** finite Perturbation/Bisektion am interessierenden
   Parameter (CAPEX schrittweise senken bis `value > 0`) — von Degeneriertheit
   unabhängig. (Bei SK ⇒ ~2 €/kW echter Abstand.)
4. **Nicht zielführend:** Basis erzwingen. Gurobi bietet keinen Lock; eine
   ε-Kosten auf `capacity_addition` würde nur `vbasis` kosmetisch ändern, nicht
   die Dual-Nicht-Eindeutigkeit beheben.

---

## Querverbindungen

- **Problem 2 verschärft 1 & 3:** Presolve aus → mehr Symmetrie sichtbar → mehr
  Degeneriertheit, höhere Crossover-Zeit (z. B. ~117 s → ~239 s bei einer
  Datenänderung beobachtet).
- **Problem 1 ≠ Problem 3:** primale vs. duale Degeneriertheit. 1 ist gelöst
  (Duale gut → Skript), 3 bleibt offen (Duale nicht eindeutig → Jitter/
  Perturbation nötig).
- **Ursprüngliche Motivation (gelöst, kein „Problem" mehr):** geteilte
  Jahr-nur-CAPEX erzeugte Cross-Talk zwischen Ländern (CZ-Perturbation
  beeinflusste alle). Behoben durch **node-resolved `capex_specific_conversion`**
  — diese liefert jetzt auch direkt das Vehikel für den Jitter aus Ansatz 3.2.

---

## Solver-Konfiguration (für reproduzierbare Duale)

| Einstellung | Wert | Grund |
|---|---|---|
| `Presolve` | `0` | Duale der Lifetime-/Diffusions-Constraints auslesbar halten (Problem 2) |
| `Crossover` | `1` | Vertex-Lösung → exakte Duale statt Barrier-Interior-Rauschen |
| `use_scaling` | `0` | Duale in Originaleinheiten (sonst `D_r_inv`-Rückkorrektur im Skript) |
| `Method` | Simplex/concurrent | exakte LP-Duale |

## Praktische Lesehilfe für `capacity_addition_analysis.csv`

- `value > 0` → gebaut, RC ≈ 0 (erwartet).
- `value = 0` **und** `rc_capex_equivalent > 0` → ehrlich unrentabel; RC =
  benötigte CAPEX-Senkung in €/kW (verlässlich).
- `value = 0` **und** `rc_capex_equivalent ≈ 0` → **Warnsignal Problem 3**: RC
  nicht interpretierbar, wahre Schwelle per Perturbation messen oder Symmetrie
  brechen.
- `vbasis` ist **kein** Wirtschaftlichkeitssignal (Problem 1) — nicht zur
  Degeneriertheits-Erkennung verwenden.
