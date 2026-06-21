# Erweiterter Toy + Storage-Bündel-Analyse

Dokumentiert zwei Aufgaben auf einem erweiterten Toy-Model: (1) Länder-Erweiterung,
(2) vollständige Storage-RC-Analyse nach dem **Bündel-Prinzip**
([`rc_storage_power_energy.md`](rc_storage_power_energy.md)).

---

## 1. Erweiterter Datensatz: `5_multiple_extended_countries`

Kopie von `5_multiple_time_steps_per_year`, erstellt per
[`setup`-Logik im Verlauf] / reproduzierbar. Änderungen:

| Aspekt | Wert |
|---|---|
| **Knoten** | DE, CH, **FR, IT, AT, ES** (6) — Demand (electricity, heat) & Edges existierten bereits europaweit, nur `system.json` aktiviert |
| **PV** | von konstant (`max_load=1.0`) auf **intermittent** umgestellt — reales Solarprofil aus Crystal_Ball (`max_load.csv`, 8760 Schritte). Ohne Intermittenz hätte Storage keinen Bau-Anreiz |
| **PV-Duplikat** | redundantes „photovoltaics copy" entfernt |
| **Storage** | **greenfield Battery** ergänzt (`reference_carrier=electricity`, capex_power 280.35, capex_energy 289.86, e2p frei) zusätzlich zum vorhandenen `natural_gas_storage` |

Annahmen-Begründung: natural_gas hat **konstanten** Importpreis (23) → kein
Arbitrage-Wert für `natural_gas_storage`; eine **Battery + intermittentes PV** ist der
kanonische, aussagekräftige Storage-Fall.

---

## 2. Storage-Bündel-Analyse — [`rc_storage_extended.py`](../rc_storage_extended.py)

**Config:** `rc_tight_e2p={"battery":16}` (fixiert Dauer → aktiviert die
Storage-Power-Perturbation), `rc_storage_power_perturbation=1e-4`,
`rc_lifetime_rhs_perturbation=1e-4`, Method=2/Presolve=0.

**Ablauf:** Baseline → falls Battery gebaut, CAPEX hochschrauben (×1.5,2,3,5,8,12,20)
bis nicht mehr gebaut → Bündel-RC auslesen. CAPEX am Ende auf Original zurückgesetzt.

### Ergebnis: Battery ist **extrem wirtschaftlich**

Bei Basis-CAPEX wird Battery massiv gebaut (DE 210 GW, FR 114, ES 46, IT 40 Power, Jahr 0).
**Selbst bei ×20 CAPEX** (power 5607, energy 5797) baut sie an den **Hoch-Solar-Knoten**
(CH alle Jahre, ES/FR/IT/AT Jahr 0) weiter — physikalisch plausibel: hohe PV-Intermittenz
→ Storage hat hohen Wert. Das ist ein realistischer Befund, kein Fehler.

### Die Bündel-RC ist exakt und interpretierbar (Beispiel ×20)

An den **nicht-gebauten** Knoten/Jahren liefert die Analyse die saubere Bündel-Distanz:

| Knoten/Jahr | rc_mathematical | C_bundle | RC_power = RC_energy | ratio_proportional |
|---|---|---|---|---|
| DE y0/y1/y2 | 17 432 | 98 363 | 1025.4 | **17.7 %** |
| ES y1 | 14 564 | 98 363 | 856.7 | 14.8 % |
| FR y1 | 8 052 | 98 363 | 473.7 | 8.2 % |
| AT y1 | 202 | 98 363 | 11.9 | **0.2 %** (fast gebaut) |

**Bündel-Math verifiziert** (DE):
- `C_bundle = capex_power + e2p·capex_energy = 5607 + 16·5797 = 98 362` ✓
- `RC_power = RC_energy = Δ = rc/(1+e2p) = 17432/17 = 1025.4` ✓ (gleicher absoluter Betrag auf beide CAPEX)
- `ratio_proportional = rc/C_bundle = 17432/98363 = 0.177` ✓ (Anteil, um den **beide** CAPEX sinken müssten)

→ Das **Bündel-Prinzip funktioniert auf dem erweiterten Multi-Country-Toy exakt**: die
gemeinsame power+energy-Distanz wird korrekt aus der power-Zeile gelesen, mit demselben
absoluten Δ auf beide Komponenten und dem proportionalen Anteil als Einzel-Kennzahl.

### Lesart der Kennzahl

`ratio_reduction_proportional` = Anteil, um den **beide** CAPEX (power **und** energy)
gemeinsam sinken müssten, damit Battery dort baut. DE @ ×20: 17.7 % → Battery ist dort
bei diesem (überhöhten) CAPEX noch 17.7 % vom Bau entfernt; AT y1: 0.2 % → praktisch an
der Schwelle.

---

## 3. Reproduktion

```bash
# Datensatz steht bereits unter 5_multiple_extended_countries/
python rc_storage_extended.py        # Baseline + Eskalation + Bündel-RC
```
Ergebnis-CSV: `outputs_<ts>_rc_storage_ext/battery_bundle_rc.csv`.

*Querverweise: [`rc_storage_power_energy.md`](rc_storage_power_energy.md) (Bündel-Herleitung),
[`rc_reliability_findings.md`](rc_reliability_findings.md) (Zuverlässigkeit).*
