# Parameter, RC und Bauentscheidung

Diese Übersicht ordnet wichtige Input-Parameter ihrer mathematischen Rolle im Modell zu und erklärt, wie sie die Reduced Costs und die Investitionsentscheidung beeinflussen.

## Grundidee

Das Modell minimiert die abgezinste Gesamtkostenfunktion

$$
J = \sum_y NPC_y
$$

mit

$$
C_y = CAPEX_y + OPEX_y^\mathrm{t} + OPEX_y^\mathrm{c} + OPEX_y^\mathrm{e}
$$

Ein Parameter kann die Reduced Costs also nicht nur über den direkten Kostenkoeffizienten verändern, sondern auch über Nebenbedingungen, Wirkungsgrade, Verfügbarkeiten oder Kapazitätsgrenzen.

## Wichtige Parameterklassen

| Parameter | Mathematische Rolle | Typische Wirkung auf RC / Bauentscheidung |
| --- | --- | --- |
| `capex_specific_conversion` | $I_{i,n,y} = \alpha_{i,y} \Delta S_{i,n,y}$ | Senkt oder erhöht direkte Investitionskosten von Conversion-Technologien. Meist der direkteste Hebel für PV, HP, CHP. |
| `capex_per_distance_transport` | $\alpha_{j,e,y} = \alpha^\mathrm{dist}_{j,e,y} h_{j,e}$ und $I_{j,e,y} = \alpha_{j,e,y}\Delta S_{j,e,y}$ | Direkt relevant für Pipelines und andere Transporttechnologien. Hängt zusätzlich an der Distanz. |
| `capex_specific_transport` | $\alpha_{j,e,y} = \alpha^\mathrm{const}_{j,y}$ | Alternative oder zusätzliche Transport-CAPEX-Komponente. |
| `opex_specific_fixed` | geht in $OPEX_y^\mathrm{t}$ ein | Ändert laufende Fixkosten. Kann Bau verhindern, obwohl CAPEX günstig ist. |
| `opex_specific_variable` | geht in $OPEX_y^\mathrm{t}$ ein | Wirkt auf laufende Nutzungskosten pro Energieeinheit. Wichtig, wenn Betrieb dominiert. |
| `price_carbon_emissions` | geht in $OPEX_y^\mathrm{e}$ ein | Höhere CO2-Preise machen emissionsarme Technologien attraktiver, auch ohne CAPEX-Änderung. |
| `conversion_factor` | physikalische Umwandlungsrelation | Ändert Output pro Input und damit Betriebskosten / Nutzwert der Anlage. |
| `transport_loss_factor_linear` | Verlustterm in Transportgleichungen | Höhere Verluste verschlechtern die Nutzbarkeit von Pipelines und erhöhen indirekte Kosten. |
| `max_load` / `min_load` | Restriktionen auf Betrieb | Können Technologien trotz guter Kosten unattraktiv oder infeasible machen. |
| `capacity_limit` | obere Schranke für Ausbau | Kann RC künstlich hoch halten, wenn die Technologie schon nahe an der Grenze ist. |
| `capacity_addition_max` / `capacity_addition_min` | Schranken für Investitionsschritt | Beeinflussen, ob überhaupt gebaut werden darf und in welchen Sprüngen. |
| `lifetime` / `depreciation_time` | Annuity-Faktor $f_h$ | Bestimmt, wie stark Investitionskosten jährlich anfallen. Kürzere Lebensdauer oder längere Abschreibung verändern CAPEX-Wirkung stark. |
| `availability_*` | Verfügbarkeits- und Angebotsrestriktionen | Können Nachfrage-/Import-/Exportpfade begrenzen und alternative Technologien begünstigen. |

## Warum nicht nur CAPEX zählt

Ein RC ist nicht nur eine Funktion des eigenen Kostenparameters. Lokal gilt vereinfacht:

$$
RC_j = c_j - A_j^T y
$$

Das bedeutet:

1. `c_j` kann sich ändern, wenn du Kostenparameter änderst.
2. Die Matrix $A$ kann sich ändern, wenn du Wirkungsgrade, Limits oder Verluste änderst.
3. Die Dualvariablen $y$ ändern sich, wenn eine andere Technologie oder ein anderer Engpass im System bindend wird.

Darum können auch Parameter ohne direkten CAPEX-Bezug die Reduced Costs und die Bauentscheidung stark beeinflussen.

## Technologiebezogene Praxis

### PV, HP, CHP

Die erste Kandidatenklasse ist meist:

- `capex_specific_conversion`
- `opex_specific_fixed`
- `opex_specific_variable`
- `conversion_factor`
- `max_load`
- `capacity_limit`

### Gas-Pipelines

Die erste Kandidatenklasse ist meist:

- `capex_per_distance_transport`
- `capex_specific_transport`
- `transport_loss_factor_linear`
- `capacity_limit`
- `max_load`

### Interpretation für deinen RC-Test

Wenn eine Technologie bei gesenktem CAPEX immer noch nicht gebaut wird, ist das meist ein Zeichen dafür, dass:

1. ein anderer Kostenparameter noch dominiert,
2. die Technologie physikalisch oder logisch eingeschränkt ist,
3. oder eine Konkurrenztechnologie im Gesamtsystem noch günstiger bleibt.

## Für deine aktuelle Analyse

Für die zuletzt getesteten Fälle gilt als Daumenregel:

1. PV, HP, CHP: zuerst CAPEX, dann OPEX und Effizienz / Load-Limits prüfen.
2. Pipelines: zuerst Distanz-CAPEX, dann Verluste und Engpassgrenzen prüfen.
3. Wenn RC trotz CAPEX-Senkung nicht auf `0` oder positivem Ausbauwert landet, ist oft nicht der CAPEX allein der Treiber.
