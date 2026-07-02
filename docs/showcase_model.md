# Showcase-Modell `6_showcase_countries`

Ein kleines, schnell rechenbares 5-Länder-Modell (Volljahr mit interner Aggregation auf 24 typische
Stunden, Lösezeit ~1 min), das **alle** Reduced-Cost-Phänomene
unserer Untersuchung an *einer* Datenbasis demonstriert: zuverlässige RCs, die am Bau-Rand validierbar
sind, die operativ-vs-lifetime-Degeneration und ihren Fix, Storage-Bundle-RCs, Transport-RCs und
realistische lokale Differenzierung. Es ist die kontrollierte Vorstufe zum großen Crystal-Ball-Modell.

Datensatz: `6_showcase_countries/` · Generator: `_build_showcase.py` · Run-Helper: `_run_showcase.py`.

---

## 1. Räumliche Struktur

5 Knoten: **AT, CH, DE, FR, IT** (Mitteleuropa, real benachbart). Kanten (`energy_system/set_edges.csv`,
beide Richtungen) entlang der echten Grenzen: AT–CH, AT–DE, AT–IT, CH–DE, CH–FR, CH–IT, DE–FR, FR–IT.
Welche Kante eine Tech tatsächlich nutzen darf, steuert die **Transport-Topologie** (Abschnitt 7), nicht
das Kantenset.

## 2. Zeitliche Struktur — volle 8760 h + interne Time-Series-Aggregation (TSA)

Das ist der wichtigste technische Punkt. Wir liefern **volle 8760-Stunden-Profile** (echte
Crystal-Ball-Wetterdaten + echte Demand-Profile, Abschnitt 4) und lassen ZEN-garden zur Laufzeit
**intern aggregieren** — genau wie im Crystal-Ball-Datensatz, ohne ein willkürliches, untypisches
Stundenfenster.

**Drei Investitionsjahre.** `optimized_years = 3`, `reference_year = 2025`, `interval_between_years = 1`
→ 2025 / 2026 / 2027. Pro Jahr wird einmal über Zubau entschieden; gebaute Kapazität trägt über ihre
Lebensdauer über. Demand **+10 %/Jahr** via `demand_yearly_variation.csv` (1.0 / 1.1 / 1.21).

**TSA-Konfiguration.**
- `system.json`: `unaggregated_time_steps_per_year = 8760`, `aggregated_time_steps_per_year = 24`,
  `conduct_time_series_aggregation = true`. (Crystal Ball selbst nutzt 10; wir nehmen 24, damit auch
  Storage einen definierten RC hat.)
- Run-Config (`analysis.time_series_aggregation`): `clusterMethod = "hierarchical"`,
  `hoursPerPeriod = 1`.

**Wie die Aggregation funktioniert.**
1. `number_typical_periods = min(unaggregated, aggregated) = 24`.
2. `tsam` clustert die 8760 Stunden per **hierarchischem Clustering** auf dem *gemeinsamen* Merkmalsvektor
   aller Zeitreihen (PV/Wind/Hydro-CF + Strom-/Wärme-Demand je Knoten) zu **24 repräsentativen Stunden**.
3. Jede der 8760 realen Stunden wird ihrer Repräsentativstunde zugeordnet; die
   `time_steps_operation_duration` = Cluster-Gewichte (Summe = 8760).
4. Der Betrieb wird über die **rekonstruierte chronologische Voll-Sequenz** abgebildet (Speicherbilanz
   koppelt über die ganze Sequenz), nur 24 *verschiedene* Stunden werden optimiert.
5. `fraction_year = unaggregated / total_hours = 8760/8760 = 1` → die Kosten sind **echte Volljahres-Kosten**
   (Zielfunktion ~6·10⁵, nicht die einer 96-h-Scheibe).

> **Hinweis zu `hoursPerPeriod`:** ZEN-gardens TSA ist für `hoursPerPeriod = 1` ausgelegt (Default;
> `hoursPerPeriod = 24` wirft in dieser Version einen internen Fehler). Repräsentative *Einzelstunden* +
> chronologische Rekonstruktion erfassen das tägliche Lade-/Entlade-Muster trotzdem korrekt.

> **RC-Einheiten:** Da `fraction_year = 1`, sind interne Modell-RC und €/kW hier identisch; die Spalte
> `*_input_units` = `*` (bei der 96-h-Toy-Variante war der Faktor 96/8760, hier 1).

## 3. Carrier

