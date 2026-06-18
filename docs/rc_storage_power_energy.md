# RC-Analyse bei Storage: Power-/Energy-Komponenten, Interpretation und Fix

Diese Datei erklärt, **warum die `rc_capex_equivalent`-Werte für Speicher-Technologien
gesondert behandelt werden müssen**, wie der implementierte Fix funktioniert, wie man die
Werte korrekt liest und wie man die Korrektheit testet.

Speicher bestehen aus *zwei* getrennt investierten Kapazitäten (Power und Energy), die nur
über den Betrieb gekoppelt sind. An *ungebauten* Speichern verliert der per-Komponente
berechnete Reduced Cost seine Aussagekraft — der Fix stellt sie über eine einseitige
Perturbation + die Energy-to-Power-Ratio-Constraint wieder her.

Hintergrund: Methodik [`rc_reduced_cost_methodology.md`](rc_reduced_cost_methodology.md),
Perturbation [`rc_lifetime_rhs_perturbation.md`](rc_lifetime_rhs_perturbation.md), Fälle
allgemein [`capacity_addition_analysis.md`](capacity_addition_analysis.md).

> Zahlen aus drei Crystal-Ball-Läufen (Single-Step, ein Jahr):
> `outputs_20260616-160044` (delta-Perturbation), `outputs_20260617-104826` (ohne),
> `outputs_20260617-131548` (neue Storage-Perturbation). delta = yotta = 1e-4 GW.

---

## 1. Aufbau: zwei Kapazitäten pro Speicher

Jede Storage-Technologie hat pro `(tech, node, year)` **zwei** Zeilen in
`capacity_addition_analysis.csv`:

| `set_capacity_types` | physisch | Einheit | CAPEX-Parameter |
|---|---|---|---|
| `power`  | Lade-/Entladeleistung (Turbine, Wechselrichter, Pumpe) | GW  | `capex_specific_storage` [€/kW]  |
| `energy` | Speichervolumen (Reservoir, Zellen, Kaverne)           | GWh | `capex_specific_storage_energy` [€/kWh] |

Beide sind **eigenständige Entscheidungsvariablen** (`capacity_addition`) mit eigenem CAPEX
und eigener Lifetime-Constraint.

### Die Kopplung ist rein operativ, nicht strukturell

Der Constraint `constraint_capacity_energy_to_power_ratio`
([storage_technology.py:601](../zen_garden/model/technology/storage_technology.py)) *könnte*
ein Verhältnis erzwingen:

```
ratio_min  <=  capacity_energy / capacity_power  <=  ratio_max     [h = Dauer]
```

Standardmäßig gilt `ratio_min = 0`, `ratio_max = inf` → der Constraint bindet **nie** → kein
Dual verknüpft die Komponenten. Die einzige Verbindung ist der Betrieb (State-of-Charge:
gespeicherte Menge ≤ `energy`, Lade-/Entladefluss ≤ `power`). Der ökonomische Wert einer
Komponente steckt damit **vollständig im Lifetime-Dual** und entsteht **nur aus dem
Betrieb**. Wichtig: dieser Constraint liest **`capacity_addition`**, nicht die Gesamt-
`capacity` (relevant für den Fix, §6).

---

## 2. Das Problem: RC an ungebauten Speichern ist nicht repräsentativ

Der Reduced Cost wird gebildet als
([postprocess.py:486](../zen_garden/postprocess/postprocess.py)):

```
rc_capex_equivalent = alpha - (elec_value - diff) / sigma

  elec_value = Summe_y ( -lambda_lifetime[y] )   <- Betriebsnutzen der Kapazitaet
  alpha      = annualisierter Eigen-CAPEX der Komponente
  sigma      = annuity_factor * Summe Diskontfaktoren
```

| Zustand | `elec_value` | `rc_capex_equivalent` | brauchbar? |
|---|---|---|---|
| **betrieben** (both_built) | groß (Lifetime-Dual stark negativ) | **≈ 0** | ja |
| **nicht betrieben** (eine/beide Komp. 0) | ≈ 0 (kein Betrieb) | **≈ alpha** | nein |

**Kernaussage:** An einem ungebauten Speicher trägt der RC **kein lokales Betriebssignal**.
Er fällt auf den annualisierten Eigen-CAPEX `alpha` zurück — die Kosten einer Einheit, für
die das Modell keinen Nutzen sieht. Kein knotenspezifischer „Abstand zum Bau".

Beleg (`rc_components.csv`, alter delta-Lauf), `battery, power`, `alpha = 76.59`:

| Knoten | Zustand   | Lifetime-Beitrag | `rc` = alpha + Beitrag |
|---|---|---|---|
| DE | gebaut    | **-76.59** (hebt alpha auf) | **0** |
| CH | both_zero | **+6.83** (kein Betrieb)    | **83.42** |

`83.42` war an **allen 16** both_zero-Knoten identisch — eine knotenunabhängige Konstante
ist das verräterische Zeichen.

### Warum ein Einzel-Komponenten-RC die Frage prinzipiell nicht beantworten kann

Reduced Costs linearisieren am Punkt `(power, energy) = (0, 0)`. Der Speicher-Bau ist aber
eine **nicht-lokale, gebündelte** Entscheidung: rentabel wird er erst, wenn man
`capex_power + Dauer · capex_energy` *gemeinsam* senkt. Am Punkt (0,0) ist der Grenznutzen
des Bündels null (ein δ-kleines Reservoir stiftet keinen Wert für mehr Turbine und
umgekehrt), also liefert jede Komponente isoliert nur ihren Eigen-CAPEX. Eine korrekte
Speicher-Distanz ist deshalb zwingend eine **gemeinsame** Kennzahl.

---

## 3. Konstellationen (nach Gesamtkapazität, nicht nach Zubau)

`real` = `capacity > 1.5·delta`. **funktional** = Power real UND Energy real; **leer** =
beide ≈ 0; **nur_Energy/nur_Power** = nur eine Seite real.

| Tech | funktional | leer | nur_Energy | nur_Power |
|---|---|---|---|---|
| battery | 10 | 16 | 2 | 0 |
| natural_gas_storage | 18 | 10 | 0 | 0 |
| oil_storage | 0 | 0 | 28 | 0 |
| pumped_hydro | 15 | 9 | 3 | 1 |
| salt_cavern_storage | 28 | 0 | 0 | 0 |
| **Summe (delta-Lauf)** | **71** | **35** | **33** | **1** |

→ nur **71/140 (51 %)** der Speicher sind funktional; deren RC sind belastbar (`rc ≈ 0`).

### Der „Energy-ohne-Power"-Artefakt war ein Perturbations-Artefakt

In allen 33 `nur_Energy`-Fällen war `capacity_power` **exakt 0.0001** (= nur das δ-Phantom),
keine echte Leistung — ein Reservoir ohne Turbine. **Ohne** Perturbation verschwinden alle
33 (→ `leer`). Beleg: die δ-RHS-Perturbation lieferte über das Phantom-Power eine
Gratis-Flusskapazität, die die LP für sinnlose Energy-Builds ausnutzte.

### Drei verschiedene Pathologien

1. **Komplementaritäts-Degenerierung** (battery both_zero): `rc_power` knotenkonstant ≈ alpha.
2. **Blockiert-aber-profitabel** (pumped_hydro: `capacity_limit = 0` für Power → `rc_power` **negativ**).
3. **Daten-Artefakte** (oil_storage `capex=1`; natural_gas_storage `capex=0`): RC grundsätzlich bedeutungslos.

CAPEX-Übersicht (Inputs):

| Tech | capex_power | capex_energy | capacity_limit | Anmerkung |
|---|---|---|---|---|
| battery | 280.35 | 289.86 | inf | normal |
| pumped_hydro | 1070.9 | 75.88 | 0 (power) | Power-Zubau teils blockiert |
| salt_cavern_storage | **0** | 2.95 | inf | Power gratis → immer gebaut |
| oil_storage | **1** | **1** | inf | Platzhalter-Daten |
| natural_gas_storage | **0** | **0** | **0** | eingefroren (Brownfield) |

---

## 4. Zusammenspiel mit der Perturbation + empirischer Vergleich

Die Lifetime-RHS-Perturbation legt ein Phantom-delta auf die RHS jeder Greenfield-
Komponente. Sie behebt **Degeneriertheit** (mehrdeutiger Dual), aber **nicht
Komplementarität** (gar kein lokaler Grenznutzen). Storage-both_zero ist Letzteres → die
Perturbation pinnt zwar den Dual, aber der ökonomisch korrekte Endpunkt existiert für eine
Einzelkomponente an (0,0) nicht.

**Mengen sind robust:** delta-Lauf vs. ohne Perturbation = Gesamt-Zubau 39 125.58 vs.
39 170.19 (0.11 %), nur degeneriertes Umschichten in salt_cavern. **Die Perturbation
verändert die Lösung nicht.**

