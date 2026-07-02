# Stresstest der Reduced Costs — Showcase-Modell `6_showcase_countries`

*Durchgeführt 2026-06-21. Ziel: nachweisen, dass die berechneten Reduced Costs (RC) den tatsächlichen
Bau-Rand punktgenau treffen — d. h. brauchbare, belastbare Ergebnisse liefern.*

## Methode: ±1%-Build/Nobuild

Für jede getestete RC wird der CAPEX der Technologie gezielt verändert und das Modell **neu gelöst**
(degenerations-immune Ground Truth, keine Dual-Annahmen):

- **Build-Punkt:** CAPEX um **(1 + 1 %)·RC** senken → die Tech **muss** bauen.
- **Nobuild-Punkt:** CAPEX um **(1 − 1 %)·RC** senken → die Tech darf **nicht** bauen.
- **PASS** = Build baut (Wert > 0) **und** Nobuild baut nicht (Wert = 0).

Die Validierungsläufe sind **ohne Perturbation** (echte Bauentscheidung), volle 8760 h → 24 typische
Stunden (TSA), Solver Gurobi. RC-Quelle: der gelöste Baseline-Lauf. Override via
`rc_capex_file_override.py` (CAPEX-Datei temporär getauscht, nach dem Lauf restauriert).

Getestet werden nur sinnvoll auflösbare `buildable_rc`-Fälle (ratio = RC/CAPEX in ~0.03–0.85); zusätzlich
ein Sonderfall (Gasboiler, ratio > 1) und der Storage-Bundle.

## Ergebnisse

| # | Technologie | unterscheidet sich von … durch | Knoten | RC [€/kW] | ratio | Build | Nobuild | Ergebnis |
|---|---|---|---|---|---|---|---|---|
| 1 | photovoltaics_capex | PV: **+10 € CAPEX** | CH | 41.5 | 0.083 | 0.039 | 0 | **PASS** |
| 2 | photovoltaics_capex | PV: +10 € CAPEX | DE | 95.9 | 0.192 | 0.042 | 0 | **PASS** |
| 3 | photovoltaics_opex | PV: **2× opex_fix** | IT | 165.2 | 0.337 | 1.000 | 0 | **PASS** |
| 4 | photovoltaics_opex | PV: 2× opex_fix | DE | 251.1 | 0.512 | 1.000 | 0 | **PASS** |
| 5 | photovoltaics_lowcf | PV: **½ Kapazitätsfaktor** | IT | 327.6 | 0.669 | 1.000 | 0 | **PASS** |
| 6 | photovoltaics_lowcf | PV: ½ Kapazitätsfaktor | DE | 370.5 | 0.756 | 1.000 | 0 | **PASS** |
| 7 | natural_gas_turbine | fossiler Strom-Peaker (CO₂) | FR | 117.8 | 0.151 | 0.002 | 0 | **PASS** |
| 8 | natural_gas_turbine | fossiler Strom-Peaker | IT | 44.9 | 0.058 | 0.037 | 0 | **PASS** |
| 9 | natural_gas_boiler | ratio > 1 (verdrängt) | AT | — | >1 | **0** (bei CAPEX≈1) | — | **PASS** |
| 10 | battery (Bundle Power/Energy) | Storage | IT | 1134 | 0.788 | 14.65 | 0 | **PASS*** |

\* Battery: PASS bei **e2p-konsistenter** Prüfung (s. u.).

**Verdikt: alle RC-Typen ±1%-validiert** — CAPEX, fixe OPEX, Kapazitätsfaktor, fossile Tech und das
Storage-Bundle. Reduced Costs liefern im realistischen 5-Länder-Modell am Bau-Rand exakte Ergebnisse.

### Re-Validierung mit der OPERATIVEN RC (storage-only-Run, 2026-06-22)

