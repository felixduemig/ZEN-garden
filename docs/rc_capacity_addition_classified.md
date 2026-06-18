# Klassifizierte, visualisierungs-fertige RC-Analyse (pro Technologieart)

Erweitert `capacity_addition_analysis.csv` um eine **Fallunterscheidung**, den
**originalen CAPEX-Preis** und den **nötigen Kostensenkungs-Anteil** und schreibt das
Ergebnis in **drei** Dateien je Technologieart — Grundlage für die Heatmap „wo sind
ungebaute Technologien tatsächlich nah am Bau?".

Erzeugt von `Postprocess.save_capacity_addition_classified()`
([postprocess.py](../zen_garden/postprocess/postprocess.py)) bei **jedem** Model-Run.
Für **bestehende** Outputs (ohne Re-Run): `python rc_classify_existing.py [OUTPUT_DIR]`
— identische Mathematik.

### CAPEX-Quelle (wichtig)
Die Ratio `rc / capex` braucht `capex` in **derselben Einheit wie die RC** (= die
modell-interne Kapazitätseinheit). Quellen je nach Lauf:

| Variante | Storage (power/energy) | Conversion / Transport |
|---|---|---|
| **In-Model** (`postprocess.py`) | `params.capex_specific_storage` (= Dateiwert, kein Skalieren bei €/kW) | `params.capex_specific_*` (bereits unit-konvertiert) |
| **Standalone** (`rc_classify_existing.py`) | **1:1 aus den Input-CSVs** `capex_specific_storage[_energy].csv` (node-/jahresaufgelöst) | **Back-Out** `capex = rc − Σ contribution_to_rc` |

Warum für Conversion/Transport **nicht** 1:1 aus der CSV: Techs mit Nicht-kW-Referenz
(z. B. `SMR_CCS`: `Euro/(tCO2eq/hour)`) werden vom Modell **unit-konvertiert** (Faktor
1000) — der rohe CSV-Wert läge in der falschen Einheit und die Ratio wäre um diesen
Faktor verfälscht. Storage ist sauberes €/kW bzw. €/kWh → CSV = RC-Einheit, daher dort
direkt aus der Datei. Das Standalone prüft Storage zusätzlich gegen den Back-Out
(Abweichung muss ≈ 0 sein).

Hintergrund: Fälle allgemein [`capacity_addition_analysis.md`](capacity_addition_analysis.md),
Storage-Besonderheit [`rc_storage_power_energy.md`](rc_storage_power_energy.md).

---

## Ausgabedateien

| Datei | Inhalt |
|---|---|
| `capacity_addition_analysis_conversion.csv` | Conversion **inkl. Retrofitting** (`*_CCS`), eine `power`-Komponente |
| `capacity_addition_analysis_transport.csv`  | Transport, eine `power`-Komponente |
| `capacity_addition_analysis_storage.csv`    | Storage, **eine Zeile pro (tech, node, year)** mit Bündel-Struktur |

---

## 1. `case` — die Fallunterscheidung

| `case` | Erkennung | Bedeutung | RC nutzbar? |
|---|---|---|---|
| `built` | `value > 0` | echt zugebaut (brown-/greenfield), `rc ≈ 0` | — (schon gebaut) |
| `buildable_rc` | `value ≈ 0`, Platz frei, `rc > 0` | **nicht gebaut, theoretisch baubar** → ehrlicher Abstand | **✅ ja** |
| `at_limit` | `value ≈ 0`, `capacity ≈ ceiling` | nicht gebaut, **am Kapazitätslimit** → kein Zubau möglich | nein (kein Hebel) |
| `not_buildable` | `value ≈ 0`, `ceiling ≈ 0` | verboten/blockiert | nein (ignorieren) |
| `blocked_profitable` | `value ≈ 0`, `rc < 0` | blockiert, aber rechnerisch profitabel | separates Thema |
| `breakeven_unreliable` | `value ≈ 0`, Platz frei, `rc ≈ 0` | exakt an der Schwelle / Rest-Degeneriertheit | RC unsicher |