**Aber keine der beiden Schalterstellungen ist für Storage brauchbar:**

| | Zubau-Menge | Energy-ohne-Power | Storage-RC ungebaut |
|---|---|---|---|
| delta an | korrekt | **Artefakt (33×)** | Eigen-CAPEX-Echo (knotenkonstant) |
| delta aus | korrekt | sauber | **Schein-Null** (238/280 RC = exakt 0) |

---

## 5. Hilft eine Kopplungs-Constraint (z. B. `power >= 0.01·energy`)?

Naheliegend: eine Constraint, deren Dual beide Wertströme verbindet. **Der Kanal
existiert** — mit `g = power - rho⁻¹·energy >= 0` (Dual `mu >= 0`) und `V = 0`:

```
rc_power  = capex_power  - mu·(1)        = capex_power  - mu
rc_energy = capex_energy - mu·(-rho⁻¹)   = capex_energy + rho⁻¹·mu
```

**Aber „bindend" heißt nicht „Dual ≠ 0".** Bei `power = energy = 0` ist `0 >= 0` bindend mit
Slack null und **unbestimmtem Dual** `mu ∈ [0, capex_power]` — dieselbe Degeneriertheit, nur
verschoben. Ohne Pinning wählt der Solver `mu = 0` → entkoppelt. **Und** die symmetrische
delta-Perturbation macht die Ratio sogar slack (`δ >= rho⁻¹·δ`), schaltet den Kanal also
aktiv ab → genau daher der Artefakt.

Fazit: die Constraint allein **verlagert** das Problem, statt es zu lösen. Die Lösung ist,
`mu` gezielt zu pinnen — §6.

---

## 6. Implementierte Lösung: Power-Floor (yotta) + ratio_min

Perturbiere **nur eine** Komponente. Dann zwingt die Ratio-Constraint die andere hoch, macht
sie basisch und **pinnt `mu` ökonomisch korrekt**.

### Warum an `capacity_addition` (Floor), nicht an der Lifetime-RHS

Die Ratio-Constraint liest `capacity_addition`, nicht `capacity`. Die Lifetime-RHS-
Perturbation legt ihr delta aber in `capacity` (Phantom-Bestand) → `addition` bleibt 0 →
Ratio liest `0 >= 0`, greift nicht. Auch `RHS − delta` (delta in `addition` schieben) hilft
nicht: dann ist `addition` von der Lifetime-Gleichung *hochgedrückt* (frei zwischen den
Schranken) → **basisch** → Reduced Cost 0 (Schein-Null). Damit `addition` aussagekräftig
bleibt, muss es **an einer Schranke** sitzen → wir heben die **untere Schranke** von
`capacity_addition[power]` auf `yotta` (eine eigene Perturbations-Variable).

### Mechanismus (Power-Floor, Energy folgt)

Constraint `addition_energy >= e2p_min·addition_power` (Dual `nu >= 0`), Floor nur auf Power:

```
1. addition_power = yotta              (an angehobener Schranke -> NICHT-basisch)
2. addition_energy >= e2p_min·yotta    -> Energy wird hochgezwungen (Constraint bindet)
3. addition_energy frei > 0            -> Energy basisch -> rc_energy = 0
4. rc_energy = capex_energy - nu = 0   -> nu = capex_energy - V_energy   (gepinnt!)
5. rc_power = capex_power + e2p_min·nu - V_power
            = (capex_power + e2p_min·capex_energy) - (V_power + e2p_min·V_energy)
            = Buendel-CAPEX - Buendel-Betriebswert     (pro kW Power)
```

`rc_power` trägt jetzt die **knotenspezifische Bündel-Distanz [€/kW]**. Weil
`capacity_power = yotta > 0`, ist die Probe **operativ funktional** → der knotenspezifische
Betriebswert V wird über die Duale messbar. Selbst-adaptiv: ist der Speicher fast rentabel,
baut die LP über `yotta` hinaus, die Constraint wird slack, V taucht auf. Nebeneffekt: der
„Energy-ohne-Power"-Artefakt verschwindet (Komponenten wachsen gemeinsam).

### Welche Komponente? → POWER (Numerik)

Die Folgevariable wird auf `Faktor · yotta` gezwungen; das muss über der Solver-Toleranz
bleiben. Da `energy >> power` (Dauer 6–3000 h):

| perturbiert | Folgevariable | Wert | Problem |
|---|---|---|---|
| Energy | Power = `yotta / Dauer` | gas: 1e-7 | **unter Noise** ✗ |
| **Power** | Energy = `Dauer · yotta` | gas: 0.1 | robust ✓ |

