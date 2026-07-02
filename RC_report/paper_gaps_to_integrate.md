# Backlog: Befunde aus der RC-Session, die noch NICHT im Paper sind

*Stand 2026-06-23. Abgleich des Entwurfs `…/GitHub/ST_Final_Report_Felix_Duemig/thesis`
gegen unsere Ergebnisse (`docs/rc_*.md`, `RC_report/*`, `outputs_CB_overnight/*`). Reine
**Zuordnung** — noch nichts implementiert. Priorität: ★★★ Kernbefund · ★★ stark · ★ Detail.*

**Ist-Stand Paper:** Part 1 (Showcase) ist vollständig. **Part 2 (Crystal Ball) ist nur ein
4-Bullet-Hook** (`05_Results.tex` Z. 445–453). Methodology/Appendix/Discussion sind Skelette
mit konkreten Leerstellen, die unten gefüllt werden. Wichtig: Der Showcase **vermeidet bewusst
Preis-Degeneration** (Firm-Gasturbine fixiert λ) — genau die Degeneration, die in CB zuschlägt.
Damit ist CB-Part 2 der natürliche Ort für unsere Befunde.

---

## A) Results Part 2 — Crystal Ball (§5.2, `sec:results-crystalball`) — Hauptanteil

**A1 ★★★ „Es skaliert": ±1%-Validierung an 5 robusten Tech-Knoten besteht.**
PV@NO, wind_onshore@NO, wind_offshore@FR, run-of-river@SK, reservoir_hydro@CH — 5 verschiedene
Technologie-Archetypen über 4 Länder, alle perturbations-stabil, alle ±1%-PASS.
→ belegt, dass die Methode auch im großen Modell funktioniert.
*Status: LÄUFT (`cb_validate5.py`, `outputs_CB_overnight/validate5_*`). Quelle: dieser Run.*

**A2 ★★★ Knoten-Spezifität: die Methode ist an den meisten CB-Knoten verlässlich.**
Nuclear baut an 8 Knoten (BE,BG,CH,DE,HU,RO,SI,SK), hat eine robuste buildable-RC an FR
(Perturbations-Swing 0,06 pp); degeneriert **nur** an import-isolierten Knoten (ES,FI,SE,UK,NL).
→ Das Versagen ist strukturell lokalisierbar, kein Flächenproblem.
*Status: SOLID. Quelle: `RC_report/pick_validation_cases.py`, runC/runB-CSVs, Memory.*

**A3 ★★★ „Wo Degeneration zuschlägt": die Import-Insel-Überbewertung (Headline-Negativ).**
nuclear@ES und electrolysis@FI fallen durch ±1% (bauen 0 am rekonstruierten Break-even).
Mechanismus präzise, **nicht** hand-wavy: gesättigter Knappheits-Vertex (alle 6 ES-Erzeuger am
Verfügbarkeits-cap, Importe verstopft — `FR→ES`-Leitung cap 0; Preis 0,179 = Knappheitsrente
zwischen NGT 0,130 und biomass 0,229). Die operative RC liest den **Nachfrage-Entlastungs**-Preis,
den ein neuer **Erzeuger** nicht realisiert → RC überschätzt den Wert / unterschätzt die Distanz.
Größenordnung: clean RC 2,26 % vs. wahr > 11,8 % (nuclear), 9,74 % vs. > 14,9 % (electrolysis).
→ Das ist der **CB-Analog des Transport-marginal-vs-finite (§5.1)**, hier durch *Preis*-Degeneration
ausgelöst (die der Showcase vermeidet). Sauber an die Transport-Erzählung anschließbar.
*Status: SOLID. Quelle: `docs/rc_crystalball_conversion_failure.md`, `RC_report/a5–a10`, validate_*-Ordner.*

**A4 ★★ Degeneration-Heuristik: Perturbations-Swing als Detektor.**
`|RC_clean − RC_pert|` trennt sauber: nuclear 9,4 pp / electro 5,0 pp (unzuverlässig) vs.
PV 0,38 / wind 0,09 (robust). → die „Heuristik, die Degeneration teilweise auflöst" (Hook-Bullet 3).
*Status: SOLID. Quelle: runA/B/C-Vergleich, `docs/rc_interpretability_status_DE.md` (F8).*

