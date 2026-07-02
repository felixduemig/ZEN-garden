# Minimal-Reproducer: die Engpass-Knappheit, die die operative RC überbewertet

*2026-06-23. Ein vollständiges, von Hand nachvollziehbares ZEN-garden-Modell, das mit den
exakten RC-Solver-Settings (Gurobi Method 2 + Crossover 1 + Presolve 0, `use_scaling 0`,
`save_duals`/`save_reduced_costs`) läuft und über die **echte** RC-Rekonstruktion in
`postprocess.py` denselben Fehler zeigt wie nuclear@ES im großen Crystal Ball. Damit ist die
Aussage aus `docs/rc_crystalball_conversion_failure.md` nicht mehr nur Theorie, sondern in
ZEN-garden selbst belegt — und über eine explizite Brücke an den CB-Fall gebunden.*

Artefakte: `_rc_analysis/build_island.py` (Datensatz-Generator), `_rc_analysis/demo_island.py`
(der Nachweis), Datensatz `rc_scarcity_demo/`. Reproduzieren:
`python _rc_analysis/demo_island.py`.

---

## 1. Das Modell (2 Knoten, 1 Leitung, 3 Techs, 4 Stunden, keine TSA)

```
        cheap_gen (Kosten 10, große Bestandskapazität)
            │  Strom
          [MAIN] ───── power_line, FIXE Kapazität 30, KEIN Ausbau ─────► [ISL]
                                                                          │
                              ┌───────────────────────────────────────────┤
                         peaker (Kosten 50, Bestand, läuft nur in Spitze)  │
                         baseload (Kandidat, Kosten 5, ungebaut)  ◄── RC-Tech
                                                                          │
                                                        Nachfrage ISL: [30, 12, 12, 12]
```

ISL wird **nur** über eine Leitung der Kapazität 30 versorgt. In der Spitzenstunde (Schritt 0)
ist die Nachfrage ≥ 30 → die Leitung ist am Limit (Engpass), der lokale `peaker` (teuer)
setzt den Preis. In den Schwachlaststunden (12 < 30) deckt der billige Import alles, Preis 10.
Kein TSA, 4 Stunden — jede Zahl ist von Hand prüfbar.

**1:1-Abbildung des scipy-Gegenbeispiels `toy_lp3.py`:**

| `toy_lp3` | dieses Modell |
|---|---|
| G1 billig, **am Limit** (Kosten 10) | Import über die **verstopfte Leitung** von MAIN (Kosten 10) |
| G2 teuer (Kosten 50) | lokaler `peaker` an ISL (Kosten 50) |
| Kandidat C, am billigsten (Kosten 5) | `baseload` an ISL (Kosten 5), ungebaut |

Kernpunkt wie im Gegenbeispiel: Ein endlicher Bau von `baseload` verdrängt den **billigen
Import** (10), **nicht** den preissetzenden `peaker` (50). Sein realisierter Wert (10−5 = 5
pro Einheit) liegt weit unter der preisbasierten Rekonstruktion (50−5 = 45 pro Einheit).

---

## 2. Der Nachweis (echte ZEN-garden-Läufe)

### A) Referenz — Nachfrage 30.0 (Peaker aus, Preis = Import-Parität 10)
```
ISL-Preis Stunde 0 = 10   |   baseload  RC = 2248 €/kW,  ratio = 0.7495
```
Das ist die **WAHRE** Distanz: baseload verdrängt billige Importe (10), Marge 5 → braucht
einen 75%-capex-Schnitt.

### B) Knappheit — Nachfrage 30.01 (Peaker läuft 0.01 GW, Preis = 50)
```
ISL-Preis Stunde 0 = 50   |   baseload  RC = 745 €/kW,  ratio = 0.2484
```
Die operative RC liest den **Knappheitspreis 50** und meldet, baseload brauche nur einen
25%-Schnitt — sie **überschätzt den Wert um Faktor 3**. (Eine 0,03%-Nachfrageänderung
30.0→30.01 lässt den Peaker antippen, der Preis springt 10→50, die RC fällt 75%→25% — obwohl
sich baseloads echte Ökonomie, die Import-Verdrängung, **nicht** geändert hat.)

### C) Ground Truth — baseload-capex variieren (Nachfrage 30.01), gebaute GW ablesen
```
   capex   gebaut_GW   Anmerkung
  2247.3     0.0100    ±1%-BUILD-Punkt (Rekonstruktion sagt: BAUT)   <-- FAIL: baut ~0
  2262.3     0.0000    ±1%-NOBUILD-Punkt
  1500.0     0.0100
  1000.0     0.0100
   800.0     0.0100    knapp über wahrem Break-even
   760.0     0.0100    ~wahrer Break-even
   700.0    12.0000    unter wahrem Break-even  -> baut voll aus
   500.0    12.0000    tief -> baut voll aus
```