| Carrier | Rolle | Preis / CO₂ |
|---|---|---|
| electricity | Nachfrage; nur aus Erzeugung (kein Import, `availability_import = 0`); Slack via `price_shed_demand = 5000 €/MWh` | endogener Knotenpreis |
| heat | Nachfrage; nur aus Boiler/heat_pump; Slack via shed | endogen |
| natural_gas | Import (∞), für Gaskessel | ~32 €/MWh (DE 30, IT 34) + **CO₂** |
| uranium | Import (∞), für Nuklear | 1.7 €/MWh, CO₂ 0 |

**CO₂-Preis** = 80 €/tCO₂ (`energy_system/attributes.json: price_carbon_emissions`). Erdgas hat
`carbon_intensity_carrier_import = 0.202 tCO₂/MWh` → effektiver Gas-Aufschlag **+16 €/MWh**, Gas
gesamt ~48 €/MWh. Das treibt die Substitution (heat_pump-vs-Gas, Erneuerbare-vs-fossil).
(Alle Kostengrößen sind aus dem Crystal-Ball-Datensatz übernommen und gerundet — Toy-Modell.)

## 4. Profile (echte 8760-h-Daten)

Alle als `max_load.csv` (Erzeuger) bzw. `demand.csv` (Nachfrage) mit Spalten `time, AT, CH, DE, FR, IT`,
**8760 Zeilen**:

- **PV / Wind / Hydro** (`max_load`): die **realen Crystal-Ball-Wetterprofile** (Kapazitätsfaktor je
  Stunde) für die 5 Länder, 1:1 übernommen. Resultierende Jahres-CF (8760-Mittel): PV AT 0.119 / CH 0.129 /
  DE 0.111 / FR 0.147 / IT 0.154; Wind AT 0.122 / CH **0.063** / DE 0.204 / FR 0.243 / IT 0.132; Hydro
  AT 0.452 / CH 0.282 / DE 0.683 / FR 0.459 / IT 0.429. → echte tägliche & saisonale Struktur, echte
  Mittagsspitzen für die Storage-Arbitrage.
- **Strom-/Wärme-Demand**: reale stündliche EU-Lastprofile (aus den ZEN-Beispieldaten), pro Land auf den
  **Ziel-Peak normiert** (`demand[n,t] = Peak[n] · Profil[n,t]/max(Profil[n])`). Peak-GW Strom AT 11 /
  CH 10 / DE 75 / FR 80 / IT 50; Wärme AT 14 / CH 12 / DE 60 / FR 45 / IT 40. So echte Form, gewählte Skala.

Nuclear, Gaskessel, heat_pump haben **konstanten** `max_load` (Skalar 0.92 bzw. 1.0), kein Profil-CSV.

## 5. Technologien & lokale Differenzierung

Asymmetrie kommt über `capacity_limit` (pro Land), Profile (CF pro Land) und `capacity_existing`
(Brownfield, `year_construction = 2020`). Kosten **aus Crystal Ball gerundet** (CAPEX €/kW, opex_fix €/kW/a,
opex_var €/MWh); Fuel separat über Carrier.

| Tech | Carrier (COP/η) | CAPEX | opex_fix/var | Lebensd. | `capacity_limit` [GW] AT/CH/DE/FR/IT | prebuilt [GW] |
|---|---|---|---|---|---|---|
| **nuclear** | uran→strom (2.95) | 6300 | 125 / 5.5 | 55 | **0** / 4 / 10 / **70** / **0** | CH 2, DE 4, FR 45 |
| **natural_gas_turbine** | gas→strom (η 53 %, cf 1.88) | 780 | 22 / 2.9 | 30 | ∞ | AT2 CH1 DE12 FR6 IT10 |
| **photovoltaics** | →strom | **490, −1%/a** | 12 / 0 | 30 | 60/40/250/300/250 | AT3 CH4 DE30 FR15 IT25 |
| **photovoltaics_capex** | →strom (=PV, **+10 € capex**) | **500, −1%/a** | 12 / 0 | 30 | **1 / 1 / 1 / 1 / 1** | 0 |
| **photovoltaics_opex** | →strom (=PV, **2× opex_fix**) | **490, −1%/a** | **24** / 0 | 30 | **1 / 1 / 1 / 1 / 1** | 0 |
| **photovoltaics_lowcf** | →strom (=PV, **½ Kapazitätsfaktor**) | **490, −1%/a** | 12 / 0 | 30 | **1 / 1 / 1 / 1 / 1** | 0 |
| **wind_onshore** | →strom | **1100, −1%/a** | 20 / 0.7 | 25 | 15/45/120/90/70 | AT1 CH2 DE25 FR12 IT6 |
| **run-of-river_hydro** | →strom | 2900 | 37 / 2 | 50 | 6/5/3/6/6 | AT5 CH4 DE2 FR5 IT5 |
| **natural_gas_boiler** | gas→wärme (1.1) | 490 | 17 / 0 | 21 | ∞ | AT10 CH8 DE45 FR30 IT32 |
| **heat_pump** | strom→wärme (COP 3) | 900 | 20 / 0 | 19 | ∞ | 0 |

