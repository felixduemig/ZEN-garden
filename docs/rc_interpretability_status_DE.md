# RC-Interpretierbarkeit im Crystal Ball: validierte Fakten, Thesen, offene Lücken

*Stand 2026-06-23. Trennt strikt, **was gegen Daten/Re-Solves belegt ist** (§1), **was gut
gestützte These bleibt** (§2), **welche Lücken offen sind** (§3) und **ob es Hoffnung gibt**
(§4). Quellen: `docs/rc_crystalball_conversion_failure.md`,
`docs/rc_scarcity_reproducer_DE.md`, Skripte `_rc_analysis/*.py`, Outputs
`outputs_CB_overnight/*`.*

---

## 1. Harte, validierte Fakten (gegen Daten oder Re-Solves geprüft)

**F1 — Die RC-Arithmetik ist korrekt.** Die operative RC wird aus den gespeicherten nativen
Dualen **exakt** reproduziert (`a3_repro2.py`); das native Pro-Typ-Schritt-Dual enthält die
Cluster-Dauer bereits. Kein Gewichtungs-/Skalierungs-/Fix-Opex-Bug.
*Beleg: numerische Reproduktion = berichtete CSV-Werte.*

**F2 — Die Carrier-Behandlung ist korrekt.** `ν` ist aus den Knotenpreisen `λ`
**maschinengenau** rekonstruierbar (max |Δ| = 0,0) für alle vier Techs, inkl. Elektrolyse
(`ν = max(0, λ_H2 − 1,901·λ_elec − dur·var)`). *Beleg: `a4_nu_from_lambda.py`.*

**F3 — Vollständigkeit, kein Kapazitäts-Leak.** CB ist ein reines LP (keine Binärvariablen,
kein On/Off), die Kapazitätslimit-Duale sind 0 (slack), und das Lifetime-Dual = operativer
Netto-Wert für nuclear (lifetime-RC == operativ-RC). Die operative Rekonstruktion verliert
keinen Faktor. *Beleg: `dual_dict.h5`, `system.json`.*

**F4 — Die CB-Validierung schlägt fehl (auf der Platte).** Bei der rekonstruierten
Break-even-capex bauen nuclear@ES und electrolysis@FI **exakt 0,000000e+00** — sowohl bei
op_A als auch op_B. PV@CZ (clean) und wind@FR **bauen** (PASS).
*Beleg: `outputs_CB_overnight/validate_20260623-011718` in voller Präzision gelesen.*

**F5 — ES ist ein gesättigter Engpass-Vertex.** In der dominanten Wert-Stunde sind **alle 6**
ES-Erzeuger an der Verfügbarkeits-Obergrenze, Importe verstopft (`FR→ES`-Leitung Kapazität
**0**, `PT→ES` am Limit), shed = 0; der Preis **0,179** liegt zwischen NGT (0,130) und
biomass (0,229) und entspricht **keinem** laufenden Aggregat. *Beleg: `a6,a7`.*

**F6 — Der Engpass-Reproducer überschätzt die Nähe in echtem ZEN-garden.** Minimal-Datensatz
`rc_scarcity_demo`, deine RC-Settings, echte `_compute_rc_capex_equivalent`: sobald der
lokale Peaker marginal ist, ISL-Preis = 50, baseload-RC-ratio = **0,2484**. Der capex-Sweep
zeigt: bei der rekonstruierten Break-even-capex (2255) baut baseload nur **0,01 GW** und
springt erst bei ~700–760 auf **12 GW** — wahrer Break-even ratio **0,75**.
*Beleg: `demo_island.py`, frische Re-Solves.*

**F7 — Der Solver „schluckt" Zubauten erst unter ~1e-6 GW.** Bei bewusst winzigem optimalem
Zubau realisiert Gurobi 1e-2, 1e-3, **1e-5 GW ziffergenau**; erst **1e-7 GW** wird auf 0
gekippt (Feasibility-Toleranz). *Beleg: `test_tiny_build.py`.*

**F8 — Perturbations-Sensitivität trennt die Klassen sauber.** RC-Swing clean→pert:
nuclear **9,4 pp**, electrolysis **5,0 pp** (entartet) vs. PV **0,38 pp**, wind **0,09 pp**
(robust). *Beleg: runA/B/C.*

**F9 — Die Entartung ist knoten-spezifisch.** Nuclear **baut** an 8 Knoten (BE,BG,CH,DE,HU,
RO,SI,SK); hat eine **robuste** buildable-RC an FR (Swing 0,06 pp); entartet nur an
import-isolierten Knoten (ES,FI,SE,UK,NL). *Beleg: CB-Conversion-CSVs.*

---

## 2. Thesen (gut gestützt, aber nicht zu 100 % geschlossen)

**T1 — Mechanismus = marginal-vs-endlich an einem Knappheits-Vertex.** Die RC liest den
No-Build-Knappheitspreis; ein endlicher Bau neuer *Erzeugung* verdrängt billige Ressourcen,
realisiert also weniger. *Stützung: stark* (Reproducer F6 zeigt es sauber; Konvexitäts-
Argument; gesättigter Vertex F5). Kein numerischer Artefakt (F6 ohne jede Numerik-Schwierigkeit).

**T2 — Aus einem einzigen Solve nicht als Punktschätzer behebbar.** Konvexität ⇒ Marginal ≥
Durchschnitt über `[0,x*]`; die Lücke (Preis-Feedback-Integral) steckt nicht in den
No-Build-Dualen. *Stützung: sehr stark* (mathematisch + Reproducer). Der „CB erfüllt die
Voraussetzungen"-Teil ist der These-Anteil.