→ **Power perturbieren, Energy folgt über `energy_to_power_ratio_min`. RC aus der `power`-Zeile lesen** (`rc_energy` mechanisch 0).

### `e2p_min`-Werte (datenbasiert)

Beobachtete Dauern (`energy/power`) der funktionalen Speicher:

| Tech | min | median | max | **e2p_min** | Begründung |
|---|---|---|---|---|---|
| battery | 14.9 h | 16.1 h | 20.9 h | **10 h** | ~0.7·min, enge Verteilung |
| pumped_hydro | 6.6 h (LU-Ausreißer) | 21.2 h | 25.1 h | **4 h** | unter dem 6.6-Ausreißer (sonst LU verzerrt) |
| salt_cavern | 39 h | 105 h | 382 h | **25 h** | ~0.64·min |
| natural_gas / oil | — | — | — | überspringen | Brownfield/`capex=0` bzw. Platzhalter |

Zwei Bedingungen: (1) **unter der min. beobachteten Dauer** (sonst bindet es in echten
Builds → Verzerrung) — die harte Grenze; (2) **über dem Noise** (`e2p_min·yotta ≫ Toleranz`)
— trivial erfüllt. Faustregel ~0.7·min; Ausreißer drücken die echte Untergrenze.
**Unterschiede zwischen Techs sind groß (Faktor ~200) → zwingend pro Technologie.**

### Implementierung (Dateien)

1. **Daten / fixe Dauer:** der Datensatz steht auf seinem **losen Default**
   (`energy_to_power_ratio_min = 0`, `..._max = inf`). Die **tighte Dauer** (min = max
   = D) wird **nicht** im Datensatz hartcodiert, sondern aus dem Aufruf gesetzt:
   `config["solver"]["solver_options"]["rc_tight_e2p"] = {"battery": 16,
   "pumped_hydro": 22, "salt_cavern_storage": 145}` (Stunden). Angewendet in
   `apply_parameter_overrides_for_rc()` ([optimization_setup.py](../zen_garden/optimization_setup.py)),
   eingehängt nach `construct_params` und vor `construct_constraints`
   ([element.py](../zen_garden/model/element.py)), Key wird vor Gurobi gepoppt.
   `{}` / Weglassen = lose Default-Ratio. Dasselbe Mechanismus erlaubt per-Node-capex-
   Overrides via `rc_capex_override` (RC ist eine Knoten-Größe — so verschiebt man die
   RC eines **einzelnen** Knotens ohne den Datensatz zu editieren).
2. **Perturbation:** `perturb_storage_power_addition_for_rc()`
   ([optimization_setup.py](../zen_garden/optimization_setup.py)) hebt die untere Schranke
   von `capacity_addition[storage, power]` auf `yotta`. Guards: greenfield (`existing == 0`),
   `e2p_min` endlich & > 0, Platz für Power (`power_ceiling >= yotta`) **und** Energy
   (`energy_ceiling >= e2p_min·yotta`). Storage ist aus `perturb_lifetime_rhs_for_rc()`
   ausgenommen. Aufruf in [runner.py](../zen_garden/runner.py). Config:
   `solver.solver_options["rc_storage_power_perturbation"] = yotta`.
3. **RC-Rekonstruktion:** e2p-Dual ergänzt (s. u.).

### Korrektheits-Check der RC-Berechnung

Die ursprüngliche Rekonstruktion `rc = capex - (elec - diff)/scaling` enthielt **nur**
Lifetime- und Diffusions-Duale. Für die Power-Probe ist das **falsch**:
`capacity_addition[power]` steht mit Koeffizient `-e2p_min` in der Ratio-Constraint, sein RC
enthält daher den Term `+ e2p_min·nu`. Ergänzt in `_compute_rc_capex_equivalent()` und
`save_rc_components()`:

```
rc_power = capex - (elec_value - diff - e2p) / scaling ,   e2p = e2p_min · nu
```

Vorzeichen/Struktur spiegeln exakt die Diffusions-Behandlung (Koeffizient negativ → Beitrag
`-nu·coeff = +nu·e2p_min`). **Verifiziert** (§8).

### Grenzen

- `e2p_min` = Dauer-Annahme; die Probe misst bei Dauer = `e2p_min`. Bleibt es unter allen
  optimalen Dauern, ist die Lösung **nachweislich unverändert** (Constraint überall slack).