- **Rekonstruierter Break-even:** 3000·(1−0.2484) = **2255 €/kW**.
- **Wahrer Break-even:** 3000·(1−0.7495) = **751 €/kW** (∈ (700, 760), exakt wie Referenz A).
- Bei der rekonstruierten Break-even-capex (2255) baut baseload nur **0.01 GW** (die winzige
  Peaker-Verdrängung) — gegen 12 GW, sobald es wirklich wirtschaftlich ist. Die „BAUT"-Vorhersage
  der RC ist **falsch**.

**Verdikt:** Die operative RC (ratio 0.25) **unterschätzt die wahre Distanz (ratio 0.75) um
Faktor 3** — gerechnet von der echten `_compute_rc_capex_equivalent` auf echten Gurobi-Dualen,
mit deinen RC-Settings. Identische Signatur wie nuclear@ES.

> Robustheit (kein fragiler Knife-Edge): der Sweep über Nachfrage 30.01 / 30.5 / 33 / 40 liefert
> **immer** Preis 50 und ratio 0.2484. Sobald der Peaker marginal ist (irgendein Spitzen-Überschuss
> über die Importkapazität), entsteht die Überbewertung. Nur die *gebaute* Menge am
> Rekonstruktions-Break-even hängt von der Peaker-Menge ab; bei kleinem Spitzen-Überschuss ≈ 0.

---

## 3. Die Brücke zum großen Crystal Ball (nuclear @ ES)

Es ist **dieselbe Transmission-Knappheit**. Belege aus den CB-Dualen (`_rc_analysis/a6,a7`):

| Element | Reproducer (ISL) | Crystal Ball (ES) |
|---|---|---|
| Import-Engpass | `power_line` MAIN→ISL **am Limit** (Fluss 30 = cap 30) | `FR→ES`-Leitung **cap 0**, `PT→ES` **am Limit** (a6) — ES ist Import-Insel (Pyrenäen) |
| billige verdrängbare Quelle | Import @ Kosten 10 | ES-Erneuerbare/Import @ ~0–0.13 |
| preissetzende Knappheits-Ressource | `peaker` @ 50 (marginal) | Knappheitsrente **0.179** > NGT 0.130, kein laufendes Aggregat (a7) |
| Vertex-Signatur | Leitung am Limit, Peaker marginal | **alle 6** ES-Erzeuger an der Verfügbarkeits-Obergrenze, shed 0 (a7) |
| Kandidat | `baseload` (billige Grundlast) | `nuclear` (billige Grundlast) |
| Was der Kandidat verdrängt | billigen Import (10), **nicht** den Peaker (50) | billige Erneuerbare/NGT (~0–0.13), **nicht** die 0.179-Rente |
| Folge | RC-ratio 0.25 statt 0.75 (3×), baut ~0 am Break-even | RC-ratio 2.26% statt > 11.8% (> 5×), **baut 0** am Break-even (Validierung) |

Der einzige Unterschied ist die *Sub-Variante*, wie der hohe Preis zustande kommt:
- **Reproducer:** ein dünn-marginaler teurer Peaker fixiert robust den Preis 50 (lösbar
  ohne Abhängigkeit von Gurobis Vertex-Wahl an einem entarteten Punkt — deshalb als Nachweis
  gewählt).
- **CB ES:** ein voll gesättigter, entarteter Vertex (alle Aggregate am Limit, Importe verstopft),
  an dem Gurobis Crossover robust die hohe Rente 0.179 meldet.

Ökonomisch ist es **identisch**: Der berichtete Preis ist der Wert, eine Einheit *Nachfrage* an
einem engpass-isolierten Knoten zu decken; ein neuer *Erzeuger* verdient aber nur, was er
*verdrängt* — die billigen laufenden Ressourcen. An einem engpass-isolierten Knoten klaffen diese
beiden auseinander, und die operative RC liest die falsche Seite.

---

## 4. Was der Reproducer beweist (und was nicht)

**Beweist:**
1. Der Fehler ist **real in ZEN-garden**, nicht im scipy-Spielzeug — gleiche RC-Settings, gleiche
   `_compute_rc_capex_equivalent`, echte Gurobi-Duale.
2. Er entsteht durch **Transmission-Engpass-Knappheit**, exakt die Konstellation an ES.
3. Er ist **richtungstreu eine untere Schranke**: die RC sagt „mind. 25% senken", wahr sind 75%.
4. Die einzige entartungs-immune Wahrheit ist der **endliche Re-Solve** (der capex-Sweep in C).

**Beweist nicht / Grenzen:** Der Reproducer ist konstruiert (ein dünn-marginaler Peaker). Er
zeigt den *Mechanismus* sauber; die *Größe* der Überbewertung in CB (3×–5×) hängt von der realen
Netz-/Merit-Order-Struktur ab. Er ersetzt nicht die ±1%-Bisektion an konkreten CB-Techs.

---

## 5. Reproduktion

```bash
python _rc_analysis/demo_island.py     # Abschnitte A/B/C oben
python _rc_analysis/sweep_island.py    # Preis/Peaker/RC über mehrere Nachfrage-Niveaus
python _rc_analysis/toy_lp3.py         # das reine scipy-Gegenbeispiel (9×)
```
Datensatz wird nach `rc_scarcity_demo/` geschrieben; Outputs nach `outputs_island/`.
