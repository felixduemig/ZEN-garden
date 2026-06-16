# RC-Analyse: Lifetime-RHS-Perturbation — Implementierung

Diese Datei dokumentiert die **RHS-Perturbation der Lifetime-Constraint**, mit der
die Reduced-Cost-Analyse die *Schein-Nullen* an ungebauten Technologien beseitigt.
Sie ist das **Wie** (Implementierung); das **Warum** (LP-Theorie) steht in
[`rc_reduced_cost_methodology.md` §C](rc_reduced_cost_methodology.md) und die
zugrunde liegende Degeneriertheit in
[`rc_analysis_known_issues.md` §Problem 3](rc_analysis_known_issues.md).

---

## 1. Das Problem in einem Absatz

Für jede **ungebaute** Technologie wollen wir `rc_capex_equivalent` = „um wie viele
€/kW müssten die Investitionskosten sinken, damit sie gebaut wird". Wir lesen das aus
dem **Dual der Lifetime-Constraint** ([technology.py:1536](../zen_garden/model/technology/technology.py)):

$$S_{h,p,y} \;-\; \sum_{\tilde y}\Delta S_{h,p,\tilde y} \;=\; \text{capacity\_existing}.$$

An einer **greenfield-ungebauten** Technologie sind $S=0$ **und** $\Delta S=0$, die
Gleichung wird zu $0=0$ (degeneriert), und ihr Dual $\lambda^{\text{lt}}$ ist **nicht
eindeutig** — es darf in einem ganzen Intervall $[-K,\,-V]$ liegen ($K$ = annualisierte
Capex, $V$ = marginaler Wert der Kapazität). Die beiden Endpunkte bedeuten das
Gegenteil:

| $\lambda^{\text{lt}}$ | `rc_capex_equivalent` |
|---|---|
| $-V$ (Wert-Endpunkt) | $\alpha - V/\sigma > 0$ ✅ ehrlicher Abstand |
| $-K$ (Capex-Endpunkt) | $0$ ❌ Schein-Null |

Ohne Hilfe greift der Solver einen beliebigen Endpunkt → dieselbe unwirtschaftliche
Technologie meldet mal den echten Abstand, mal eine irreführende 0.

---

## 2. Die Idee: RHS-Störung statt Objective-Störung

Im **dualen** Maximierungsproblem $\max\,b^\top y$ ist der Beitrag der
Lifetime-Constraint

$$\underbrace{b}_{\text{RHS}=\text{capacity\_existing}=0}\cdot\;\lambda^{\text{lt}} \;=\; 0\cdot\lambda^{\text{lt}}.$$

Das Dual-Ziel ist also **flach in $\lambda^{\text{lt}}$** → keine Auswahl. Eine
Störung des **Objectives** (`rc_perturbation`) verschiebt nur das *zulässige Intervall*
und lässt das Dual-Ziel flach — sie kann den Endpunkt **nicht** wählen.

Stattdessen stören wir die **RHS** um ein kleines $\delta>0$ (ein „Phantom" an
Bestandskapazität). Der Dual-Zielterm wird

$$\delta\cdot\lambda^{\text{lt}},\qquad \delta>0,$$

und sein Maximum über das (unveränderte) Intervall $[-K,-V]$ liegt bei
$\lambda^{\text{lt}}=-V$ — dem **ökonomisch korrekten Wert-Endpunkt**. Das Dual-Optimum
ist damit eindeutig; `rc_capex_equivalent` zeigt den echten Abstand.

> **Vorzeichen ist kritisch:** $\delta>0$ wählt $-V$ (korrekt), $\delta<0$ wählt $-K$
> (Schein-Null). Als Grenzwert $\delta\to0$ bleibt das Primaloptimum unverändert
> (`capacity_addition` bleibt 0; nur `capacity` nimmt das Phantom $\delta$ auf).

Faustregel: **RHS-Störung wählt unter Dualen** (= bricht primale Degeneriertheit) —
genau unser Fall. Objective-Störung wählt unter Primalen.

---

## 3. Der entscheidende Guard: nur Greenfield, nur mit Headroom

Naiv „$\delta$ auf jede Lifetime-RHS" macht das Modell **infeasible**. Zwei
Bedingungen müssen erfüllt sein (beide am Code verifiziert, eine via IIS):

