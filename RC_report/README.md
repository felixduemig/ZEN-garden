# RC-Report — Skripte, Outputs, Reproduktion

Alle Skripte und Ergebnisse der Untersuchung **„Warum die operative Reduced-Cost-
Rekonstruktion die Bau-Distanz mancher Crystal-Ball-Conversion-Techs unterschätzt"**
(2026-06-23). Dieser Ordner ist der **Einstiegspunkt**: er bündelt die Skripte; die
Schreibwerke liegen in `docs/`, die (großen) Solver-Outputs in `outputs_*/` (siehe unten).

## Reproduktion — Grundregeln
- **Python:** `C:/Users/felix/anaconda3/envs/zen-garden-env/python.exe`
- **Immer aus der Repo-Wurzel ausführen** (`...\ZEN-garden`), nicht aus diesem Ordner:
  `python RC_report/<skript>.py`. Die Skripte lösen Pfade relativ zur Wurzel auf.
- Read-only-Analysen (a1–a10, toy_lp*) brauchen nur die vorhandenen Outputs.
  Solver-Skripte (build/demo/sweep/test_island, cb_validate5) brauchen Gurobi
  (Method 2 + Crossover 1 + Presolve 0, `use_scaling 0`).

## Skripte

| Skript | Zweck | Erzeugt / liest | Solver? |
|---|---|---|---|
| `a1_arithmetic.py` | native Duale, Dauer-Gewichte, max_load sichten (Lead 3) | liest runC | nein |
| `a2_reproduce.py` | erste RC-Reproduktion (Scaling-Varianten) | liest runC | nein |
| **`a3_repro2.py`** | **reproduziert die berichtete operative RC exakt** aus nativen Dualen (Lead 3 ✓) | liest runC | nein |
| **`a4_nu_from_lambda.py`** | **ν aus Knotenpreisen λ, maschinengenau** (Lead 1 ✓) | liest runC | nein |
| `a5_price_setter.py` | Pro-Schritt-Beitrag m·ν, ES-Preissetzer | liest runC | nein |
| `a6_congestion.py` | ES-Import-Engpass (Leitungs-caps, Transport-Duale) | liest runC | nein |
| **`a7_scarcity.py`** | **ES gesättigter Knappheits-Vertex** (alle 6 Aggregate am cap) | liest runC | nein |
| `a8_run_compare.py` | ν über runA/B/C vergleichen | liest A/B/C | nein |
| `a9_repro_allruns.py` | RC über alle Läufe reproduzieren | liest A/B/C | nein |
| `a10_fingerprint.py` | Knappheits-Fingerabdruck über die 4 Techs | liest runC | nein |
| `toy_lp.py`, `toy_lp2.py` | frühe scipy-Spielzeuge (überholt von toy_lp3) | — | nein |
| **`toy_lp3.py`** | **minimales Gegenbeispiel: 9×-Überbewertung, baut 0** | — | nein (scipy) |
| **`build_island.py`** | erzeugt den Reproducer-Datensatz `rc_scarcity_demo/` | schreibt Dataset | nein |
| **`demo_island.py`** | **der echte ZEN-garden-Beweis** (A/B/C + capex-Sweep, 3×) | Re-Solves → outputs_island | **ja** |
| `sweep_island.py` | Nachfrage-Sweep (Preis/Peaker/RC) | Re-Solves → outputs_island | **ja** |
| `run_island.py` | Einzel-Solve + Dispatch inspizieren | Re-Solve → outputs_island | **ja** |
| **`test_tiny_build.py`** | **Solver-Swallow-Schwelle** (~1e-6 GW) | Re-Solves → outputs_island | **ja** |
| `pick_validation_cases.py` | wählt robuste ±1%-Validierungsfälle | liest runC/runB | nein |
| `cb_validate5.py` *(noch in `_rc_analysis/`, läuft)* | ±1%-Validierung 5 robuster CB-RCs | Re-Solves → validate5_* | **ja** |

> `cb_validate5.py` liegt noch in `_rc_analysis/`, weil der Validierungslauf es gerade
> benutzt. Sobald er fertig ist, wandert es hierher (siehe „Offene Aufräum-Schritte").

## Outputs (bewusst auf Repo-Ebene belassen — groß bzw. in Benutzung)

| Pfad | Inhalt | regenerierbar? |
|---|---|---|
| `outputs_CB_overnight/runA, runB, runC/` | die 3 CB-Solves (A=keine Pert, B=rhs-Pert 1e-3, C=clean) — **Quelldaten** | nein (Overnight-Run; ~11 min/Solve) |
| `outputs_CB_overnight/validate_20260623-011718/` | ±1%-Ground-Truth: nuclear ES / electrolysis FI **FAIL** | via override re-solve |
| `outputs_CB_overnight/validate_20260623-080711/` | PV CZ clean **PASS** | via override re-solve |
| `outputs_CB_overnight/validate5_*/` | **5 robuste Techs ±1% (läuft gerade)** | via `cb_validate5.py` |
| `outputs_island/` | Reproducer-Solves (demo/sweep/tiny) | via `demo_island.py` etc. |
| `rc_scarcity_demo/` | Reproducer-Datensatz | via `build_island.py` |

## Schreibwerke (in `docs/`)

| Doc | Inhalt |
|---|---|
| `docs/rc_crystalball_conversion_failure.md` (+`_DE`) | Root-Cause: Leads 1–3 widerlegt, Mechanismus, Unbehebbarkeit |
| `docs/rc_scarcity_reproducer_DE.md` | der Reproducer + Brücke zu CB ES |
| `docs/rc_interpretability_status_DE.md` | harte Fakten (F1–F9) / Thesen (T1–T5) / Lücken (L1–L4) |
| `docs/rc_*.md` (übrige) | Vorläufer: Methodik, operative Rekonstruktion, Storage, Heatmaps |

## Ergebnis → Artefakt (so ist jede Kernaussage belegt)

1. **RC-Arithmetik korrekt** → `a3_repro2.py` (reproduziert die CSV exakt).
2. **Carrier-Behandlung korrekt** (inkl. Elektrolyse-H₂) → `a4_nu_from_lambda.py` (|Δ|=0).
3. **Vollständigkeit, kein Kapazitäts-Leak** → `a6`/`a7` + Dual-Checks (capacity-limit-Dual=0).
4. **ES = gesättigter Engpass-Vertex** (Preis 0,179 = keine laufende Grenz-MC) → `a7_scarcity.py`, `a6_congestion.py`.
5. **CB-Validierung: nuclear/electrolysis FAIL, PV/wind PASS** → `outputs_CB_overnight/validate_20260623-*`.
6. **Minimal-Gegenbeispiel 9×, baut 0** → `toy_lp3.py`.
7. **Reproducer in echtem ZEN-garden, 3×, baut nur Schimmer** → `build_island.py`+`demo_island.py`, `docs/rc_scarcity_reproducer_DE.md`.
8. **Solver schluckt Bau erst <~1e-6 GW** (numerische These eingegrenzt) → `test_tiny_build.py`.
9. **5 robuste CB-RCs ±1%-validiert** → `cb_validate5.py` + `outputs_CB_overnight/validate5_*` (läuft).

## Offene Aufräum-Schritte (nach dem laufenden Validierungslauf)
- `cb_validate5.py` von `_rc_analysis/` hierher verschieben, `_rc_analysis/` löschen.
- `validate5_*`-Ergebnis (PASS/FAIL + rohe Baumengen) in dieses README aufnehmen.
