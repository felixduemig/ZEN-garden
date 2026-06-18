# RC-Heatmaps: Visualisierung der nötigen CAPEX-Senkung

Diese Datei dokumentiert die **Heatmap-Visualisierung** der klassifizierten
Reduced-Cost-Analyse — die Antwort auf „**wo sind ungebaute Technologien
tatsächlich nah am Bau?**" als Bild (Technologien × Knoten, gefärbt nach nötiger
CAPEX-Senkung).

Datengrundlage sind die klassifizierten CSVs aus
[`rc_capacity_addition_classified.md`](rc_capacity_addition_classified.md);
die Storage-Besonderheit steht in
[`rc_storage_power_energy.md`](rc_storage_power_energy.md).

Implementierung: [`rc_heatmaps.py`](../rc_heatmaps.py) (Repo-Root, eigenständig).

---

## 1. Aufruf

**Eigenständig** (jederzeit, beliebig oft, ohne neu zu rechnen):

```bash
python rc_heatmaps.py <OUTPUT_DIR> [--vmax 100] [--storage-metric M] [--no-annot]
```

`<OUTPUT_DIR>` wird **rekursiv** nach Szenario-Ordnern durchsucht, die
`capacity_addition_analysis_{conversion,transport,storage}.csv` enthalten — man
kann also den Top-Level-Output-Ordner oder einen einzelnen Szenario-Ordner übergeben.

**Automatisch am Ende eines Model-Runs** (Opt-in, siehe §5):

```python
config["analysis"]["generate_rc_heatmaps"] = True
```

| Option | Default | Wirkung |
|---|---|---|
| `--vmax` | `100` | oberes Ende der Farbskala in %; ab hier dunkelrot. Kleiner = mehr Kontrast im unteren %-Bereich |
| `--storage-metric` | `proportional` | Storage-Kennzahl: `proportional` \| `energy` \| `power` (s. §3) |
| `--no-annot` | aus | keine Zahlen in die Zellen schreiben |

---

## 2. Ausgabe-Ordnerstruktur

Pro Szenario, **neben** den klassifizierten CSVs:

```
<scenario>/heatmaps/
└── <jahr>/                         # = reference_year + index·interval_between_years
    ├── conversion/
    │   ├── rc_heatmap_conversion_<jahr>.png             # Heatmap
    │   ├── rc_heatmap_conversion_<jahr>.csv             # Matrix tech × node (RC in %)
    │   └── rc_heatmap_conversion_<jahr>_categories.csv  # Matrix tech × node (Fälle)
    ├── transport/   …
    └── storage/     …
```

Das Jahr-Level ist **multi-year-fähig**: bei mehreren optimierten Jahren entstehen
`heatmaps/2050/…`, `heatmaps/2052/…` usw. automatisch.

---

## 3. Was wird gefärbt? (die Kennzahl)

Gezeigt wird die **anteilige nötige CAPEX-Senkung zum Zubau** in Prozent:

| Technologieart | Spalte (× 100) | Bedeutung |
|---|---|---|
| conversion | `ratio_reduction` | `rc / capex` |
| transport | `ratio_reduction` | `rc / capex` |
| storage | `ratio_reduction_proportional` *(Default)* | `rc / C_bundle` — beide CAPEX um denselben % senken |

Bei Storage wählbar via `--storage-metric`:
- `proportional` — `rc / C_bundle` (sauberes Pendant zu conversion `rc / capex`)
- `energy` — `Δ / capex_energy`
- `power` — `Δ / capex_power`

(`Δ`, `C_bundle`, e2p: siehe [`rc_storage_power_energy.md`](rc_storage_power_energy.md).)

---

## 4. Die vier visuellen Zustände

Nur **echte RC** fließen in die Farbskala — gebaute Technologien (rc ≈ 0) würden
die Skala sonst ans grüne Ende ziehen, ohne Aussage über „Abstand zum Bau".

| Zustand | `case` | Farbe |
|---|---|---|
| **echte RC** | `buildable_rc` (& `rc_reliable`) | Heatmap **grün → rot** (grün = wenig %, rot = viel) |
| **korrekt zugebaut** | `built` (rc ≈ 0) | **weiß** — fließt **nicht** in die Skala |
| **nicht baubar / am Limit** | `at_limit`, `not_buildable` | **schwarz** |
| **unzuverlässig / sonstiges** | `breakeven_unreliable`, `blocked_profitable`, Placeholder-Storage (`rc_reliable == False`) | **grau** |

Achsen: Technologien von oben nach unten (alphabetisch), Knoten von links nach
rechts (alphabetisch — stabil über Jahre hinweg für Vergleiche).

Zeilen/Spalten, die **ausschließlich** „grau/sonstiges" enthalten (keine echte RC,
nichts gebaut, nichts blockiert), werden weggelassen (z.B. `oil_storage`). Reine
weiß- oder schwarz-Zeilen bleiben erhalten — die Aussage „überall gebaut" bzw.
„überall blockiert" ist gewollt.

---

## 5. Auto-Run beim Model-Run (Flag)

| Stelle | Was |
|---|---|
| [`default_config.py`](../zen_garden/default_config.py) | Feld `Analysis.generate_rc_heatmaps: bool = False` |
| Aktivierung | `config["analysis"]["generate_rc_heatmaps"] = True` |
| [`postprocess.py`](../zen_garden/postprocess/postprocess.py) | `save_capacity_addition_analysis()` → ruft nach den klassifizierten CSVs `_generate_rc_heatmaps()` (nur wenn Flag gesetzt) |

`_generate_rc_heatmaps()` lädt [`rc_heatmaps.py`](../rc_heatmaps.py) **per Dateipfad**
(`importlib`, Repo-Root) und ruft `run()` auf `self.name_dir` (= der Szenario-Ordner)
mit Defaults (`vmax=100`, `storage_metric="proportional"`). So gibt es **eine**
Logik-Quelle; das Standalone bleibt mit allen Optionen nutzbar.

**Designentscheidungen:**
- Flag in **`analysis`**, nicht in `solver_options` — sonst würde Gurobi es als
  unbekannte Option sehen (die RC-Perturbationen werden genau deshalb vor dem Solve
  aus `solver_options` gepoppt).
- **Best-effort**: schlägt die Erzeugung fehl, gibt es nur eine Warnung; der Run
  bricht nicht ab.
- Der Ordnername wird **nicht** übergeben — `postprocess` kennt ihn selbst.

---

## 6. Verwandte Dateien

| Datei | Rolle |
|---|---|
| [`rc_heatmaps.py`](../rc_heatmaps.py) | Heatmap-Generator (Standalone + via Flag) |
| [`rc_classify_existing.py`](../rc_classify_existing.py) | klassifizierte CSVs für **bestehende** Outputs (ohne Re-Run) |
| [`rc_capacity_addition_classified.md`](rc_capacity_addition_classified.md) | die klassifizierten CSVs (Fälle, CAPEX, Ratios) |
| [`rc_storage_power_energy.md`](rc_storage_power_energy.md) | Storage-Bündel (e2p, `C_bundle`, `Δ`) |
| [`rc_lifetime_rhs_perturbation.md`](rc_lifetime_rhs_perturbation.md) | Perturbation für zuverlässige RC (conversion/transport) |