- **Myopic Foresight:** der Config-Knopf wird (wie die anderen Perturbationen) beim ersten
  Schritt `pop`-t → greift nur im ersten Schritt. Für Single-Step/Perfect-Foresight
  irrelevant.

---

## 7. Mathematische Herleitung: Bündel-Distanz und Break-even-Faktor

Setup: `x_P, x_E` (Power/Energy-Addition) mit Koeffizienten `c_P, c_E`; Constraint
`x_E - rho·x_P >= 0` (rho = e2p_min, Dual `nu >= 0`); Betriebswerte `V_P, V_E`.

**Reduced Cost von Power** (allg. `c̄_j = c_j - Σ λ_i a_{i,j}`):
```
c̄_P = c_P - V_P + rho·nu                 (x_P-Koeff in Ratio = -rho)        (1)
```
**nu pinnen** über x_E-Optimalität (basisch → c̄_E = 0; x_E-Koeff in Ratio = +1):
```
c̄_E = c_E - V_E - nu = 0   =>   nu = c_E - V_E                              (2)
```
**Bündel-Form** ((2) in (1)):
```
rc_power = c̄_P = (c_P + rho·c_E) - (V_P + rho·V_E) = C_bundle - V_bundle    (3)
   C_bundle = c_P + rho·c_E   [€/kW]      V_bundle = V_P + rho·V_E
```

**Break-even bei proportionaler Senkung:** beide CAPEX um Anteil `f` senken
(`c -> (1-f)c`); nu folgt über (2):
```
c̄_P' = (1-f)·C_bundle - V_bundle                                            (4)
c̄_P' = 0   =>   f = (C_bundle - V_bundle)/C_bundle = rc_power / C_bundle
```
```
┌──────────────────────────────────────────────┐
│  f = rc_power / C_bundle ,  C_bundle = c_P + rho·c_E │
└──────────────────────────────────────────────┘
```

- **Exakt** (nicht nur linear): `V_P, V_E` sind durch das übrige System bestimmt und konstant,
  bis der Speicher eintritt — genau bis dahin gilt die RC-Spanne.
- **Annual vs. overnight:** `f` ist ein Verhältnis → der Annuitätsfaktor kürzt sich. Senkt
  man die overnight-CSV-CAPEX um den Anteil `f`, sinkt der annualisierte CAPEX um denselben
  Anteil. Also: `f` einmal berechnen, beide CSVs um `(1-f)` skalieren.
- **Allgemein** (beliebige Aufteilung `Δ_P, Δ_E`): Eintritt bei `Δ_P + rho·Δ_E = rc_power`.
  „nur Energy" machbar falls `rc_power/rho ≤ c_E`; „nur Power" falls `rc_power ≤ c_P` (bei
  Storage meist **nicht** erfüllt → Power allein scheitert).

---

## 8. Verifikation (Lauf `outputs_20260617-131548`)

| Check | Ergebnis |
|---|---|
| Probe greift | `capacity_power = yotta`, Energy folgt mit `e2p_min·yotta` ✓ |
| `rc_power` knotenspezifisch | 93–875 (statt konstant 83.42) ✓ |
| Vorzeichen | überall **positiv**, kein negatives `rc_power` an Probe-Knoten ✓ |
| gebaute Speicher | 105/106 mit `rc ≈ 0` (max 0.29) ✓ |
| Artefakt weg | oil_storage komplett `leer` (war 28× nur_Energy) ✓ |
| keine Verzerrung | Gesamt-Zubau 39 167 vs. 39 125 (0.107 %) ✓ |

**Decomposition** (`rc_power = capex(76.59) + lifetime(6.83) + e2p`):

| Knoten | e2p-Beitrag | rc_power | Bedeutung |
|---|---|---|---|
| CH | 9.59 | **93.01** | fast rentabel |
| DK | 604.63 | **688.06** | weit weg |
| SE | 791.21 | **874.63** | ≈ voller Bündel-CAPEX (hoffnungslos) |

Ökonomik-Check: annualisierter Energy-CAPEX × e2p_min = 289.86 · 0.273 · 10 ≈ **791** =
e2p-Beitrag bei SE (V_energy ≈ 0) → `rc_power ≈ 875 = voller Bündel-CAPEX`. **Vorzeichen und
Größe stimmen.**

### Zwei-Stufen-Verhalten: Energy-Erweiterung durch Sunk-Power (verifiziert)

