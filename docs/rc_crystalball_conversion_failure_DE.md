# Warum die operative Reduced-Cost-Rekonstruktion die Bau-Distanz für manche Crystal-Ball-Conversion-Techs UNTERSCHÄTZT

*Root-Cause-Untersuchung, 2026-06-23. Daten: `outputs_CB_overnight/{runA,runB,runC}` (CB-
Snapshot, 28 Knoten, 1 Jahr, 10 typische Stunden, reines LP, Gurobi Barrier+Crossover) und
die sauberen Ground-Truth-Re-Solves in `outputs_CB_overnight/validate_*`. Reproduktions-
Skripte: `_rc_analysis/a1..a10_*.py`, `_rc_analysis/toy_lp3.py`. Es wurden keine neuen
CB-Läufe gestartet.*

---

## 0. Verdikt (TL;DR)

- **Es ist kein Arithmetik-, Carrier- oder Vollständigkeits-Bug.** Die Leads 1 (Carrier-/
  Conversion-Behandlung), 2 (eine fehlende wertbildende Kapazitäts-Constraint) und 3
  (Gewichtung/Skalierung) werden unten jeweils gegen die gespeicherten Duale widerlegt. Die
  Rekonstruktion ist eine *getreue* Bewertung des Kapazitätswerts zu den No-Build-Dispatch-
  Preisen — `ν` wird maschinengenau aus den Knotenpreisen `λ` reproduziert, inklusive des
  Wasserstoff-Referenz-Carriers der Elektrolyse, und die berichtete RC wird exakt aus
  `Σ mₜ·νₜ / scaling` reproduziert.