`rc_reliable = case ∈ {built, buildable_rc}` (Storage zusätzlich: e2p gesetzt **und**
keine Platzhalter-Daten `oil_storage`/`natural_gas_storage`). Für die Heatmap auf
`rc_reliable == True` und `case == buildable_rc` filtern.

---

## 2. Conversion / Transport — Spalten

Wie `capacity_addition_analysis.csv`, plus:

| Spalte | Bedeutung |
|---|---|
| `tech_type` | `conversion` / `transport` |
| `case` | s. o. |
| `capex_specific_input_units` | **originaler CAPEX** für das Planungsjahr [€/kW] — der Wert, von dem die RC abgezogen wird (`rc = capex − Betriebswert`) |
| `ratio_reduction` | `rc / capex` = **Anteil, um den der CAPEX sinken muss**, damit gebaut wird (nur für `built`/`buildable_rc`) |
| `rc_reliable` | Bool-Filter für die Heatmap |

`ratio_reduction = 0.05` ⇒ 5 % günstigerer CAPEX und die Technologie tritt ein.
`> 1` ⇒ >100 % nötig → strukturell unwirtschaftlich.

---

## 3. Storage — Bündel-Struktur (eine Zeile pro tech/node/year)

Speicher haben zwei getrennt investierte Komponenten (power [GW], energy [GWh]). Der
aus der **`power`-Zeile** gelesene Reduced Cost ist die **Bündel-Distanz**
`rc_power = C_bundle − V_bundle` mit `C_bundle = capex_power + D·capex_energy`
(`D` = `energy_to_power_ratio` [h], Pfad A: fix). Details: §6–§9 in
[`rc_storage_power_energy.md`](rc_storage_power_energy.md).

Closing-Logik: zieht man von **beiden** CAPEX **denselben absoluten Wert** Δ ab, tritt
der Speicher ein bei `Δ·1 + Δ·D = rc_power` →

```
Δ = rc_power / (1 + D)
```

| Spalte | Bedeutung |
|---|---|
| `case` | aus der `power`-Zeile (Probe trägt das Signal) |
| `rc_mathematical` | die bekannte RC = Bündel-Distanz aus der `power`-Zeile [€/kW] |
| `e2p` | `D`, Dauerfaktor [h] |
| `capex_power` | originaler Power-CAPEX [€/kW] |
| `capex_energy` | originaler Energy-CAPEX [€/kWh] |
| `C_bundle` | `capex_power + e2p·capex_energy` [€/kW] |
| `RC_power`, `RC_energy` | `Δ` — **derselbe absolute Wert** auf beide CAPEX |
| `ratio_power_reduction` | `Δ / capex_power` |
| `ratio_energy_reduction` | `Δ / capex_energy` |
| `ratio_reduction_proportional` | `f = rc_power / C_bundle` — **Alternative**: beide CAPEX um denselben **Prozentsatz** senken (§7) |

Die zwei Ratios unterscheiden sich, weil `capex_power ≠ capex_energy` (gleicher Euro-Betrag,
unterschiedlicher Prozentsatz). Für eine *einzelne* Heatmap-Kennzahl bietet sich
`ratio_energy_reduction` (Energy-CAPEX dominiert das Bündel) oder das proportionale
`ratio_reduction_proportional` an.

> **Platzhalter-Daten:** `oil_storage` (`capex=1`) und `natural_gas_storage` (`capex=0`)
> haben kein gesetztes `e2p` → keine Dekomposition, `rc_reliable = False`. Bei
> `salt_cavern_storage` ist `capex_power = 0` → `ratio_power_reduction = NaN`
> (Energy-Ratio bleibt gültig).

---

## 4. Beispiel (Lauf `outputs_20260617-175519`)

Naheste ungebaute Speicher (kleinste `ratio_energy_reduction`):

| Tech | Knoten | `ratio_energy_reduction` | `ratio_power_reduction` | `f_prop` |
|---|---|---|---|---|
| battery | AT | 0.011 | 0.013 | 0.011 |
| battery | LU | 0.061 | 0.073 | 0.061 |
| battery | HU | 0.078 | 0.094 | 0.079 |

→ `battery @ AT` ist mit ~1 % nötiger CAPEX-Senkung am dichtesten am Bau.