Bei Teil-Senkungen (z. B. nur CH `-5/-5`, Lauf `outputs_20260617-155542`) tritt ein
charakteristisches Zwischen-Stadium auf: `capacity_power = yotta` (am Minimum), aber
`capacity_energy` **über** dem Floor (CH: 0.00155 statt 0.001, Dauer 15.5 h statt 10 h),
während ferne Knoten am Floor (10 h) bleiben.

**Ursache — Sunk-Power:** Der yotta-Floor zwingt eine winzige Power, die damit *fixe,
bereits „bezahlte" (sunk)* Kapazität ist. Das Modell optimiert die Energy dann **bedingt
auf diese feste Power**: es hat nur die Wahl zwischen dem Minimum (`e2p_min·yotta`) und dem
*für die bestehende Power ökonomisch optimalen* Energy-Wert. Wegen der Sunk-Power und der
Near-Optimality der (gesenkten) Kosten baut es das **tatsächlich Optimale für die
vorhandene Power** — also Energy bis zur optimalen Dauer.

**Wichtig:** Das heißt **nicht**, dass das Paket rentabel ist. Auf der Power-Seite wird
**nicht mehr** als yotta gebaut (`rc_power > 0`), das Bündel ist also weiter unwirtschaftlich.
Die Energy-Erweiterung ist ein *bedingtes Optimum auf die Sunk-Power*, **kein**
Rentabilitäts-Signal.

Decomposition (`-5`-Lauf) belegt die Umschaltung:

| Knoten | Energy | e2p-Beitrag | Lifetime-Beitrag | `rc_power` | Bedeutung |
|---|---|---|---|---|---|
| CH | 0.00155 (15.5 h) | **0** (slack) | **−55.78** (Power hat Wert) | **15.81** | reine Power-Distanz |
| FR | 0.00100 (10 h) | +362.3 (bindet) | +6.83 (kein Wert) | 445.7 | Bündel-Distanz |