- **Das Versagen ist eine Eigenschaft des LP, nicht des Codes: ein entarteter
  („Knappheits"-)No-Build-Vertex, an dem der Dispatch-Preis, zu dem die Technologie bewertet
  wird, der *Nachfrage-Entlastungs*-Preis ist, während ein endlicher Bau einer neuen
  *Angebots*-Technologie nur den deutlich niedrigeren *Angebots-Verdrängungs*-Wert
  realisiert.** Die rekonstruierte RC ist eine First-Order-Größe (marginal), abgelesen an
  dieser Messerschneide; die wahre Bau-Schwelle ist eine Größe des endlichen Schritts. Beide
  unterscheiden sich um die Selbst-Kannibalisierung, die der erste endliche Bau auslöst — und
  diese ist **für jeden einzelnen Solve unsichtbar**. Das sind die Leads **4 (berichtetes
  Dual ≠ Rechtsableitung) und 5 (marginal-vs-endlich)**, die zwei Seiten desselben Knicks in
  der Kosten-über-Kapazität-Funktion sind.
- **Die frühere „marginal-vs-endlich"-Intuition ist BESTÄTIGT und hat jetzt eine rigorose
  KKT-/LP-Sensitivitäts-Begründung sowie ein minimales Gegenbeispiel** (`toy_lp3.py`): ein
  6-Variablen-LP, in dem der rekonstruierte Break-even beweisbar 9× der wahre ist und das LP
  *exakt null* baut, knapp unterhalb des rekonstruierten Break-even — was das CB-
  Validierungs-FAIL reproduziert.
- **Verdikt zur Behebbarkeit: Das Signal ist aus einem einzigen Solve intrinsisch nicht
  rekonstruierbar für diese Techs.** Jede Single-Solve-Dual-Schätzung ist eine *obere
  Schranke* des realisierten Werts (⇒ eine *untere Schranke* der Distanz), weil
  Kosten-über-Kapazität konvex ist und die Duale nur die steilste (No-Build-)Steigung sehen.
  Eine Korrekturformel kann nicht existieren; die ehrliche Lösung ist ein
  **Entartungs-/Unzuverlässigkeits-Flag** (Perturbations-Sensitivität, die das Multi-Run-
  Setup bereits liefert) plus ein **endlicher Bisektions-Re-Solve** für geflaggte Techs.
  Konkretes Flag + Code in §7.

---

## 1. Die Größenordnung der Überbewertung (mit den gespeicherten Zahlen)

`capacity_addition_analysis_conversion.csv`, vier Diagnose-Techs, alle `value = 0`
(ungebaut), `case = buildable_rc`, `rc_reliable = True`. RC in €/kW; ratio = RC/capex.
In Run C ist lifetime-RC == operational-RC für beide versagenden Techs (kein Kapazitäts-
Variablen-Leak — siehe §3), also ist das **nicht** die Entartung, für die die operative
Spalte gebaut wurde.

| Tech | Knoten | capex €/kW | RC_clean (Run C) | RC_pert (Run B) | Ground-Truth ±1 % | **wahre RC (untere Schranke)** | Clean-Überbewertung |
|---|---|---:|---:|---:|---|---:|---:|
| **nuclear** | ES | 5578.7 | 125.99 (**2.26 %**) | 652.54 (11.70 %) | baut 0 selbst bei Run B → **FAIL** | **> 659 €/kW (> 11.81 %)** | **> 533 €/kW (> 9.5 % des capex)** |
| **electrolysis** | FI | 576.4 | 56.13 (**9.74 %**) | 85.14 (14.77 %) | baut 0 selbst bei Run B → **FAIL** | **> 86 €/kW (> 14.92 %)** | **> 30 €/kW (> 5.2 % des capex)** |
| photovoltaics | CZ | 317.0 | 15.06 (4.75 %) | 13.86 (4.37 %) | baut bei 4.75 % → **PASS (clean)** | ≈ 14 €/kW (4.4 %) | ≈ 0 |
| wind_offshore | FR | 1926.3 | 215.39 (11.18 %) | 213.61 (11.09 %) | baut bei 11.1 % → **PASS** | ≈ 216 €/kW (11.2 %) | ≈ 0 |

Die untere Schranke der wahren RC ist der harte Fakt auf der Platte: beim Run-B-Override-
capex = capex·(1 − 1.01·ratio) — **4919.6 €/kW** für nuclear, **490.4 €/kW** für
electrolysis — baut der saubere Re-Solve **0** (`validate_20260623-011718/c06`, `…/c04`,
`built=0.0000`). Also liegt der wahre Break-even-capex darunter, d. h. die wahre RC
übersteigt diese Werte. Die Validierung liefert nur eine einseitige Eingrenzung (ein engeres
oberes Ende bräuchte eine tiefere Bisektion, die absichtlich nicht auf der Platte liegt); sie
beweist bereits, dass die Rekonstruktion zuversichtlich falsch ist — sie meldet nuclear als
**2.26 % von der Wirtschaftlichkeit entfernt, während es mindestens 11.8 % entfernt ist**.

**Die Richtung ist einheitlich:** jede Rekonstruktion (lifetime oder operativ, clean oder
perturbiert) **unterschätzt die Distanz / überschätzt den Wert**. Der saubere Run C ist die
*schlimmste* Überbewertung, also ist die Perturbation nicht die Ursache (sie schiebt den Wert
*Richtung* Wahrheit).

---

## 2. Leads 1–3 sind widerlegt (reine Daten-Checks)

### Lead 3 — Arithmetik / Gewichtung / Skalierung: **KORREKT** (`a3_repro2.py`)
Das native Kapazitätsfaktor-Dual ist an den **10 typischen Operations-Schritten** gespeichert
(20720 = 2072 (tech,node) × 10), und `Results.get_dual` expandiert es auf 8760. Die
Rekonstruktion summiert über die **nativen 10 Schritte ohne zusätzliche Dauer-Gewichtung**,
weil das Dual pro Typ-Schritt seine Cluster-Dauer bereits enthält (das Energiekosten-Ziel ist
dauer-gewichtet, also ist das Gurobi-Dual der Pro-Schritt-Constraint der *jährliche*
Grenzwert). Reproduktion der berichteten operativen Ratio aus den gespeicherten nativen
Dualen:

```
RC_op_ratio = 1 − (Σₜ mₜ·νₜ − opex_fixed·δ) / (af·δ · capex)
```

stimmt **exakt** mit der CSV für alle vier Techs überein (z. B. nuclear ES: V = 391.51, ratio
+0.02258 vs berichtet 0.022584). Eine explizite Dauer-Gewichtung ergibt Unsinn (ratio ≈
−1627). ⇒ **Kein Gewichtungs-/Skalierungs-/Fix-Opex-Bug.**

### Lead 1 — Carrier / Referenz-Carrier-Behandlung: **KORREKT** (`a4_nu_from_lambda.py`)
Die unabhängige Rekonstruktion von `ν` aus den Knotenbilanz-Preisen `λ`:

```
νₜ = max(0, λ_ref,node,t − Σ_in α_in·λ_in,node,t − durₜ·var_opex)
```

reproduziert das gespeicherte Kapazitätsfaktor-Dual **maschinengenau (max |Δ| = 0.0)** für
alle vier, inklusive **Elektrolyse** (`ref = hydrogen`, Input Strom, α = 1.901):
`νₜ = max(0, λ_H2 − 1.901·λ_elec − dur·var)`. Der Wasserstoff-seitige Wert und die
Strom-Input-Kosten werden korrekt verrechnet. ⇒ **Kein Carrier-/Conversion-Factor-Mismatch.**

### Lead 2 — Vollständigkeit (eine zweite wertbildende Kapazitäts-Constraint): **KEINE bindet**
- Das Modell ist ein **reines LP**: keine On/Off-Binärvariablen, kein
  `constraint_technology_on_off`, keine Reserve-/Firm-Capacity-/Kapazitätsmarkt-Constraints
  existieren (`a-checks`; var_dict hat keine Binärvariablen). ⇒ der **Min-Load-/Must-Run-
  Faktor fehlt**.
- `constraint_technology_capacity_limit_not_reached`-Dual = **0** für nuclear ES (Kapazität
  0 ≪ Ceiling 7.163), `…_reached` hat keine Zeile. Das Kapazitätslimit ist **slack**, trägt
  also keinen Wert. (Elektrolyse-Ceiling ist `inf`.) PV und wind haben ebenfalls endliche
  Ceilings und **bestehen**, also ist ein bindendes Limit ohnehin nicht der Splitter.
- `constraint_technology_lifetime`-Dual μ = −292.6 (nuclear) entspricht dem operativen
  Netto-Wert 292.8 → **kein Kapazitäts-Variablen-Leak** (`c̄(capacity) = 0`); lifetime-RC ==
  operational-RC in Run C. Der Vollständigkeitssatz hält; die operative Rekonstruktion
  verliert keinen echten Faktor.

⇒ Leads 1–3 geschlossen. Die Rekonstruktion ist korrekt **gegeben die Preise**; die Preise
sind das Problem.

---

## 3. Der Mechanismus (KKT / LP-Sensitivität), exakt verortet

### 3.1 Der Dispatch sitzt an einem entarteten „Knappheits"-Vertex
Am dominanten Wert-Schritt von nuclear (ES, Schritt 0, der 260 von den gesamt 391 `Σ mₜ·νₜ`
beiträgt) ist der gespeicherte Dispatch (`a7_scarcity.py`):

```
ES Strom, Schritt 0 (Preis λ = 0.179 €/kWh, shed = 0, Importe = 0, FR→ES Leitungs-cap = 0):
  wind_onshore  13.17  (mc 0.0006)  at_cap=True
  reservoir_hyd  6.61  (mc 0.0014)  at_cap=True
  photovoltaics  2.54  (mc 0.0000)  at_cap=True
  biomass_plant  2.14  (mc 0.2294)  at_cap=True
  run-of-river   0.84  (mc 0.0020)  at_cap=True
  natural_gas    0.53  (mc 0.1296)  at_cap=True     ← alle sechs AN Verfügbarkeits-cap
```

**Jeder lokale Erzeuger ist an seiner Verfügbarkeits-Obergrenze, die Importleitungen sind an
ihrem Limit, und die Nachfrage wird mit null Lastabwurf gedeckt.** Die Anzahl bindender
Constraints übersteigt das, was einen eindeutigen Preis fixiert: das ist ein primal-
entarteter Vertex. Der berichtete Preis **0.179 entspricht den Grenzkosten keines laufenden
Aggregats** (er liegt zwischen NGT 0.130 und biomass 0.229) — er ist eine **Knappheits-/
Engpass-Rente**, der Wert der Entlastung der *Nachfrage*, nicht die Kosten eines marginalen
Erzeugers mit Reserve.

### 3.2 Warum ein endlicher Bau weniger realisiert als der berichtete Preis (das KKT-Argument)
Schreibe die optimalen Dispatch-Kosten als Funktion der Kandidaten-Kapazität `x`:
`C(x) = annuity(capex)·x + D(x)`, wobei `D(x)` die optimalen Dispatch-Kosten bei `x`
verfügbaren Einheiten sind. `D` ist **konvex und fallend** (mehr günstige Firm-Capacity
schadet nie), also ist seine Rechtsableitung `D′(0⁺)` die *größte* (am wenigsten negative)
Steigung:

- Die operative Rekonstruktion setzt den Kapazitätswert auf `−D′`, ausgewertet mit dem
  gespeicherten No-Build-Dual `λ = 0.179` — der **Nachfrage-Entlastungs**-Wert (linke/steilste
  Steigung, `p_hi`).
- Ein endlicher Bau von *Angebot* verdrängt die **günstigsten abregelbaren laufenden
  Ressourcen**, realisiert also den **Angebots-Verdrängungs**-Wert (`p_lo`), der an diesem
  Vertex strikt kleiner ist. Das optimale Dual ist **nicht-eindeutig auf `[p_lo, p_hi]`**; die
  Rekonstruktion liest `p_hi`, der Bau realisiert `p_lo`.

Weil `D` konvex ist, ist **jedes Single-Solve-Dual `≥` dem Durchschnittswert über `[0, x*]`**,
also ist die Rekonstruktion eine obere Schranke des realisierbaren Werts und die berichtete RC
eine *untere Schranke* der wahren Distanz — genau das beobachtete einseitige Versagen. Die
Lücke ist die **Selbst-Kannibalisierung**: während `x` wächst, flutet der Kandidat seine
eigenen Wert-Stunden und der Preis kollabiert Richtung `p_lo` (und darunter). Das LP baut
deshalb **exakt 0** knapp unterhalb des rekonstruierten Break-even (kein ε), weil die *erste*
infinitesimale Einheit bereits auf dem unteren Ast des Knicks lebt.

### 3.3 Derselbe Mechanismus, zwei Carrier-Seiten
- **nuclear ES — Output-seitige Knappheit.** Verkauft Strom in einen import-isolierten, voll
  gesättigten Knoten; sein Wert ist die Knappheitsrente (0.179, das 2.4-Fache des ~0.07-
  Kontinentalpreises, über den Kosten der eigenen NGT). Der Bau entlastet die Knappheit direkt
  → Preis kollabiert auf den günstigen verdrängten Stack (wind/hydro/PV ≈ 0, NGT 0.13). 67 %
  seines Werts liegen in diesem einen Messerschneide-Schritt.
- **electrolysis FI — Input-seitiger Überschuss** (`a10_fingerprint.py`). Eine flexible *Last*:
  Marge `= λ_H2 − 1.901·λ_elec`. Ihr Wert konzentriert sich auf Schritt 8, wo `λ_elec = 0.0014`
  (im Wesentlichen **gratis, Abregelungs-Regime-Strom** — der entartete `λ≈0`-Fall) und
  `λ_H2 = 0.069`, Marge +0.067. Ihr Bau bietet FIs Beinahe-Gratis-Strom hoch → `λ_elec` steigt
  → die Marge kollabiert (und der zusätzliche H₂ drückt `λ_H2`). Selbst-Kannibalisierung auf
  dem *Input*. Derselbe Knick, spiegelverkehrt.

### 3.4 Warum PV und wind BESTEHEN
PV/wind sind **variable Price-Taker**. Beim getesteten Schnitt baut das LP eine *kleine* Menge
(PV 0.32 GW, wind 10.6 GW) in tiefen Märkten, also ist die Wertfunktion über den ausgelösten
Bau lokal linear → marginal ≈ endlich → die RC ist exakt. (Sie sitzen *auch* an gesättigten
Vertizes — „all-at-cap" ist mit 10 typischen Stunden üblich — aber ihr ausgelöster Bau ist zu
klein, um den Preis zu bewegen.) Der entscheidende Unterschied ist **Bau-Größe /
Kannibalisierungs-Tiefe**, nicht der Vertex-Typ: nuclear ist ein *Price-Maker* (ein ~6 GW
Grundlast-Eintreter in einen dünnen isolierten Knoten), PV/wind sind Price-Taker.

### 3.5 Entartungs-Fingerabdruck (der praktische Diskriminator)
Die Perturbations-Sensitivität der Rekonstruktion trennt die beiden Klassen sauber
(`|RC_runB − RC_runC|`, in Prozentpunkten des capex):

| Tech | clean→pert Swing | zuverlässig? |
|---|---:|---|
| nuclear ES | **9.44 pp** | NEIN (entartet) |
| electrolysis FI | **5.03 pp** | NEIN (entartet) |
| photovoltaics CZ | 0.38 pp | ja |
| wind_offshore FR | 0.09 pp | ja |

Ein robustes Dual ist perturbations-invariant; nuclear/electrolysis schwanken um 5–9 pp, weil
ihr Wert auf dem entarteten Ast reitet (und weil nuclear an einer Messerschneide sitzt — seine
Netto-Marge beträgt nur 6.8 eines Brutto-Werts von 392, also wird eine 7 %-Dual-Wackelei zu
einem 9-pp-RC-Swing).

---

## 4. Das minimale Gegenbeispiel (`_rc_analysis/toy_lp3.py`, Sub-Sekunden-scipy-LP)

1 Knoten, 2 identische Stunden. Nachfrage je 100. Bestandsanlagen: **G1** cap 100 Kosten 10
(günstig), **G2** cap 100 Kosten 50 (Peaker). Kandidat **C**: Grundlast Kosten 5, Investkosten
`I`.

```
NO-BUILD: g1 = 100,100 (an cap)   g2 = 0,0 (idle)   → ENTARTETER Vertex
Preis λ ist NICHT-EINDEUTIG auf [10, 50]:
   Nachfrage+ε → λ = 50  (G2-Kosten = NACHFRAGE-ENTLASTUNGS-Wert, das Dual, das der Knappheits-Solve meldet)
   Nachfrage−ε → λ = 10  (G1-Kosten = ANGEBOTS-VERDRÄNGUNGS-Wert, die Rechtsableitung)

operative RC liest λ = 50 → rekonstruierter Break-even I* = 2·(50−5) = 90
WAHRER Break-even (endlicher Re-Solve / Bisektion)     =  10   (C verdrängt günstiges G1, nicht idle G2)
                                              ÜBERBEWERTUNG = 9×
Bei I = 89 (knapp unter der Rekonstruktion): gebaute Kapazität = 0.0000  → KEIN BAU  (= CB FAIL)
```

Das reproduziert jedes qualitative Merkmal des CB-Versagens: einen entarteten No-Build-Vertex,
ein Preis-Intervall, eine Rekonstruktion, die das hohe (Nachfrage-Entlastungs-)Ende liest,
einen wahren Wert am niedrigen (Angebots-Verdrängungs-)Ende und einen Bau von **exakt null**
unterhalb des rekonstruierten Break-even. Es zeigt auch, dass die Überbewertung *kein* Solver-
Artefakt ist, das man wegperturbieren kann: wenn die Knappheitsstruktur das hohe Ende robust
fixiert (wie ES über die Läufe A/B/C — der ES-Schritt-0-Preis ist **0.17916 / 0.17915 /
0.17920**, perturbations-invariant), bewegt keine RHS-Perturbation den dominanten Term, also
unterschießt selbst Run B.

---

## 5. Bestätigung / Widerlegung der früheren „marginal-vs-endlich"-These

**BESTÄTIGT im Kern, im Mechanismus geschärft.** Die frühere Formulierung („endliche Bauten
bewegen Preise") war unvollständig: eine *glatte* Preissteigung würde das LP trotzdem ein ε
bauen und den ±1 %-Bau-Test bestehen lassen. Das beobachtete Verhalten ist ein Bau von **exakt
0**, was einen **Knick** (unstetige Ableitung) bei `x = 0` erfordert, d. h. einen *entarteten*
No-Build-Vertex, an dem die preissetzende Ressource bei Null-Menge liegt / der Knoten gesättigt
ist. Die präzise Aussage lautet also:

> Die rekonstruierte RC ist der Grenzwert der ersten Einheit, ausgewertet am **oberen Ast**
> eines Knicks in Kosten-über-Kapazität (das Nachfrage-Entlastungs-Dual an einem entarteten
> Knappheits-Vertex). Die Bau-Schwelle ist der Wert des endlichen Schritts am **unteren Ast**
> (Angebots-Verdrängung, dann das Abwandern der Residual-Angebotskurve). Sie unterscheiden
> sich um die Selbst-Kannibalisierungs-Breite des Knicks, die für hoch-volllaststündige /
> preissetzende Eintreter (nuclear Grundlast, electrolysis flexible Last) groß und für
> kleinbauende Price-Taker (PV, wind) ≈ 0 ist.

Lead 4 (berichtetes Dual ≠ Rechtsableitung) und Lead 5 (marginal vs endlich) sind die
duale/primale Sicht auf diesen einen Knick. Nach Beitrag gerankt: die **endliche
Schritt-Konkavität ist die ganze Lücke**; die No-Build-Dual-Entartung ist ihre Signatur auf
infinitesimaler Skala (und der Grund, warum der Bau 0 statt ε ist).

---

## 6. Ist es behebbar? — Beweis, dass es das **nicht** ist, aus einem einzigen Solve

Sei `V(x) = −D(x)` der (konkave, steigende) realisierbare Wert von `x` Einheiten. Der wahre
Break-even-capex löst `annuity·capex* = V(x*)/x*`, hängt also vom **Durchschnitts**-Wert über
`[0, x*]` ab. Ein einzelner Solve liefert nur Duale bei `x = 0`, die `V′(0⁺)` ergeben
(bestenfalls die Rechtsableitung; die Rekonstruktion liest tatsächlich `V′(0⁻) ≥ V′(0⁺)`). Aus
Konkavität folgt `V′(0⁺) ≥ V(x*)/x*` für alle `x* > 0`, mit **strikter** Ungleichung, sobald
die Wertfunktion über `[0, x*]` gekrümmt ist — genau der selbst-kannibalisierende Fall. Daher:

> **Jede Single-Solve-Reduced-Cost-Rekonstruktion überschätzt den realisierbaren Wert (⇒
> unterschätzt die Distanz), sobald der endliche Eintritt der Technologie ihre eigenen
> Carrier-Preise bewegt, und die Größe des Fehlers (das Integral der Konkavität über
> `[0, x*]`) ist keine Funktion der `x = 0`-Duale.** Keine Umgewichtung der `x = 0`-Duale kann
> ihn rekonstruieren.

Selbst die *exakte Rechtsableitung* `V′(0⁺)` (das Beste, was ein einzelner Solve liefern
könnte, gewonnen durch einen zweiten lexikografischen Dual-Solve) würde nur die obere Schranke
verengen, nicht `V(x*)/x*` erreichen. ⇒ **Eine Korrekturformel ist unmöglich; der endliche
Re-Solve (Bisektion) ist die einzige entartungs-immune Wahrheit.** Das minimale Gegenbeispiel
in §4 ist der Zeuge.

---

## 7. Die ehrliche Lösung: Detect-and-Abstain, dann Bisektion

Da keine Single-Solve-Korrektur existiert, ist das Deliverable ein **Zuverlässigkeits-Flag**,
das diese RCs als *untere Schranken der Distanz* markiert (keine Punktschätzungen) und sie an
einen Bisektions-Re-Solve weiterleitet. Zwei komplementäre Signale, beide bereits berechenbar:

**(a) Perturbations-Sensitivitäts-Flag (robust, braucht die 2 Solves, die der Harness ohnehin
macht).** Markiere eine Conversion-RC als `rc_unreliable_degenerate`, wenn sie sich zwischen
dem sauberen und dem RHS-perturbierten Solve um mehr als eine Toleranz bewegt:

```python
# post-hoc über runC (clean) und runB (rhs-perturbiert) Conversion-CSVs
RC_DEGEN_TOL = 0.01            # 1 pp des capex
merged = clean.merge(pert, on=["set_technologies","set_location"], suffixes=("_c","_p"))
swing = (merged["ratio_reduction_operational_p"] - merged["ratio_reduction_operational_c"]).abs()
merged["rc_unreliable_degenerate"] = swing > RC_DEGEN_TOL   # nuclear 0.094, electro 0.050 → True
                                                            # PV 0.004, wind 0.001          → False
```

Das trennt die vier Fälle sauber (§3.5). Die berichtete RC (und besonders die kleinere von
clean/perturbiert) ist dann als **„Distanz ≥ dies"** zu lesen, und der wahre Wert per
Bisektion am Override-capex zu gewinnen.

**(b) Single-Solve-Knappheits-Konzentrations-Heuristik (ein günstigerer Vorfilter).** Markiere,
wenn ein großer Anteil von `Σ mₜ·νₜ` aus Stunden stammt, in denen der Referenz-Carrier-Knoten
*gesättigt* ist (alle lokalen Anbieter dieses Carriers an ihrer Verfügbarkeits-Obergrenze
**und** Netto-Import-Spielraum ≈ 0, also ein isolierter/verstopfter Knappheits-Vertex), oder,
für input-konsumierende Techs, in denen der Input-Preis im Beinahe-Null-Überschuss-Regime
liegt. Das ist eine notwendige Bedingung für den Knick; es über-flaggt (PVs gesättigte Stunden
sind harmlos), muss also mit einem Bau-Größen-Test kombiniert werden — daher ist (a) als
operatives Flag vorzuziehen.

**Empfohlene Code-Änderung** in `save_capacity_addition_classified`
(`postprocess.py:1446`): füge eine Spalte `rc_is_lower_bound` (Default `False`) hinzu und
setze sie, wenn das Perturbations-Paar verfügbar ist, aus Signal (a); annotiere die
`rc_reliable`-Docs, dass für `buildable_rc`-Conversion-Zeilen mit `rc_is_lower_bound = True`
die RC eine **untere Schranke des capex-Schnitts** ist, zu bestätigen per
`rc_capex_file_override.py`-Bisektion. Keine Änderung an `_compute_rc_capex_equivalent`
gerechtfertigt — sie ist arithmetisch korrekt; die Beschränkung ist informativ, kein Bug.

**Gegen-Check gegen Ground-Truth:** Flag (a) markiert genau die zwei Techs, deren ±1 %-Test
FAILED (nuclear, electrolysis), und gibt die zwei frei, die PASSED (PV, wind). Für die
freigegebenen Techs stimmt die operative RC mit der Validierungs-Schwelle überein (PV clean
4.75 % baut, wind 11.18 % baut). Für die geflaggten Techs bestätigt die bisektierte Wahrheit
(> 11.8 %, > 14.9 %), dass die Rekonstruktion eine untere Schranke war, wie das Flag behauptet.

---

## 8. Reproduktions-Artefakte

| Skript | Zweck |
|---|---|
| `_rc_analysis/a3_repro2.py` | reproduziert berichtete RC exakt aus nativen Dualen (Lead 3) |
| `_rc_analysis/a4_nu_from_lambda.py` | `ν` aus Knotenpreisen `λ`, maschinengenau (Lead 1) |
| `_rc_analysis/a7_scarcity.py` | der gesättigte ES-Schritt-0-Vertex (alle 6 an cap, shed 0) |
| `_rc_analysis/a6_congestion.py` | ES-Import-Engpass (FR→ES cap 0, PT→ES am Limit) |
| `_rc_analysis/a8_run_compare.py`, `a9_*`, Fingerprint `a10_*` | Cross-Run-/Knappheits-Diagnostik |
| `_rc_analysis/toy_lp3.py` | **das minimale Gegenbeispiel (9× Überbewertung, Bau = 0)** |

Gespeicherte CB-Outputs: `outputs_CB_overnight/{runA,runB,runC}/Crystal_Ball`; Ground-Truth:
`outputs_CB_overnight/validate_20260623-011718` (c03–c06) und `…-080711` (PV clean).