**T3 — Die operative RC ist eine *untere Schranke* der wahren Distanz** (für `buildable_rc`
+ `rc_reliable` Conversion). *Stützung: stark* (gilt über alle beobachteten Fälle; folgt aus
Konvexität). **Ausnahme:** Carry-over-Phantome (`ratio_reduction > 1`) — dort ist die RC gar
keine Distanz.

**T4 — Der CB-Nullbau ist *genuin*, nicht numerisch verschluckt.** Argument: op_B senkte den
capex 533 €/kW *unter* den rekonstruierten Break-even (11,7%-Schnitt, 5× die RC) und baute
trotzdem 0; ein so weit jenseits des Break-even liegender Bau wäre GW-groß und damit
nicht schluckbar (F7). *Stützung: stark, aber nicht endgültig* — der definitive Test (CB-
capex-Feingitter-Rerun) ist der verbotene ~11-min-Lauf.

**T5 — Reproducer zeigt die *schwache* Form, CB die *starke*.** Der Reproducer (eindeutiger
Preis über marginalen Peaker) belegt die Konkavitäts-Form: RC = korrekter *marginaler* Wert,
Bau = realer Schimmer (0,01 GW), ±1%-Test *technisch* PASS. CB (entarteter Vertex) zeigt die
stärkere Form: Bau **exakt 0**, ±1%-FAIL. Richtung und Knappheits-Mechanismus sind im
Reproducer hart belegt; die *exakte* „baut 0"-Form von CB ist über F4/F5 + T4 gestützt, aber
nicht im Toy reproduziert (bei eindeutigem Preis entsteht ein Schimmer, kein exaktes 0).

---

## 3. Die verbleibenden Lücken (punktgenau)

**L1 — Die marginal-vs-endlich-Lücke an selbst-kannibalisierenden / Knappheits-Knoten.**
*Kern-Lücke.* Die operative RC ist eine Marginalgröße; wo der endliche Eintritt den eigenen
Carrier-Preis bewegt (Grundlast an Import-Inseln, flexible Last an Abregelungs-Knoten),
überschätzt sie die ökonomische Nähe (sie ist nur eine untere Schranke). Betrifft
nuclear/electrolysis an ES/FI/SE/UK/NL.

**L2 — Dual-Nicht-Eindeutigkeit / Vertex-Auswahl an entarteten Punkten.** Welches gültige
Dual der Solver meldet, verschiebt die RC (clean vs. pert, F8). Die Perturbation schiebt
Richtung realisierbares Ende, ist aber **kein Theorem** (keine Garantie auf den exakten Vertex).

**L3 — Sub-Toleranz-Bau an Grenzfällen (deine Hypothese).** Liegt der *wahre* Break-even
einer Tech *genau* am getesteten capex, ist der optimale Bau dort ~0 und kann unter ~1e-6 GW
fallen → **falscher FAIL** im ±1%-Test (F7). Betrifft Tech, deren RC eigentlich *korrekt* ist.

**L4 — Interpretations-/Nutzungs-Lücke.** Die Closeness-Pipeline/Heatmaps lesen die RC als
Punkt­schätzer der Bau-Distanz, obwohl sie eine Marginalgröße / untere Schranke ist. Für die
entarteten Knoten ist das Ranking zu optimistisch (nuclear@ES wirkt „2,3 % entfernt", ist
aber > 11,8 %).

---

## 4. Gibt es Hoffnung, das aufzulösen?

**Den exakten Punktschätzer aus einem Solve: nein (bewiesen, T2).** Die einzige
entartungs-immune Wahrheit ist der endliche Re-Solve (Bisektion). Das ist eine *Grenze des
Ansatzes*, kein Bug.

**Eine verlässliche Arbeits-Pipeline: ja, klar machbar.** Vier Schritte, alle umsetzbar:

1. **Rechnen wie bisher.** Die operative RC ist korrekt (F1–F3) und für die Mehrheit der
   Fälle (Price-Taker, gut vernetzte Knoten — ~70–88 %) **exakt** (PV/wind PASS; nuclear@FR
   robust). Da ist keine Lücke.
2. **Entartete/selbst-kannibalisierende Techs flaggen.** Robust per **Perturbations-Swing**
   (`|RC_clean − RC_pert| > ~1 pp` → unzuverlässig; F8 trennt sauber) und/oder
   Knappheits-Heuristik (Wert konzentriert in Stunden, in denen der Referenz-Knoten gesättigt
   und import-verstopft ist; F5).
3. **Geflaggte RCs als *untere Schranke* lesen** (`rc_is_lower_bound`), nicht als Punkt­schätzer
   (T3) — und im Closeness-Ranking entsprechend kennzeichnen statt zu vertrauen (schließt L4).
4. **Nur die geflaggten Techs bisektieren** (capex-Override + Re-Solve) für die wahre Distanz.
   Das ist der einzige exakte Schritt — aber gezielt, nicht flächendeckend.

**Gegen L3 zusätzlich:** bei der Validierung die **rohe** Baumenge prüfen (mit physikalisch
sinnvoller Schwelle, z. B. 1e-3 GW), nicht 0/1 über einer zu engen Toleranz — fängt
Grenzfall-Falsch-FAILs ab.

**Bilanz:** Die *exakte* Distanz an entarteten Knoten ist aus einem Solve prinzipiell nicht
erreichbar. Die *Interpretierbarkeit* ist aber vollständig wiederherstellbar: die RC bleibt
ein korrekter, billiger Screening-Wert mit **bekanntem, detektierbarem Versagensmodus** und
einem gezielten exakten Check (Bisektion) für die wenigen geflaggten Fälle. Die offene Arbeit
ist Engineering (Flag + Bisektions-Hook in `postprocess.py` / der Closeness-Pipeline), keine
ungelöste Theorie.