### 3a. Nur Greenfield ($\text{existing}=0$)
Die $0=0$-Degeneriertheit existiert **nur** bei $\text{existing}=0$. Brownfield-
Technologien ($\text{existing}>0$) haben $S>0$ → ihr Lifetime-Dual ist **schon
eindeutig**; sie brauchen die Störung nicht und **vertragen sie nicht**.

> **Lektion aus der IIS.** `reservoir_hydro` an SK ist Brownfield mit
> $\text{existing} = \text{capacity\_limit} = 0.8044$ (voll ausgebaute Wasserkraft).
> $\delta$ auf die RHS verlangte $S = 0.8044 + \delta$, aber
> $S \le \text{capacity\_limit} = 0.8044$ → infeasible um exakt $\delta$. Der
> Greenfield-Guard ($\text{existing}=0$) überspringt solche Einträge.

### 3b. Genug Headroom ($\min(\text{capacity.upper},\,\text{capacity\_limit})\ge\delta$)
Auch unter den Greenfield-Einträgen gibt es welche, die $\delta$ nicht aufnehmen können:
- `capacity_limit < δ` (sehr kleines Limit), oder
- On/Off-Technologien mit `capacity_addition_max = 0`, deren **Variablen-Obergrenze**
  laut [`capacity_bounds()`](../zen_garden/model/technology/technology.py) (technology.py:759-768)
  $\min(\text{addition\_max}+\text{existing},\,\text{capacity\_limit}+\text{existing})=0$
  ist — **obwohl `capacity_limit = inf`**.

Deshalb prüft der Guard die **echte Headroom** $\min(\text{capacity.upper},
\text{capacity\_limit})$, nicht nur `capacity_limit`.

Zusammengefasst — perturbiert wird, wo:

$$\big(|\text{RHS}| < 10^{-9}\big)\;\wedge\;\big(\min(\text{capacity.upper},\,\text{capacity\_limit})\ge\delta\big).$$

---

## 4. Implementierung

| Ort | Inhalt |
|---|---|
| [`main_rc_simplex.py:77`](../main_rc_simplex.py) | Knopf `config["solver"]["solver_options"]["rc_lifetime_rhs_perturbation"] = 1e-3` |
| [`optimization_setup.py:695`](../zen_garden/optimization_setup.py) | Methode `perturb_lifetime_rhs_for_rc()` |
| [`runner.py`](../zen_garden/runner.py) | Aufruf im Horizont-Loop, **nach** `perturb_objective_for_rc()`, **vor** Scaling/Solve |

Kern der Methode (gekürzt):

```python
delta = self.solver.solver_options.pop("rc_lifetime_rhs_perturbation", None)
if not delta:
    return
con = self.model.constraints["constraint_technology_lifetime"]
rhs_da = con.rhs
cap_upper = xr.align(rhs_da, self.model.variables["capacity"].upper, join="left")[1].fillna(np.inf)
cap_limit = xr.align(rhs_da, self.parameters.capacity_limit,        join="left")[1].fillna(np.inf)
ceiling   = np.minimum(cap_upper, cap_limit)
is_greenfield = np.abs(rhs_da) < 1e-9
add = xr.where(is_greenfield & (ceiling >= delta), float(delta), 0.0)
con.rhs.data = rhs_da.data + add.broadcast_like(rhs_da).transpose(*rhs_da.dims).data
```

Designentscheidungen:
- **Post-Build, nicht zur Bauzeit:** Die Störung wird nach dem Modellaufbau direkt auf
  `con.rhs` addiert (Schreib-API wie im Scaling, [unit_handling.py:1442](../zen_garden/preprocess/unit_handling.py)).
  Vorteil: Die `capacity_limit`-Klassifikation und die Diffusions-Basis (die den
  `capacity_existing`-*Parameter* nutzen) bleiben **unberührt** — nur der Dual der
  Lifetime-Constraint wird beeinflusst.
- **Key wird gepoppt:** `rc_lifetime_rhs_perturbation` ist keine Gurobi-Option; sie wird
  abgefangen und entfernt, bevor `solver_options` an Gurobi geht.
- **Sicherer Fallback:** Scheitert das Alignment, wird **gar nicht** perturbiert
  (Frühausstieg mit `logging.error`) — niemals „alles perturbieren" (das hatte
  Infeasibility riskiert).
- **`use_scaling=0`:** Die Störung wird vor `run_scaling()` addiert; mit
  `use_scaling=0` wirkt $\delta$ in rohen Einheiten (GW) und ist direkt interpretierbar.

