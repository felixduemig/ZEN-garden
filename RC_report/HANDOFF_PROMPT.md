# Handoff-Prompt (als erste Nachricht in die neue Session kopieren)

---

Du übernimmst ein laufendes **Semesterarbeits**-Projekt von Felix (Semesterarbeit / term paper, **KEINE** Masterarbeit). Es geht um die **Reduced-Cost-(RC)-Rekonstruktion** in **ZEN-garden** (Energiesystem-Optimierung, linopy + Gurobi): aus einem einzigen LP-Solve ablesen, *wie weit eine ungebaute Technologie vom Bauen entfernt ist* (capex-äquivalenter Reduced Cost). Wir validieren das am **Crystal-Ball-(CB)**-Datensatz (28 Knoten, 1-Jahres-Snapshot 2050, 10 typische Stunden) und an einem kleinen **Showcase**-Modell, und schreiben parallel den **Report (Semesterarbeit)**.

**Sprich Deutsch. Schreib Formeln terminal-lesbar (Code-Blöcke / ASCII, NIEMALS LaTeX wie `$\sum$` — das rendert nicht und Felix hat sich zweimal beschwert). Behaupte keine Mechanismen ohne Datenbeleg — verifiziere erst, dann sag es. Das ist die wichtigste Arbeitsregel: Felix hat „allgemeine Vermutungen ohne Fundament" explizit kritisiert.**

## 1. Lies ZUERST diese Dateien (in der Reihenfolge), dann hast du den vollen Kontext

**Memory (Projektgedächtnis):**
- `C:\Users\felix\.claude\projects\C--Users-felix-Documents-GitHub-ZEN-garden\memory\MEMORY.md` (Index)
- `…\memory\cb-snapshot-rc-findings.md` ← **das wichtigste Doc**: Root-Cause, Validierung, Lever C verworfen, nuclear@FR-vs-ES
- `…\memory\rc-report-todos.md` (offene Thesis-Aufgaben)
- `…\memory\rc-reliability-findings.md`, `…\memory\showcase-model.md`