Die obige Tabelle nutzte die Lifetime-Ratio. Nachdem das Klassifizierungs-Gate auf die **operative** RC
umgestellt wurde (s. `docs/rc_operational_reconstruction.md` §5c) und der kanonische Report-Run der
**storage-only-Lauf** `outputs_showcase_storage_only/` ist (Conversion/Transport ohne Perturbation, nur
Storage perturbiert), wurde der ±1%-Test komplett gegen die **operative** RC neu gefahren
(`_val_storage_only.py`): **17/17 PASS**, e2p-konsistent über alle 5 Battery-Knoten.

**Schlüsselergebnis — die drei `photovoltaics_capex`-Twins (AT/FR/IT):** dort ist die *Lifetime*-RC = 0
(degeneriert, Klon ist exakter +10 €-Zwilling von gebautem PV), die *operative* RC = **10 €/kW** (= 2 %).
Der ±1%-Test trifft exakt: bei −1.01×2 % baut der Klon (1 GW), bei −0.99×2 % nicht → **PASS**. Das ist der
direkte Beweis, dass die operative RC der korrekte Wert ist und die Lifetime-0 der Fehler war — und dass
Conversion **gar keine** Perturbation braucht. Skript: `_val_storage_only.py` →
`outputs_*_val_storage_only/val_storage_only_summary.csv`.

## Drei Befunde im Detail

**1. Die RC berücksichtigt jeden Kostenfaktor isoliert.** Die drei PV-Klone sind identisch zu PV bis
auf genau einen Faktor (alle auf 1 GW/Land gedeckelt). Die RC staffelt sich entsprechend sauber:
+10 € CAPEX → RC ~33–96; doppelte opex_fix → RC ~165–251; halber Kapazitätsfaktor → RC ~328–371. Jeweils
±1%-bestätigt. Auch die **lokale Differenzierung** ist korrekt (gleiche Tech, andere RC je Knoten, weil
PV-Wert/Erlös je Land variiert).

**2. ratio > 1 heißt beweisbar „baut nie".** Der Gasboiler wird von der COP-3-Wärmepumpe verdrängt
(Wärme ≈ 6 vs. 53 €/MWh) → RC > CAPEX. Der Check bestätigt: **selbst bei CAPEX ≈ 0 baut der Gasboiler
nichts** (Wert = 0). Die RC kennzeichnet eine nicht-lebensfähige Technologie korrekt.

**3. Storage-RC ist für eine feste Dauer (e2p) definiert — Validierung muss das spiegeln.** Die
Bundle-RC (Power + Energy proportional) wird unter fixem `energy_to_power_ratio = 4 h` berechnet. Lässt
man e2p im Validierungslauf **frei** (1–12 h), optimiert die Battery eine andere Dauer → der ±1%-Test
scheint zu „versagen" (Bau schon am Nobuild-Punkt). Fixiert man e2p im Build/Nobuild auf denselben Wert
(4 h), **bestätigt** sich die Bundle-RC sauber (Build 14.65, Nobuild 0 → PASS). Methodischer Lernpunkt:
Storage-RC und ihre Validierung müssen unter derselben Dauer-Annahme laufen.

## Storage im Detail: bedingte RC + e2p-Konsistenz (n = 5)

Storage ist der schwierigste, zuvor als „Phantom" verdächtigte Fall — er validiert hier dennoch
**exakt**, sobald das Protokoll stimmt. Der Schlüssel: eine Conversion-Tech hat *einen* CAPEX, ihre RC
ist unbedingt; die Battery hat **zwei** CAPEX (Power €/kW + Energy €/kWh) und ein Dauer-Verhältnis
**e2p**. Die Bundle-RC beantwortet daher eine *bedingte* Frage: „Um welchen %-Satz muss ich Power+Energy
proportional senken, damit die Battery baut — **bei gegebener Dauer e2p**?"

Drei Anläufe bei battery IT y0 zeigen, warum die ersten beiden scheinbar scheiterten:

| Anlauf | RC-Quelle | ratio | e2p im Validierungslauf | Ergebnis | Diagnose |
|---|---|---|---|---|---|
| 1 | **ohne** Perturbation | 0.527 | frei (1–12) | FAIL | falscher RC-Wert (Storage-RC braucht die Perturbation) → unterschätzt |
| 2 | **mit** Perturbation | 0.788 | frei (1–12) | FAIL | richtiger RC (für 4-h-Battery), aber Lauf wählt *andere, günstigere Dauer* → baut zu früh |
| 3 | **mit** Perturbation | 0.788 | **fix = 4** | **PASS** | konsistent → Break-even = 0.788 = RC |

Beide FAILs waren also **Methodik-Mismatches, kein RC-Fehler**. Mit e2p-konsistenter Prüfung bestätigt
sich die Bundle-RC über **alle fünf Länder**:

| Knoten | Bundle-RC [€/kW] | ratio | Build | Nobuild | Ergebnis |
|---|---|---|---|---|---|
| IT | 1134 | 0.788 | 14.65 | 0 | **PASS** |
| FR | 1182 | 0.821 | 21.16 | 0 | **PASS** |
| CH | 1212 | 0.841 | 3.05 | 0 | **PASS** |
| AT | 1250 | 0.868 | 10.23 | 0 | **PASS** |
| DE | 1262 | 0.876 | 9.43 | 0 | **PASS** |

**Regel für die Praxis (auch fürs Crystal-Ball-Modell):** Storage-RC immer **mit Perturbation** rechnen,
und die **Dauer (e2p) zwischen RC-Berechnung, Interpretation und Validierung konsistent** halten. Die
Storage-RC ist keine unbedingte Einzelzahl, sondern „Distanz zum Bau bei fester Dauer" — in
Heatmaps/„wie nah ist Storage" muss die Dauer mitgenannt werden.

## Zweite Validierungsebene: Solver-Robustheit (Method × Presolve)

Die RC wird aus *Duals* rekonstruiert — und Duals hängen von der Basis ab, die der Solver zurückgibt.
Da wir jetzt die **korrekten** RC-Werte kennen (±1%-validiert), können wir prüfen, welche Gurobi-Konfig
sie reproduziert. Getestet: Method {0 = Primal-Simplex, 1 = Dual-Simplex, 2 = Barrier} × Presolve {0, 1},
Crossover 1, ohne Perturbation. (`outputs_showcase_solvertest/solvertest_RC_comparison.csv`.)

Stimmen alle 8 validierten Conversion-RCs mit den korrekten Werten überein?

| | Primal P0 | Primal P1 | Dual P0 | Dual P1 | **Barrier P0** | Barrier P1 |
|---|---|---|---|---|---|---|
| **Lifetime-RC** | teilweise | ✗ (→0) | teilweise | ✗ (→0) | **✓ alle** | ✗ (→0) |
| **operativer RC** | ✓ alle | ✗ (→0) | ✓ alle | ✗ (→0) | **✓ alle** | ✓ alle |

**Drei Befunde:**
1. **Presolve = AUS ist Pflicht.** Mit Presolve AN brechen beide Rekonstruktionen bei den Simplex-Methoden
   ein (alle RCs → 0): Presolve verändert Basis/Duals und löscht die degenerierten Lifetime-Duals.
2. **Lifetime-RC braucht spezifisch Barrier + Presolve 0** (nur `M2_P0` liefert alle korrekt). Simplex
   landet auf einem anderen degenerierten Vertex → Lifetime-Dual = 0 → RC kollabiert.
3. **Der operative RC ist deutlich robuster** — korrekt für *jede* Methode (sofern Presolve aus), sogar
   bei Barrier + Presolve an (4/6 Konfigs vs. 1/6 beim Lifetime-RC).