PV/Wind-CAPEX sinken **−1 %/Jahr** (`capex_specific_conversion.csv`, pro Knoten×Jahr).

**Die drei PV-Klone** (`_capex`, `_opex`, `_lowcf`) sind identisch zu `photovoltaics` bis auf **genau
einen** Faktor und auf **1 GW/Land** gedeckelt — so isoliert ihre RC den Effekt dieses Faktors:
`_capex` (+10 € capex), `_opex` (doppeltes opex_fix), `_lowcf` (halber Kapazitätsfaktor, via `pv_half`-Profil).
Die **natural_gas_turbine** ist das dispatchbare Backup (Firm Capacity) — sie deckt Spitzen, setzt einen
positiven Grenzpreis und behebt damit das frühere Strom-Überschuss-/λ≈0-Problem.

Mit diesen (realistischen) Kosten baut heat_pump und **verdrängt den Gaskessel vollständig** für Wärme
(CO₂-Preis + COP 3 + billiger Erneuerbaren-Strom) — eine kohärente Dekarbonisierungs-Lösung. Der
**Gaskessel ist damit der ungebaute `buildable_rc`-Grenzfall** auf der Wärmeseite.

## 6. Storage — battery (Power & Energy getrennt)

Separater Zubau von Leistung und Energie (`capex_specific_storage = 280 €/kW`,
`capex_specific_storage_energy = 290 €/kWh`, CB-gerundet), loses Verhältnis
`energy_to_power_ratio ∈ [1, 12] h` (im RC-Lauf via `rc_tight_e2p = {battery: 4}` fixiert, damit die
Storage-Power-Perturbation feuert). Wirkungsgrad lade/entlade 0.93, self_discharge 1e-3, Lebensdauer 13 a.
Damit zeigen wir die **Bundle-RC** (Power/Energy-Differenzierung). Battery baut in den PV-reichen Knoten
und ist in den übrigen `buildable_rc`.

## 7. Transport (selektive, asymmetrische Topologie)

`capacity_limit` default 0 → eine Tech kann nur auf den explizit in `capacity_limit.csv` gelisteten
Kanten bauen. Distanz pro Kante via `distance.csv`, CAPEX = `capex_per_distance × Distanz` (CB-Werte).

- **power_line** (Strom, 546 €/km/MW, Verlust 5e-5/km): Kanten **DE–FR, DE–AT, AT–CH, CH–IT, FR–IT**
  (prebuilt 4/3/2/2/3 GW). **Kein** AT–IT (existiert als Kante, aber `capacity_limit = 0` → der
  AT–IT-Strompfad ist `not_buildable`) → Stromfluss muss Umwege nehmen → interessanter Transport-RC.
- **natural_gas_pipeline** (Gas, 265 €/km/MW): Kanten **DE–AT, DE–CH, AT–IT, FR–IT** (prebuilt 8/5/6/5).

## 8. Welche RC-Phänomene das Modell zeigt (Lauf-Ergebnisse)

Demand **vollständig gedeckt** (Shed = 0). Strompreis median ~18 €/MWh, nur ~2 % der Stunden ≈ 0
(die Gasturbine setzt einen positiven Grenzpreis → eindeutige Preise). Fallverteilung Conversion:
`built` 40, `buildable_rc` 88, `at_limit` 16, `not_buildable` 6.

Bau-Mix: heat_pump verdrängt Gas (Gaskessel → `buildable_rc`); PV in den CF-starken Knoten; Wind DE/FR/IT;
nuclear FR/DE/CH (AT/IT `not_buildable`); Hydro am Limit; Gasturbine als Firm-Backup (überwiegend Bestand,
deckt Spitzen). Battery baut **nicht** (Gas-Peaker ist günstiger für die Spitze), trägt aber eine
definierte Bundle-RC (s. u.).

**★ Kern-Showcase: die drei PV-Klone** (gedeckelt 1 GW, je ein Faktor verändert) — die RC isoliert jeden
Faktor sauber:

| PV-Variante | Abweichung von PV | RC [€/kW] (y0) |
|---|---|---|
| photovoltaics (Basis, gebaut) | — | 23 |
| photovoltaics_capex | +10 € capex | **33** (= 23 + 10) |
| photovoltaics_opex | 2× opex_fix (+12 €/kW/a) | **189** (kapitalisierter Mehr-opex) |
| photovoltaics_lowcf | ½ Kapazitätsfaktor | **339** (halber Ertrag → halb so wertvoll) |

→ Beleg, dass die RC **capex, opex_fix und Kapazitätsfaktor** korrekt berücksichtigt.

| weiteres Phänomen | wo | Beobachtung |
|---|---|---|
| `built` / `at_limit` / `not_buildable` | PV/Wind/HP/nuclear · Hydro/nuclear FR · nuclear AT-IT, power_line AT-IT | volle Fallabdeckung |
| **Bundle-RC (Power/Energy)** | battery (ungebaut) | rc_mathematical ~1120–1262 €/kW, ratio ~0.8, e2p 4, lokal differenziert (IT am nächsten) |
| fossile Strom-RC unter CO₂ | natural_gas_turbine | Peaker-RC; setzt den Strom-Grenzpreis |
| Transport-RC | power_line, gas_pipeline | gebaut / `buildable_rc` / `not_buildable` je Kante |
| lokale Differenzierung | überall | RCs unterscheiden sich pro Land (CF/Limit/Bestand/Netz) |

**lifetime- vs. operative RC.** Für reine `buildable_rc`-Erzeuger (inkl. der PV-Klone) stimmen beide
überein → RC direkt verlässlich. Die operativ-vs-lifetime-**Degeneration** (Lifetime-Kollaps) tritt v. a.
im 2-Knoten-Toy auf (s. `docs/rc_operational_reconstruction.md`). Für **Substitut/at-limit**-Techs gibt
die operative Spalte einen Überschuss (≤ 0) statt der Bau-Distanz — dort `case` + lifetime lesen. Die
operative Spalte bleibt der **Cross-Check**.

## 8b. Grenzen / Vorbehalte (ehrlich)

- **Strompreise jetzt eindeutig:** das frühere λ≈0-Überschuss-Problem (Strompreis ≈0 in ~50 % der Stunden)
  ist durch die **Gasturbine** behoben (median ~18, nur ~2 % ≈0). Damit ruhen auch die RCs
  strom-verbrauchender Techs auf gut definierten Preisen.
- **Battery baut nicht:** der Gas-Peaker (780 €/kW firm) ist günstiger für die Abendspitze als eine 4-h-
  Battery (~1440 €/kW) — ökonomisch korrekt. Storage wird daher als **`buildable_rc` mit definierter
  Bundle-RC** gezeigt (RC quantifiziert die Distanz), nicht als gebaute Tech.
- **Aggressive Dekarbonisierung:** CO₂ 80 €/t + COP-3-heat_pump verdrängen den Gaskessel vollständig — für
  2025–2027 optimistisch, als Toy-Stresstest der RC-Methode ok.
- **Ground-truth-Validierung** der RCs (±1%-Build/Nobuild): **erledigt — alle getesteten RC-Typen PASS.**
  Siehe `docs/showcase_stresstest.md`.

## 9. Ausführung & nächste Schritte

```bash
python _build_showcase.py          # Datensatz (neu) generieren
python _run_showcase.py            # Baseline-RC-Lauf (TSA, ohne Perturbation)
python _run_showcase.py pert       # RC-Lauf mit Perturbation + tight-e2p (Cross-Check)
```
Run-Config: `analysis.time_series_aggregation = {hoursPerPeriod: 1, clusterMethod: "hierarchical"}`;
Solver gurobi, `Method 2 / Crossover 1 / Presolve 0`, `use_scaling 0`, `save_duals` + `save_reduced_costs`.
Ausgabe-CSVs: `capacity_addition_analysis[_conversion/_storage/_transport].csv` mit beiden RC-Spalten
(`rc_capex_equivalent[_input_units]` = lifetime, `rc_capex_equivalent_operational[_input_units]` =
operativ) + `ratio_reduction(_operational)`.

**Stresstest:** ✅ erledigt — vollständige ±1%-Validierung in `docs/showcase_stresstest.md`
(8/8 Conversion + Gasboiler-gratis + Storage-Bundle, alle PASS).

**Geplante Folgeschritte** (separat): (a) Heatmap der RC-Nähe; (b) Übergang zum Crystal-Ball-Modell.