Log-Zeile zur Kontrolle:
```
RC perturbation: added +0.001 to RHS of constraint_technology_lifetime (N/M entries perturbed; K skipped for head-room < delta)
```

---

## 5. Empirische Validierung (Crystal_Ball, 1-Jahres-Snapshot)

Vergleich gegen die beiden Baselines (alle 2952 Zeilen, `value≈0` = ungebaut):

| Lauf | `value≈0` | **rc>0 (ehrlich)** | **rc≈0 (Schein/Break-even)** | rc<0 |
|---|---|---|---|---|
| **RHS-Perturbation (diese Implementierung)** | 2000 | **1735** | **156** | 109 |
| SIMPLEX-Baseline (Objective-Pert.) | 2066 | 1283 | 675 | 108 |
| Barrier-Baseline | 2066 | 1586 | 371 | 109 |

- **Schein-Nullen drastisch reduziert** (675/371 → **156**), ehrliche Positive erhöht
  (1283/1586 → **1735**).
- **Cross-Checks gegen bekannte Werte:** ungebautes **PV DK = 78,4 €/kW**
  (Known Issues dokumentierte 77,69), **PV IE = 23,9** (SIMPLEX-Baseline 23,98).
- **Wirkt über den Dual, nicht über `vbasis`:** Die meisten gefixten PV-Knoten haben
  weiterhin `vbasis=0`, aber korrekten positiven RC — genau wie die Theorie vorhersagt
  (der RHS-Tilt pinnt $\lambda^{\text{lt}}$, unabhängig vom Basis-Status).
- **Negative RC sind vorbestehend** (109 ≈ 108 ≈ 109 in *allen* Läufen) → **nicht**
  von dieser Implementierung verursacht. Sie sind ein separates Phänomen
  („profitabel, aber durch eine andere Constraint blockiert", typisch Diffusionslimit).

---

## 6. Bedienung & Caveats

- **Aktivieren / Größe:** `rc_lifetime_rhs_perturbation = δ` in
  [`main_rc_simplex.py`](../main_rc_simplex.py). Wähle $\delta$
  **über** der Feasibility-Toleranz ($\gg 10^{-6}$) und **klein** ($10^{-4}\dots10^{-3}$
  GW). Default `1e-3` ergibt < 1 % Abweichung von den bekannten Referenzwerten.
- **Deaktivieren:** `0` oder `None`.
- **Vorzeichen:** immer positiv ($\delta>0$).
- **`value`-Spalte bleibt sauber:** Das Phantom sitzt in `capacity`/RHS, nicht in
  `capacity_addition` → `value` bleibt für ungebaute Techs 0 (kein Abziehen nötig).
- **Nicht abgedeckt:** Die ~109 negativen RC (blockierte-aber-profitable Technologien)
  und genuine Break-even-Mehrdeutigkeit zwischen *symmetrischen* Knoten. Letztere
  braucht zusätzlich einen **node-resolved CAPEX-Jitter**
  ([Known Issues §Problem 3](rc_analysis_known_issues.md)).

---

## 7. Checkliste „RC vertrauenswürdig?"

1. Im Log steht `RC perturbation: added +δ … (N/M perturbed; K skipped)` mit **N groß**.
   (N=0 ⇒ Alignment-Problem.)
2. Lauf ist **feasible** (kein „Crossover changed status to Infeasible").
3. Gebaute Techs (`value>0`) → `rc_capex_equivalent ≈ 0`.
4. Ungebaute Techs → überwiegend **positiver** RC; eine **0** bei `value=0` ist ein
   Warnsignal (Break-even/Rest-Degeneriertheit, vgl. Flag
   `rc_unreliable = (|value|<1e-9) ∧ (|rc_capex_equivalent|<1e-6)`).
5. Optional: $\delta$ um eine Größenordnung variieren — die RC sollten **stabil**
   bleiben (Beweis für strukturelle, nicht Tie-Break-getriebene Selektion).

---

*Verwandte Dokumente:* [`rc_reduced_cost_methodology.md`](rc_reduced_cost_methodology.md)
(Herleitung der RC-Formel, §C zur Perturbations-Theorie) ·
[`rc_analysis_known_issues.md`](rc_analysis_known_issues.md) (die drei Degeneriertheits-Probleme).