*Hinweis:* `natural_gas_turbine` ist überall korrekt (nicht-degenerierter Dual, weil quasi-gebaut/Bestand);
die Fragilität trifft nur die ungebauten, vorbaufreien Grenztechs. Nativer RC bleibt 0 (mit Presolve an
bei 2/8 ≠ 0 — Basiswechsel).

**Fazit:** `Method 2 (Barrier) + Presolve 0` ist die belegt richtige Wahl; die operative Dual-Rekonstruktion
ist zusätzlich solver-robuster als die Lifetime-Variante.

### Was Presolve genau kaputt macht

Presolve ist eine **Vorverarbeitung** *vor* dem eigentlichen Solve: es entfernt redundante/linear abhängige
Constraints, **substituiert Variablen über Gleichungs-Constraints** (bei `x − y = 0` wird `x` überall durch
`y` ersetzt und Constraint + Variable verschwinden), aggregiert und zieht Schranken zusammen. Danach löst
Gurobi das kleinere Problem und rechnet Lösung + Duals zurück („Postsolve").

Unsere RC-Rekonstruktion liest den **Dual einer bestimmten Constraint** (Lifetime-Bilanz μ) für eine
**gleichungs-gekoppelte Variable** (`capacity_addition`) — und genau diese Kopplungen sind Presolves
Lieblingsfutter:
- `capacity_addition − capacity_approximation = 0` (capex-Coupling) → Gleichung zweier Variablen → substituiert.
- `capacity = Bestand + Σ capacity_addition` (Lifetime-Bilanz) → aggregiert.

Drei Folgen: (1) Die Constraint, deren Dual wir lesen, **existiert im reduzierten Problem nicht mehr** — ihr
Dual wird erst beim Postsolve rekonstruiert. (2) Unser LP ist hier **degeneriert** → der Dual ist **nicht
eindeutig** (eine ganze Menge optimaler Duals). (3) Presolve löst ein *strukturell anderes* Problem, landet
auf einer **anderen optimalen Basis** und der Postsolve gibt einen **anderen Vertreter** aus der Dual-Menge
zurück — typischerweise den, bei dem der **Lifetime-Dual μ auf 0 kollabiert** (der Wert ist in `c̄(S)`
umgeparkt).

**Kernaussage:** Presolve ändert nicht die *Lösung*, aber *welchen* der vielen gültigen Duals man
zurückbekommt — und die RC braucht einen bestimmten. In einem nicht-degenerierten Problem wäre das egal
(eindeutiger Dual); bei den gekoppelten Bau-Variablen ist es fatal. Deshalb **Presolve 0** (Original-Constraints
bleiben stehen) und **`use_scaling 0`** (Skalierung transformiert sonst die Dual-*Werte* zeilen-/spaltenweise).
Der operative RC überlebt Barrier+Presolve, weil er an den robuster verankerten Carrier-Preisen λ hängt;
Simplex+Presolve verschiebt zusätzlich diese Preis-Duals → dann kippt auch er.

## Nicht getestet (und warum)
- **heat_pump, photovoltaics, wind, nuclear (real)**: entweder gebaut (RC ≈ 0, nichts zu testen) oder
  am Limit / verboten / mit Vorbau (Carry-over) → kein sauberer Greenfield-Bau-Rand für einen ±1%-Test.
- Die *sauber* testbaren Fälle sind die vorbau-freien Grenztechs (PV-Klone, gas_turbine, battery) — und
  genau die wurden geprüft.

## Reproduktion
- Haupt-Stresstest (8 Conversion + Gasboiler-gratis): `_val_showcase.py` → `outputs_*_val_showcase/val_showcase_summary.csv`
- Storage e2p-konsistent, alle 5 Knoten: `_val_battery_multi.py` → `outputs_*_val_batt_multi/val_batt_multi_summary.csv`
  (`_val_battery.py` / `_val_battery2.py` = die diagnostischen Anläufe 2 und 3)
- Datensatz/Modell: siehe `docs/showcase_model.md`.