**A5 ★★ Reproducer als Mechanismus-Beleg (optional, Abwägung nötig).**
Minimaler 2-Knoten/1-Leitung ZEN-garden-Datensatz `rc_scarcity_demo`, der die Überbewertung im
echten Solver mit unseren Settings zeigt (RC-ratio 0,25 vs. wahr 0,75, 3×; capex-Sweep: baut
0,01 GW am Break-even, springt erst bei ~750 auf 12 GW).
→ Könnte die A3-Erklärung stützen. **Abwägung:** der Entwurf verzichtet bewusst auf das scipy-Toy
(„not reported, to avoid confusing the narrative"). Der Reproducer ist aber ein *ZEN-garden-Modell*
(konsistent mit der Report-Linie). Alternativ A3 direkt aus CB-ES-Dispatch erklären.
*Status: SOLID. Quelle: `docs/rc_scarcity_reproducer_DE.md`, `RC_report/build_island.py`, `demo_island.py`.*

**A6 ★ Setup-Kontrast Snapshot vs. Showcase.**
CB = 28 Knoten, **1 optimiertes Jahr (2050)**, 10 typische Stunden, 68 Conversion + 5 Storage +
5 Transport; Single-Year-Snapshot vs. 3-Perioden-Showcase. → erster Hook-Bullet von Part 2.
*Status: SOLID. Quelle: runC `system.json`. (Teils auch Framework §3.2, siehe E1.)*

---

## B) Methodology (§4) — bestehende Leerstellen füllen

**B1 ★★ Vollständigkeitssatz für CB bestätigt (füllt den offenen Caveat).**
§4.3 (`sec:operational-dual`) sagt explizit: „when moving to Crystal Ball — check for MILP/min-load
or reserve constraints". Wir haben geprüft: CB ist **reines LP** (keine On/Off-Binärvariablen, kein
`constraint_technology_on_off`, keine Reserve-/Kapazitätsmarkt-Constraints), Kapazitätslimit-Dual=0.
→ Der Vollständigkeitssatz hält auch in CB; der Caveat kann als „verifiziert" geschlossen werden.
*Status: SOLID. Quelle: `RC_report/a-checks`, `docs/rc_crystalball_conversion_failure.md` (Lead 2).*

**B2 ★★ Operative ν=λ-Identität maschinengenau auch in CB — inkl. Elektrolyse.**
Die heat-pump-„Spread"-Erzählung (§4.3) generalisiert: ν_t = max(0, λ_H2 − 1,901·λ_elec − dur·var)
für Elektrolyse (Referenz-Carrier Wasserstoff), maschinengenau aus λ reproduziert (|Δ|=0).
→ konkreter Beleg, dass die operative Formel im großen Modell mit mehreren Carriern stimmt.
*Status: SOLID. Quelle: `RC_report/a4_nu_from_lambda.py`, `a3_repro2.py`.*

**B3 ★★ RC ist an degenerierten Knoten eine *untere Schranke* (präzise Charakterisierung).**
Aus Konvexität: rekonstruierte RC ≤ wahre Distanz (für `buildable_rc`+reliable Conversion).
→ ergänzt §4.4 (`which-dual`) / §4.5 (Klassifikation): die operative RC ist nicht nur „degeneracy-
robuster", sondern an Preis-degenerierten Knoten *richtungstreu konservativ* (nie zu pessimistisch).
*Status: SOLID. Quelle: `docs/rc_interpretability_status_DE.md` (T2/T3).*

**B4 ★ Detektion in die Klassifikation aufnehmen.**
§4.5/§4.6: ein `rc_is_lower_bound`-Flag aus dem Perturbations-Swing (A4) als zusätzliche Kategorie
neben built/buildable/at-limit/unreliable. → macht die Heuristik aus Part 2 methodisch greifbar.
*Status: Vorschlag. Quelle: `docs/rc_interpretability_status_DE.md` (§4).*

---

## C) Appendix — Numerical Pitfalls (`app:problems`, „More To Come" Z. 35)