**Working Docs (Bericht-Pipeline, im Repo `C:\Users\felix\Documents\GitHub\ZEN-garden\RC_report\`):**
- `RC_report\cb_test_status.md` ← Master-Status: was getestet, Ergebnisse, Schlussfolgerungen, offene Tests (P1–P6)
- `RC_report\cb_rc_validation_collected.md` ← 15 PASS / 3 FAIL ±1%-Validierung + Takeaways
- `RC_report\lever_equivalence.md` (Kosten-/Wert-Hebel-Äquivalenz)
- `RC_report\rc_reliability_map.png` + `rc_reliability_map.py` (Zuverlässigkeits-Landkarte, Swing-gefärbt)
- `RC_report\discussion_draft.md`, `paper_gaps_to_integrate.md`, `README.md`

**Tiefe technische Docs (`C:\Users\felix\Documents\GitHub\ZEN-garden\docs\`):**
- `docs\rc_crystalball_conversion_failure.md` (+`_DE.md`) ← Root-Cause-Beweis (Scarcity-Vertex-Degeneration, untere Schranke, single-solve nicht korrigierbar)
- `docs\rc_interpretability_status_DE.md` (F1–F9 harte Fakten, T1–T5 Thesen, L1–L4 Lücken)
- `docs\rc_scarcity_reproducer_DE.md`

**Code (Repo-Root):**
- `zen_garden\postprocess\postprocess.py:486` = `_compute_rc_capex_equivalent` (Formel & welche Duals eingehen)
- `zen_garden\optimization_setup.py:822` = `perturb_lifetime_rhs_for_rc` (die Perturbation)
- `rc_capex_file_override.py` (Capex-Override-Kontextmanager für ±1%-Re-Solves)

**Thesis (`C:\Users\felix\Documents\GitHub\ST_Final_Report_Felix_Duemig\thesis\`):**
- `STYLEGUIDE.md`; Sections: `03_Framework.tex` (Showcase- + PV-Clone-Grafik drin), `05_Results.tex` (§5.1 Hebel, §5.2 CB Part 2), `02_Appendix.tex` (Dead-Ends inkl. Lever C), `06_Discussion.tex`
- Kompilieren: aus dem `thesis`-Ordner `latexmk -pdf -shell-escape -interaction=nonstopmode 99_Main.tex`
- Struktur folgt der **Vorlage** (Beispiel-PDFs nur für Nicht-Vorlage-Aspekte); Subsubsections sind nummeriert (`secnumdepth=3`).

## 2. Wie die RC berechnet wird (Kurz, damit du es nicht neu herleitest)

```
RC = capex − (V − diffusion − e2p) / scaling ,   scaling = annuity_factor · Σ_pay discount
```
Zwei Varianten für den Kapazitätswert V:
- **operational (bevorzugt):** V = Σ_t m_t·ν_t − fixe_opex ,  ν_t = Dual von `constraint_capacity_factor_conversion` (m_t·S ≥ G_t). Degeneranz-immun gegen den Lifetime-Kollaps.
- **lifetime (legacy):** V aus dem Dual von `constraint_technology_lifetime`; kollabiert bei ungebauten Greenfield-Knoten auf 0 → braucht die Perturbation.
Gurobi-Settings für saubere Duals: **Method 2, Crossover 1, Presolve 0, use_scaling 0**.

## 3. Stand (was solide / erledigt ist)

- **±1%-Validierung (degeneranz-immune Ground Truth via Capex-Re-Solve): 15 distinct PASS / 3 FAIL.** PASS quer über Tech-Typen inkl. Nicht-Renewable-Conversion (heat_pump_DH, methanol_from_hydrogen, natural_gas_turbine_CCS) UND **nuclear@FR (baut 41 GW am vorhergesagten Punkt)**.
- **3 FAIL, alle erklärt:** nuclear@ES + electrolysis@FI = **Scarcity-Vertex-Degeneration** (Perturbations-Swing fängt sie); coal_to_cement_fuel@SK = **Constraint-Pinning** (Swing fängt sie NICHT — 2. Fehler-Eimer).
- **Detektor-Heuristik = B (Perturbations-Swing):** clean (runC) vs. rhs-perturbiert (runB) operational-RC; großer Swing = degeneriert. Validiert (nuclear ES 9.4pp/FAIL vs FR 0.062pp/PASS).
- **Lever C (Nodal-Demand-Kink) GETESTET & VERWORFEN** — probt Primal-Preis-Sensitivität statt Dual-Eindeutigkeit, verfehlt ES. Dokumentiert in Appendix `app:dead-ends`. **NICHT erneut vorschlagen.** Alle C-Artefakte sind gelöscht.
- **Thesis:** zwei Framework-Grafiken eingebaut (Showcase-Struktur, PV-Clones), §5.1-Hebel mit validierten Zahlen, secnumdepth=3. Kompiliert sauber (47 Seiten).

## 4. DIE LAUFENDE AUFGABE — hier weitermachen

**Frage, die wir gerade rock-solid klären wollen:** *Warum funktioniert der clean operational RC für nuclear@FR, aber nicht für nuclear@ES?* (Felix will es niet-und-nagelfest, an echten Zahlen, nicht behauptet.)

**FR ist verstanden & solide:** Preis 88 = Markt-Median (eindeutig, nicht abgeschnitten) → marginaler Wert = realisierter Wert → RC exakt (baut 41 GW).

**ES — verifizierte Fakten:** import-isoliert (power_line FR→ES 2.0/2.0 und PT→ES 2.5/2.5 beide AM CAP in h0); h0-Preis 267.9 = lokaler Rent (Median aller Knoten 89); 58% des Werts aus dieser einen, groß-gewichteten Stunde (Gewicht 1495 h); **op_C 2.26% vs op_B 11.70%** (gleicher Primal, anderer Dual → Wert ist dual-mehrdeutig, clean griff das optimistische Ende); baut bei −11.7% noch 0, bei −50% volle 7.16 GW → clean-RC unterschätzt ≥5×.

**WIDERLEGT (nicht wiederholen):** „endlicher Bau crasht den ES-Preis" — der Preis ist klebrig (7 GW Zubau → h0 nur 267.9→251.2).

**OFFENER WIDERSPRUCH, den ein laufender Sweep löst:** Eine grobe Wertrechnung (nuclear verdient ~243 Marge über 1495 h in h0) macht nuclear schon bei vollem Capex fast rentabel (passt zu 2.3%), widerspricht aber „baut bei −11.7% noch 0". 

**→ ERSTE AKTION:** Lies das Ergebnis des laufenden Capex-Sweeps:
```
C:\Users\felix\Documents\GitHub\ZEN-garden\outputs_CB_overnight\es_sweep\sweep.csv
```
(Script `RC_report\_es_sweep.py`, Schnitte 8/15/22/30/40%, baut nuclear@ES je Schnitt → wahre Bauschwelle). Falls noch nicht fertig: Prozess prüfen mit PowerShell `Get-Process python`. Dann am Break-even den **realisierten Jahreswert** sauber nachrechnen (Zeitgewichte × Output × (Preis − Grenzkosten≈8), Daten in `outputs_CB_overnight\es_finite_proof\` und `runC\`) und damit den Widerspruch auflösen: ist die *marginale* Einheit viel weniger wert als der Durchschnitt, oder war die Wertrechnung daneben? Ergebnis dann als endgültige, widerspruchsfreie ES-Erklärung formulieren (und falls die Kurve etwas anderes sagt, die Diagnose korrigieren).

## 5. Umgebung & Betriebsregeln

- Python: `C:/Users/felix/anaconda3/envs/zen-garden-env/python.exe` ; Repo: `C:\Users\felix\Documents\GitHub\ZEN-garden` ; OS Windows, Shell PowerShell + Bash-Tool.
- **CB-Re-Solve ≈ 8–15 min.** **NIE zwei schwere Gurobi-Solves parallel** (CPU/RAM-Thrash, OOM).
- Hintergrund-Läufe: `SetThreadExecutionState`-Keep-Awake ins Script bauen (sonst killt Idle-Standby den Lauf, ist nachts passiert). App offen lassen ODER detached starten.
- Datensatz-Overrides (Capex/Demand) IMMER byte-genau wiederherstellen (Kontextmanager mit `finally`); nach jedem Abbruch prüfen, dass `ZEN-models\data\Crystal_Ball\…` wieder im Original ist.
- Temporäre Experiment-Scripte heißen `RC_report\_*.py` und dürfen nach Gebrauch gelöscht werden; Befunde aber sichern (Memory + ggf. Appendix-Dead-Ends).

## 6. Offene To-dos für den finalen Report (Semesterarbeit)

Vollständige Liste in `RC_report\cb_test_status.md` (P1–P6) und `…\memory\rc-report-todos.md`; Backlog-Detail `RC_report\paper_gaps_to_integrate.md`. Kondensiert:

**A) Analyse / Experimente (teils CSV-Arbeit ohne Solve, teils CB-Re-Solves):**
- **P5 — Populations-Zensus** aus runC: Anteile built / at-limit / buildable-reliable / flagged → **§5.2.2**. Reine CSV-Auswertung, schnellster Win, kein Solve.
- **P1 — Reliability-Detektor bauen & testen** → **§5.2.6**: (a) Swing-Klassifikator über *alle* buildable_rc-Fälle, gegen die 18 ±1%-Labels legen → Threshold + Precision/Recall (Swing liegt in runC/runB, kein Solve); (b) Constraint-Pinning-Detektor (bindet die Referenz-Carrier-Bilanz/Min-Constraint?) — der 2. Fehler-Eimer, den der Swing verfehlt.
- **P2 — untere-Schranke-Lücke beziffern:** Bisection auf nuclear@ES + electrolysis@FI → exakter Unterschätzungs-Faktor (bisher nur „≥5×").
- **P3 — Abdeckungslücken:** Storage-Bundle + Transport ±1% am CB (bisher nur Conversion); at-limit-Fälle; eine must-run-Tech (min_load>0).
- **P4 — mehr PASS-Knoten** für breitere Evidenz (7 Restkandidaten + Tech-Diversität; in kleinen Chunks, da späte Solves langsam wurden).
- **P6 — Multi-Period-Check:** CB ist 1-Jahres-Snapshot; im Mehrperioden-Slice gegenprüfen.
- **CB-CAPEX nach Angreifbarkeit screenen** (knotengleich + kleine RC + Literatur-Spread; PV/Wind/Elektrolyse/WP) → **§5.2.8** Mini-Case-Studies.

**B) Schreiben / Struktur (gemäß `thesis\STYLEGUIDE.md`):**
- **Skelette in Prosa ausschreiben:** §5.2 (CB Part 2), §2 Background, §3 Framework, §4 Methodology, §A Appendix, §0 Abstract.
- **§5.1 Lever-Framing** final mit Felix abstimmen.
- **§6 Discussion-Zusatzpunkte** aus `RC_report\discussion_draft.md` (untere-Schranke-Garantie, Near-Optimal/MGA-Einordnung, ceteris-paribus-Nicht-Komponierbarkeit) nach Wahl ergänzen.

**Schon erledigt (nicht doppeln):** secnumdepth=3; zwei Framework-Grafiken (Showcase-Struktur, PV-Clones); §5.1-Hebel mit validierten Zahlen; §5.2-Bullet-Skelett; 15-PASS-Validierung; Lever C verworfen + im Appendix dokumentiert.

**Bestätige kurz, dass du die Kerndateien gelesen hast, gib mir den aktuellen Stand des ES-Sweeps, und lass uns die ES-Erklärung zu Ende bringen.**