→ **Bedeutungs-Umschaltung von `rc_power`:** solange die e2p-Constraint **bindet** (Energy am
Floor), ist `rc_power` die **Bündel**-Distanz; sobald die Energy sich erweitert und die
Constraint **slack** wird, ist `rc_power` nur noch die **reine Power**-Distanz (die Energy ist
dann „im Geld", aber auf die Sunk-Power bedingt). Die erweiterte Dauer (15.5 h) ist
nebenbei ein nützliches Signal: sie ist die *optimale Speicher-Dauer* dieses Knotens,
aufgedeckt durch die Probe, noch bevor der Speicher voll baut.

### Break-even-Validierung bei fixem Verhältnis (verifiziert, exakt)

Mit Pfad A (`ratio_min = ratio_max = D`) ist die Dauer fix → der Break-even ist **linear
und exakt** vorhersagbar: `rc_power(neu) = rc_power(Basis) − (ΔP + D·ΔE)`. Test an
`battery @ CH` (Basis `rc_power = 97.765`, `D = 16`):

| Test | ΔP + 16·ΔE | Vorhersage `rc_power` | Ergebnis | Status |
|---|---|---|---|---|
| **−5.5 / −5.5** | 5.5 + 88 = 93.5 | 97.765 − 93.5 = **4.265** | `rc_power = 4.2649` | ungebaut (Probe), **exakt getroffen** |
| **−6 / −6** | 6 + 96 = 102 | 97.765 − 102 = −4.24 → ≤ 0 | `value_power = 0.780`, `rc_power ≈ 0` | **gebaut** (Dauer 16 h) |

→ Break-even bei `X = 97.765/17 ≈ 5.75` (symmetrische Senkung), also genau zwischen −5.5
(draußen) und −6 (drin). **Die RC ist damit empirisch bestätigt:** punktgenaue lineare
Vorhersage, sauberer Kipppunkt, kein Dauer-Drift mehr. Alle anderen Storage-Knoten im
−6-Lauf bleiben konsistent (gebaut `rc ≈ 0`, Probe `rc > 0`, keine Schein-Nullen).

---

## 9. Wie man die RC liest (Rezept + Beispiel)

Relevante Spalte: **`rc_capex_equivalent_input_units`** [€/kW].

| `value_power` | Bedeutung | RC lesen aus |
|---|---|---|
| ≈ 0.0001 (yotta) | ungebaut (Probe) | **`power`-Zeile** |
| groß | gebaut | rc ≈ 0 (nichts zu lesen) |

`rc_power` ist die **Bündel-Distanz** pro kW Power, für ein Bündel der Dauer `e2p_min`. Sie
**enthält bereits den Energy-CAPEX**. Die `energy`-Zeile an Probe-Knoten **ignorieren** (sie
ist nicht korrigiert).

Beispiele (Lauf 131548):
```
battery @ CH (fast rentabel):   power value=0.0001  rc=93.01   <- lesen
battery @ SE (weit weg):        power value=0.0001  rc=874.63  <- lesen (~voller Bündel-CAPEX)
battery @ DE (gebaut):          power value=17.29   rc=0.0     <- schon gebaut
```

**Stellhebel zum Bauen:** nicht Power allein (zu klein), sondern das **Bündel** — beide CAPEX
um `f = rc_power / C_bundle` senken (§7), in der Praxis dominiert vom Energy-CAPEX.

---

## 10. Testfall: Break-even-Validierung

Falsifizierbarer Test, ob `rc_power` korrekt = Bündel-Distanz: senke beide CAPEX eines
Knotens um `f` und der Speicher muss *gerade* eintreten. Skript:
[`rc_storage_breakeven_test.py`](../rc_storage_breakeven_test.py).

```
python rc_storage_breakeven_test.py analyze            # f pro Probe-Knoten
python rc_storage_breakeven_test.py scale battery CH 0.88   # -12% (> f) -> sollte BAUEN
python rc_storage_breakeven_test.py scale battery CH 0.91   # -9%  (< f) -> sollte NICHT bauen
python rc_storage_breakeven_test.py restore battery        # CSVs zuruecksetzen
```

Beispiel battery @ CH:
```
rc_power = 93.01 ,  C_bundle = c_P + e2p_min·c_E = 76.59 + 10·79.12 = 867.8 ,  f = 0.107
```
**Erwartung:**
- −9 % (`scale 0.91`): CH bleibt ungebaut (`value_power = yotta`, `rc_power` klein > 0).
- −12 % (`scale 0.88`): CH tritt ein (`value_power ≫ yotta`, `rc_power → 0`).

Tritt CH schon bei −9 % ein oder erst weit jenseits −12 %, ist die RC fehlerhaft. Gut
testbar sind Knoten mit `f < 1` (z. B. CH/LU); `f > 1` (z. B. SE) ist per Skalierung nicht
erreichbar (>100 % nötig → strukturell unwirtschaftlich).

---

## 11. Fix-Übersicht & Empfehlung

| # | Ansatz | liefert | Status |
|---|---|---|---|
| **A** | Flag `rc_unreliable_storage` + RC→NaN für nicht-funktionale Paare | ehrliche Markierung | optional |
| **B** | Postproc-Bündel `rc_power + Dauer·rc_energy` | Distanz ohne Modelländerung | Fallback |
| **D** | **Power-Floor + ratio_min** (§6) | knotenspez. Bündel-Distanz in `rc_power`, inkl. V | Vorstufe |
| **D′** | **Power-Floor + FIXES Verhältnis** (`ratio_min = ratio_max = D`) | **eindeutige** Bündel-Distanz bei Dauer `D`, keine Zwei-Stufen | **aktiv (Pfad A)** |

---

## 11a. Aktive Lösung: Pfad A — fixes Energy-to-Power-Verhältnis

Die Dauer-Mehrdeutigkeit (§7, §8 Zwei-Stufen) wird beseitigt, indem der **Freiheitsgrad
Dauer entfernt** wird: `energy_to_power_ratio_min = energy_to_power_ratio_max = D` pro
Technologie. Dann ist `energy = D · power` fest, der Speicher ist eine Verbundvariable, und
`rc_power` ist **immer** die eindeutige Bündel-Distanz bei Dauer `D` (keine Energy-
Erweiterung, keine Bedeutungsumschaltung).

### Gewählte `D` (manuell, aus den vorliegenden Daten, **Zubau-basiert**)

`D` = repräsentative **Zubau-Dauer** `value_energy / value_power` der real gebauten Speicher
(Lauf `outputs_20260617-131548`), bewusst auf den **Zubau** (`capacity_addition`) statt die
Gesamtkapazität geschaut, weil die e2p-Constraint auf `capacity_addition` wirkt:

| Tech | n | Median | gewichtet (Σ vE/Σ vP) | **gesetzt `D` [h]** | Begründung |
|---|---|---|---|---|---|
| battery | 10 | 16.1 | 17.0 | **16** | enge Verteilung, Median ≈ gewichtet |
| pumped_hydro | 12 | 23.2 | 22.2 | **22** | Median ≈ gewichtet (DE 59 h Ausreißer) |
| salt_cavern_storage | 27 | 107.8 | 145.8 | **145** | breite Streuung (39–382 h) → gewichtete Dauer (große Zubauten = lang) |
| natural_gas / oil | — | — | — | nicht gesetzt | Brownfield / `capex` = Platzhalter |

Gesetzt in den jeweiligen `attributes.json` (`energy_to_power_ratio_min = ratio_max = D`).
**Kein Auto-Rerun** — die Werte sind extern fixiert; bei neuen Daten manuell nachführen.

### Begleitende Code-Anpassung
Bei fixem Verhältnis kann an nahe-rentablen Knoten die **`ratio_max`**-Constraint binden
(Energy am Deckel). Deren Dual ist jetzt zusätzlich in `_compute_rc_capex_equivalent()` und
`save_rc_components()` berücksichtigt (analog zu `ratio_min`; `rc_components.csv` enthält
nun `e2p_ratio_min` *und* `e2p_ratio_max`). **Noch im nächsten Lauf zu verifizieren.**

### Kosten von Pfad A (quantifiziert)
Fixe Dauer **verändert die primale Lösung** (zwingt alle Speicher einer Tech auf `D`).
Vergleich freies vs. fixes Verhältnis (Läufe `131548` vs. `165837`, beide ohne
CAPEX-Senkung):

| Größe | Effekt |
|---|---|
| **Systemkosten (`net_present_cost`)** | **+0.015 %** (1 257 924 vs. 1 257 737) — vernachlässigbar |
| battery-Zubau | POWER +0.9 %, ENERGY −5.3 % (frei ~17 h → fix 16 h) |
| pumped_hydro-Zubau | POWER +1.2 %, ENERGY −0.5 % |
| salt_cavern-Zubau | POWER +8.1 %, ENERGY +7.5 % (breiteste Streuung → am stärksten verzerrt) |

→ **Die Verschlechterung der Zielfunktion ist mit ~0.015 % praktisch null.** Die
Deployment-Verschiebung ist bei battery/pumped klein (<1.5 % Power); **salt_cavern** wird
am stärksten verzerrt (±~8 %), weil seine freie Dauer am breitesten streut (39–382 h) —
kostet aber kaum etwas (capex_energy ≈ 2.95 €/kWh). Für die RC-Interpretierbarkeit ist das
der bewusst akzeptierte Preis; für *Deployment*-Aussagen ggf. einen separaten freien Lauf
nutzen, v. a. wenn salt_cavern-Dauern relevant sind.

### Theoretische Alternative: mehrere fixe Dauer-Varianten pro Tech

Statt *einer* fixen Dauer könnte man pro Storage-Tech **mehrere Varianten mit je fixem
e2p-Verhältnis** definieren (z. B. battery-4h, battery-8h, battery-16h) und sie als separate
Technologien gleichzeitig im Modell führen. Das **diskretisiert** den Dauer-Freiheitsgrad:
jede Variante hat einen sauberen, eindeutigen `rc_power`, und das Modell wählt endogen die
beste Variante — die Dauer-Mehrdeutigkeit verschwindet, ohne eine einzelne Dauer
aufzwingen zu müssen (geringere Verzerrung als ein einzelnes `D`). Preis: mehr
Technologien/Variablen und Daten je Variante. (Nur als Gedanke dokumentiert, nicht
umgesetzt.)

**Datenqualität (parallel, unabhängig):** `oil_storage` (`capex=1`) und
`natural_gas_storage` (`capex=0`) echte Parameter geben oder aus der RC-Auswertung
ausschließen.

---

## 12. Vertrauens-Checkliste für Storage-Zeilen

1. **Beide Komponenten real (`capacity > delta`)?** → RC belastbar (≈ 0).
2. **`value_power ≈ yotta`?** → Probe; lies `rc_power` (= Bündel-Distanz), ignoriere `rc_energy`.
3. **Bauen/Break-even:** beide CAPEX um `f = rc_power / C_bundle` senken (nicht Power allein).
4. **`rc` negativ?** → blockiert-aber-profitabel (z. B. `capacity_limit = 0`), separates Thema.
5. **`capex_specific` = 0 oder 1?** → Platzhalter-Daten, RC bedeutungslos.
6. **`e2p_min` gesetzt?** Nur dann greift die Probe; sonst bleibt der Speicher `leer` (kein RC).
7. **Pfad A aktiv (`ratio_min = ratio_max = D`)?** Dann ist `rc_power` die *eindeutige*
   Bündel-Distanz bei Dauer `D` — keine Energy-Erweiterung, keine Zwei-Stufen (§11a).