**C1 ★★ Neuer Pitfall: marginal-vs-finite an Preis-degenerierten Knoten.**
Das CB-Pendant zum Transport-Gap, aber durch *Preis*-Degeneration ausgelöst: an gesättigten
Import-Inseln liest die RC eine Knappheitsrente, die der erste *endliche* Bau auslöscht (konkave
Wertfunktion). Unterscheidet sich vom Kapazitäts-Leak (nicht per Perturbation behebbar).
*Status: SOLID. Quelle: `docs/rc_crystalball_conversion_failure.md`.*

**C2 ★ Neuer Pitfall: Solver-Swallow-Schwelle (~1e-6 GW).**
Gurobi realisiert optimale Mini-Bauten bis 1e-5 GW ziffergenau, kippt sie aber bei 1e-7 GW auf 0.
→ Risiko falscher ±1%-FAILs bei Tech *genau* am Break-even; Gegenmittel: an der **rohen** Baumenge
validieren, nicht an einer 0/1-Schwelle. (Für nuclear/electrolysis ausgeschlossen — dort baut exakt 0,
533 €/kW jenseits des Break-even.)
*Status: SOLID. Quelle: `RC_report/test_tiny_build.py`, validate-Ordner volle Präzision.*

**C3 ★ „CB ist reines LP" als belegte Fußnote** (stützt B1 und die Completeness-Aussage).
*Status: SOLID. Quelle: wie B1.*

---

## D) Discussion (§6) — Hooks mit unseren Befunden untermauern

**D1 ★★ Die ehrliche Grenze, jetzt mit CB-Evidenz.**
„Limits: degeneracy (price non-uniqueness)" ist schon als Hook da — wir liefern den konkreten Fall
(Import-Inseln), die Größenordnung (3×–5×), und die Lokalisierbarkeit (nur schwach vernetzte Knoten).
*Status: SOLID.*

**D2 ★★ „Was am Modell ändern": von Hook zu konkretem Rezept.**
Der Hook nennt schon „firm capacity to pin prices; flagging unreliable cells; perturbation only where
needed". Wir konkretisieren: (i) Perturbations-Swing-Flag, (ii) RC dort als untere Schranke lesen,
(iii) nur geflaggte Techs bisektieren; ~70–88 % der Fälle sind ohnehin exakt.
*Status: SOLID. Quelle: `docs/rc_interpretability_status_DE.md` (§4).*

**D3 ★ Unbehebbarkeit ehrlich benennen.**
Der exakte Punktschätzer ist an degenerierten Knoten aus *einem* Solve prinzipiell nicht holbar
(Konvexitäts-Argument); die Bisektion bleibt die einzige entartungs-immune Wahrheit. Das ist eine
Grenze des Ansatzes, kein Bug — gute, ehrliche Discussion-Aussage.
*Status: SOLID.*

---

## E) Framework (§3.2) & Conclusion (§7)

**E1 ★ Framework `sec:crystal-ball` mit konkreten Zahlen füllen.**
28 Knoten, Snapshot-Jahr 2050, 10 typische Stunden, 68/5/5 Techs, Import-Insel-Struktur
(ES über die Pyrenäen, `FR→ES`-cap 0) — Letzteres motiviert die Part-2-Degeneration direkt.
*Status: SOLID. Quelle: runC `system.json`, `RC_report/a6_congestion.py`.*

**E2 ★ Conclusion/Outlook: ein Satz pro Befund.**
RC skaliert für die Mehrheit der CB-Tech-Knoten; die Grenze sind import-isolierte Knappheits-Knoten;
Future Work = Flag + gezielte Bisektion. *Status: SOLID.*

---

## Was BEWUSST nicht aufnehmen / Abwägungen
- **scipy-Toy (`toy_lp3.py`)**: laut Entwurf bewusst draußen. Nur der *ZEN-garden*-Reproducer (A5)
  käme in Frage, und auch der nur, wenn ein 3. Modell die Erzählung nicht überlädt.
- **Solver-Abhängigkeit (SE PV 166 vs 0)**: steht schon in `app:problem3` — A4 *erweitert* es
  (Swing als Detektor), ersetzt es nicht.
- **Transport marginal-vs-finite**: in §5.1 bereits ausführlich — A3/C1 sind das *Conversion/Preis*-
  Pendant, klar als Anschluss formulieren, nicht doppeln.
