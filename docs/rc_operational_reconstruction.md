# Reduced-Cost-Interpretierbarkeit: heat_pump vs. PV und die operative RC-Variante

*Untersuchung 2026-06-20/21, Toy-Modelle `5_multiple_time_steps_per_year` (2 Knoten DE/CH)
und `5_multiple_extended_countries` (6 Knoten). Fokus: warum die rekonstruierte Reduced
Cost (RC) für heat_pump nicht interpretierbar ist, wo PV immer stimmt, und wie man es
behebt.*

## TL;DR

- Die berichtete RC `rc_capex_equivalent` wird aus dem **Lifetime-Dual** μ^life rekonstruiert.
  Sie ist **lauf-abhängig** und unterschätzt für heat_pump den nötigen CAPEX-Schnitt (z. B.
  CH y1: RC 1650 statt der wahren ~2089 €/kW) — der Bau „switcht" deutlich früher als die RC
  erwarten lässt.
- **Ursache (beweisbar): Dual-Degeneration.** Die native Reduced Cost der `capacity`-Variable
  leakt in μ^life, sobald `capacity` nicht-basisch ist (ungebaute Tech). Bei PV ist `capacity`
  basisch (gebaut) → kein Leak → RC exakt. Bei heat_pump ist sie nicht-basisch → Leak → RC falsch.
- **Teil-Fix:** eine zweite Spalte `rc_capex_equivalent_operational`, die den Wert aus dem
  **Betriebs-Dual** (Kapazitätsfaktor-Constraint) statt aus μ^life zieht und den
  Kapazitäts-Variablen-Leak per Konstruktion ausschließt. Per **±1%-Build/Nobuild-Test
  bestätigt** (alle heat_pump-Fälle PASS; die abweichenden Lifetime-Werte FAIL).
- **ABER:** das ist nur *eine* von zwei Degenerationen. Die operative Spalte behebt den
  Kapazitäts-Leak, **nicht** die Degeneration der Dispatch-*Preise* selbst. An preis-entarteten
  Knoten (z. B. viel Gratis-PV) ist die operative RC ohne Perturbation **nachweislich falsch**
  (DE y1: operativ-ohne-Perturbation = 1912.4, per Test widerlegt; nur 2023.4 mit Perturbation
  ist korrekt). **Verlässliches Rezept = Perturbation AN + operative Spalte.**

---

## 1. Beobachtung: der Bau switcht früher als die RC sagt

CAPEX-Sweep für `heat_pump @ CH, Jahr 1` (Original-Toy, CAPEX-Override pro Jahr):

| CAPEX [€/kW] | gebaut [GW] |
|---|---|
| 3600 (Baseline) | 0 |
| 1550 | 0 |
| **1500** | 0.32 ← Switch |
| 1200 | 14.75 |
| 900 | 17.9 |

Der echte Bau-Switch liegt bei **CAPEX ≈ 1500–1525** (→ wahre RC ≈ 2075–2100 €/kW). Die
Lifetime-RC meldete je nach Solve aber 1650 (→ Break-even 1949) oder 2089 — also
**lauf-abhängig** und im 1650-Fall deutlich daneben.

Wenn heat_pump baut, läuft sie mit **Kapazitätsfaktor 0.99 (Grundlast)**; der CH-Wärmepreis
ist flach 0.0239 (= Gasboiler-Grenzkosten), Strom meist gratis (PV-Überschuss). Kein
Knappheits-Spike — der Wert ist reine Brennstoffverdrängung.

## 2. Die RC-Rekonstruktion und der „native-RC-Kollaps"

`capacity_addition` kommt in genau zwei Investitions-Constraints vor:
- `constraint_technology_lifetime`: `capacity[y] − Σ_lifetime capacity_addition = existing` (Wertseite, Dual μ^life)
- `constraint_capacity_coupling`: `capacity_addition − capacity_approximation = 0` (CAPEX-Pfad)

Deren Dual-Beiträge **heben sich exakt auf** → die native Reduced Cost von `capacity_addition`
ist **identisch 0**. Es gibt also keine direkt ablesbare RC; die Rekonstruktion ist Pflicht:

```
rc_capex_equivalent = capex_specific − Σ_pay(−μ^life_y) / scaling
```

Das ist nur exakt, wenn μ^life der eindeutige Grenzwert der Kapazität ist.

## 3. Der strukturelle Unterschied heat_pump vs. PV (Beweis)

Aus den `attributes.json`:

| | reference_carrier | input_carrier | gebaut? |
|---|---|---|---|
| **photovoltaics** | electricity | **[]** (keiner) | **ja** (Kapazität 6–73 GW) |
| **heat_pump** | heat | **electricity** (0.25/Wärme, COP 4) | **nein** (Kapazität 0) |

Aus der Stationarität der `capacity`-Variable folgt die **Identität** (numerisch exakt verifiziert):

```
−μ^life_y = Σ_t max_load_t · ν^cap_t  −  opex_fixed · δ_y  +  c̄(capacity_y)
            └─────── Betriebswert ──────┘   └─ Fix-Opex ─┘   └─ Leak ─┘
```

mit ν^cap = Dual von `constraint_capacity_factor_conversion` (= `max_load·capacity − ref_flow ≥ 0`),
und ν^cap_t = `max(0, λ_heat_t − λ_elec_t/COP)` (ebenfalls exakt verifiziert).

**Residual-Zerlegung `−μ^life − Σ(max_load·ν^cap)` (Lauf 125738, ohne Perturbation):**

| Jahr | PV (CH/DE) | heat_pump CH | = opex_fix·δ − c̄(capacity) |
|---|---|---|---|
| y0 | **0.0000** | 0.960 | 0.96·1 − 0 |
| **y1** | **0.0000** | 0.137 | 0.96·0.943 − **0.768** |
| y2 | **0.0000** | 0.854 | 0.96·0.890 − 0 |

- `opex_specific_fixed`: heat_pump = **0.96**, PV = **0**.
- native `c̄(capacity)`: PV = `[0,0,0]` (gebaut → basisch); heat_pump = `[0, 0.768, 0]` (ungebaut → nicht-basisch in y1).

**Damit ist die Stelle exakt lokalisiert:** Für PV ist `c̄(capacity)=0` → μ^life = reiner
Betriebswert → RC exakt/interpretierbar. Für heat_pump leakt `c̄(capacity)=0.768` in μ^life →
die RC überzählt um genau `0.768/scaling` → 1650 statt 2089 (Break-even 1949 statt 1511).

**Warum heat_pump diese Konstellation trifft:** Betriebsmarge `λ_heat − 0.25·λ_elec = 0.0239 − 0
= 0.0239 > 0` strikt positiv (billiger als der Gasboiler, der λ_heat setzt) → heat_pump *will*
laufen, ist aber bei CAPEX 3600 nicht baubar → `capacity` hängt nicht-basisch an der Untergrenze →
`c̄(capacity)≠0`. PV als Strom-*erzeuger* wird gebaut → `capacity` basisch → nie dieser Leak.

## 4. Zwei Degenerations-Spielarten (Knoten-/Modellabhängig)

- **Original-Toy (DE/CH): Vintage-/Kapazitäts-Variablen-Leak** (oben). Flache Grundlast, kein Knappheitspreis. operativ ≠ lifetime.
- **Erweiterter Toy (6 Knoten): Knappheits-Dual.** heat_pump-Wert hängt dort zu 62–93 % an *einer* Stunde mit Wärmepreis-Spike (z. B. IT t*=77: 5.28 = 214× Median), in der der Gasboiler genau 1 von 288 Stunden an seiner Kapazitätsgrenze ist. Dieser Knappheitspreis ist nicht eindeutig (Null-Mengen-Entlastung) → RC-Phantom, das beim ersten gebauten kW kollabiert.

Gemeinsame Wurzel: native RC = 0, und die Ersatz-Rekonstruktion hängt an einem nicht-eindeutigen Dual.

## 5. Die operative RC-Variante (Fix)

Statt μ^life wird der Kapazitätswert direkt aus dem Betriebs-Dual gezogen — ohne den Leak:

```
value_operational = Σ_pay [ Σ_t max_load_t · ν^cap_t  −  opex_fixed · δ_y ]
rc_capex_equivalent_operational = capex_specific − value_operational / scaling
```

- Degenerations-immun (enthält `c̄(capacity)` nicht).
- **Nur für Conversion** definiert (Storage/Transport = `NaN` — deren Wert braucht Storage-Level-/Arbitrage-Duals).
- Identität: `operativ = lifetime + Σ_pay c̄(capacity)/scaling` → beide sind **gleich, wo `capacity` basisch ist**, und unterscheiden sich exakt um den Leak.

### Implementierung
`zen_garden/postprocess/postprocess.py`:
- `_compute_rc_capex_equivalent` gibt jetzt `(result, result_operational)` zurück.
- Neue Spalten in `capacity_addition_analysis.csv`: `rc_capex_equivalent_operational[_input_units]`.
- In `capacity_addition_analysis_conversion.csv` zusätzlich `ratio_reduction_operational`.
- Erscheint nur in **neuen** Läufen (braucht Live-Duals).

## 5b. Die zwei Wege als Übersetzungskette (PV vs. heat_pump)

Beide Rekonstruktionen beantworten dieselbe Frage: *„Was bringt eine zusätzliche Einheit Kapazität,
aufsummiert über alle Zeitschritte?"* — pro Zeitschritt `Kapazitätsfaktor × Grenzwert des Carriers`.
Sie greifen den Wert nur an **verschiedenen Enden derselben Constraint-Kette** ab.

**a) PV — Wert hängt an *einem* Preis (dem Output):**
```
ΔS_PV  ──Lifetime-Bilanz [μ_PV]──►  S_PV  ──Kap.-Faktor: G ≤ CF_t·S [ν_t]──►  G_PV (Strom)  ──Strombilanz [λ_elec,t]
```
Wert(1 GW PV) = `Σ_t CF_t·λ_elec,t` — mittags & Strom knapp → großer Beitrag; Überschuss (λ=0) → 0.
- **operativ** liest `ν_t` (unten, am Dispatch) = `Σ CF_t·λ_elec`.
- **lifetime** liest `μ_PV` (oben, an der Bilanz) = sollte `−Σ CF_t·λ_elec` sein.

**b) heat_pump — Wert hängt am *Spread zweier* Preise:**
```
ΔS_HP ──Lifetime [μ_HP]──► S_HP ──Kap.-Faktor [ν_t]──► G_heat ┬─► Wärmebilanz  [+ λ_heat,t]   (Erlös)
                                                              └─► Strombilanz  [− λ_elec,t]   (Input/COP)
   ⇒  ν_t = λ_heat,t − λ_elec,t/COP   (Betriebsmarge)
```
Wert(1 GW HP) = `Σ_t (λ_heat,t − λ_elec,t/COP)` über profitable Zeitschritte. PV hängt an *einem* (Output-)
Preis, heat_pump am *Spread* von Output (λ_heat) und Input (λ_elec) → heat_pump erbt jede Degeneration der
Stromseite (das λ_elec≈0-Überschuss-Regime); deshalb stabilisiert eine dispatchbare Stromquelle (Gasturbine,
die λ_elec eindeutig macht) auch heat_pumps RC.

**Wo die Degeneration sitzt:** am Übersetzungs-Schritt `S → ΔS` (der Lifetime-Bilanz). Sauber gilt
`μ = −Σ m_t·ν_t`; bei nicht-basischer Kapazität + Degeneration nur noch `μ = −Σ m_t·ν_t − c̄(S)`. Der Solver
darf einen Teil des Werts vom Bilanz-Dual μ in die Reduced Cost der Kapazitätsvariable `c̄(S)` umparken →
lifetime kollabiert. Operativ liest `ν_t` *vor* diesem Schritt (an den Carrier-Preisen) → immun, solange λ
eindeutig ist.

**Logische Beziehung der beiden (wichtig):** Es gilt exakt
> **lifetime-RC = operativ-RC − c̄(S)**

d. h. lifetime ist „operativ **plus** ein Degenerations-Risiko". Daraus folgt (generisch, d. h. ohne
zufällige Auslöschung):
- **lifetime korrekt ⟹ operativ korrekt** (lifetime verlangt operativ-korrekt *und* `c̄(S)=0` → strikt stärker).
- **operativ korrekt ⇏ lifetime korrekt** (operativ kann stimmen, während `c̄(S)≠0` lifetime verfälscht).
- **operativ ist nicht *immer* korrekt** — es kann scheitern, wenn die Carrier-Preise λ *selbst* degenerieren
  (z. B. Presolve), aber dann scheitern i. d. R. *beide*.

Genau das zeigt die Solver-Matrix (`docs/showcase_stresstest.md`): lifetime nur in 1/6 Konfigs korrekt,
operativ in 4/6 — und **jede** Konfig, in der lifetime korrekt war, war auch operativ korrekt, nie umgekehrt.

## 5c. Vollständigkeit: verliert die operative Rekonstruktion je einen echten Faktor?

Berechtigte Sorge: operativ liest **nur einen** Dual (ν^cap, Kapazitätsfaktor). Lifetime μ ist dagegen
— per Stationaritätsbedingung (KKT) der Kapazitätsvariable — die **Summe über *alle* Constraints, in
denen `capacity` vorkommt**, mal deren Duals. Also gilt exakt:

> **lifetime − operativ = c̄(capacity) [Degenerations-Leak] + (Duals jeder *weiteren* Constraint mit `capacity`).**

Daraus der **Vollständigkeitssatz:**
> operativ ist mathematisch **vollständig ⟺ die Kapazitätsfaktor-Constraint ist die einzige wertbildende
> Constraint, in der `capacity` auftaucht.**

Gibt es keine weitere → die Differenz ist *rein* der Leak (= Degenerierung), den operativ entfernt → operativ
ist der verlässlichere Proxy.

**Faktoren, die man theoretisch verlieren könnte** (Constraints mit `capacity` außer dem Kapazitätsfaktor):
1. **Min-Load / Must-Run** (`G ≥ min_load·S`) — Kapazität trägt Zwangsproduktions-*Kosten*.
2. **Reserve / Firm-Capacity / Adequacy / Capacity-Market** — Kapazität verdient eine Zahlung über die Energie hinaus.
3. **Kapazitäts-skaliertes Ramping.**

**Nachweis für ZEN-garden (LP), exemplarisch heat_pump:**
- Die einzige wertbildende Kapazitäts-Constraint ist `constraint_capacity_factor_conversion`
  (`conversion_technology.py:553`): `m_max,t·S ≥ G_t` — reine Obergrenze, **kein min_load-Term**.
- **Reserve/Firm-Capacity/Adequacy/Capacity-Market existieren in `zen_garden/model/` nicht** (grep leer) → Faktor 2 ausgeschlossen.
- `min_load` steckt nur in der **On-Off-Constraint** (`technology.py:1950`, MILP-only); der Showcase ist ein **reines LP** → inaktiv → Faktor 1 entfällt.
- `capacity ≤ limit` ist ein Bound; bindend ⇒ Tech wird als `at_limit` geflaggt, RC wird dann gar nicht benutzt.

⟹ **Für heat_pump (und jede LP-Conversion-Tech) verliert operativ keinen Faktor.** Außerhalb der
Degenerierung sind operativ und lifetime *identisch*; die einzig mögliche Abweichung ist der Leak, und dort
ist operativ der *richtigere* (Toy: operativ 2089 ≈ Sweep-Ground-Truth ~2075, lifetime 1650 = falsch).

**Wichtige Nuance:** operativ entfernt *eine* Degenerations-Quelle (den Kapazitäts-Leak c̄), **nicht** die
Preis-Degenerierung (λ nicht eindeutig, Bedingung C2). Preis-degenerierte Knoten brauchen weiterhin die
Perturbation. Im Showcase sind die Preise eindeutig (die Gasturbine fixiert λ_elec) → operativ verlässlich
ohne Perturbation.

**Vorbehalt für Crystal_Ball:** sobald eine Tech als **MILP mit min_load/on-off** läuft (Must-Run-Dual sitzt
in der On-Off-Constraint, die operativ *nicht* liest) oder ein **Reserve/Kapazitätsmarkt-Constraint** ergänzt
wird, verliert operativ diesen Faktor und lifetime wäre vollständiger. Vor dem Übertragen also prüfen, ob
Techs min_load/on-off (MILP) nutzen. Für reine LP-Modelle ohne Reserve-Constraint ist operativ vollständig.

## 6. Perturbation an/aus (Läufe 164755 vs. 164925)

Fingerabdruck: `capacity`(ungebaut) = 0.0001 → Perturbation AN (164755); = 0 → AUS (164925).

| node y | **AN (164755)** life | op | **AUS (164925)** life | op |
|---|---|---|---|---|
| CH y0 | 283.8 | 283.8 | **0** (breakeven_unreliable) | 283.8 |
| CH y1 | 2089.2 | 2089.2 | **1650.5** | 2089.2 |
| CH y2 | 2089.2 | 2089.2 | 2089.2 | 2089.2 |
| DE y1 | 2023.4 | 2023.4 | **1747.0** | 1912.4 |

- **Perturbation entfernt den Leak** (capacity wird basisch → `c̄=0`): mit Perturbation ist `life == operativ`.
- Ohne Perturbation divergieren sie (Leak): y0 fällt auf 0/breakeven_unreliable, y1 sackt ~20 % ab.
- **Zwei verschiedene Effekte, NICHT verwechseln:**
  - **CH**: operative RC ist *invariant* (2089 mit und ohne Perturbation) — hier sind die
    Dispatch-Preise eindeutig, also reicht die operative Spalte allein.
  - **DE**: operative RC *springt* (2023.4 mit / **1912.4** ohne Perturbation). Das ist **kein**
    harmloser „~5%-Versatz": der ±1%-Test misst das wahre Break-even-Fenster DE y1 ∈
    (1556.4, 1596.9) → wahre RC ∈ (2003, 2044). **2023.4 liegt drin (korrekt), 1912.4 liegt
    drüber (Break-even 1687.6 > Nobuild-Punkt 1596.9, an dem nichts baut → beweisbar falsch).**
  - Ursache: die *no-build*-Dispatch-Preise an DE sind dual-degeneriert (viel Gratis-PV,
    λ_elec=0 mehrdeutig). Die Perturbation zwingt ein Phantom-heat_pump in den Dispatch und
    selektiert damit den Preis-Vertex, an dem heat_pump marginal ist — den **ökonomisch
    richtigen** für ihre Bewertung. Ohne Perturbation landet der Solve auf einem falschen Vertex.

## 7. Validierung: ±1%-Build/Nobuild

Pro RC: CAPEX um `(1±1%)·rc` senken; bei `(1+1%)` MUSS bauen, bei `(1−1%)` darf NICHT.
Läufe **ohne Perturbation** (echte Bauentscheidung). Quelle der RC: Lauf 164755 (life==op).

| source | node y | RC | build@ | nobuild@ | val_build | val_nobuild | Ergebnis |
|---|---|---|---|---|---|---|---|
| 164755 | CH y0 | 283.8 | 3313.3 | 3319.0 | 0.290 | 0.0 | **PASS** |
| 164755 | CH y1 | 2089.2 | 1489.9 | 1531.7 | 0.351 | 0.0 | **PASS** |
| 164755 | CH y2 | 2089.2 | 1489.9 | 1531.7 | 0.351 | 0.0 | **PASS** |
| 164755 | DE y0 | 107.0 | 3491.9 | 3494.0 | 0.635 | 0.0 | **PASS** |
| 164755 | DE y1 | 2023.4 | 1556.4 | 1596.9 | 0.768 | 0.0 | **PASS** |
| 164755 | DE y2 | 2023.4 | 1556.4 | 1596.9 | 0.768 | 0.0 | **PASS** |
| 164925 (alt) | CH y1 | 1650.5 | 1933.0 | 1966.0 | **0.0** | 0.0 | **FAIL** |
| 164925 (alt) | DE y1 | 1747.0 | 1835.6 | 1870.5 | **0.0** | 0.0 | **FAIL** |

→ Die **164755-/operativen Werte (mit Perturbation) sind auf ±1% genau korrekt** (der Switch
liegt exakt im Band). Die abweichenden alten Werte fallen durch (heat_pump baut selbst am
Build-Punkt nicht → RC ~21 % zu klein).

**Das Build/Nobuild-Fenster widerlegt zusätzlich den operativen Wert OHNE Perturbation:**
DE y1 baut bei 1556.4, nicht bei 1596.9 → wahres Break-even ∈ (1556.4, 1596.9), wahre RC ∈
(2003, 2044). Der operative Wert *mit* Perturbation (2023.4 → BE 1576.6) liegt drin; der
operative Wert *ohne* Perturbation (1912.4 → BE 1687.6) liegt **drüber** — er sagt Bau bei 1687.6
voraus, aber bei 1596.9 baut nichts ⇒ **1912.4 ist beweisbar falsch.** Nur der perturbierte
operative Wert ist exakt. (CH y1 dagegen: 2089 mit *und* ohne Perturbation, BE 1510.8 ∈
(1489.9, 1531.7) → an CH genügt die operative Spalte allein.)

## 8. Gegenprobe Gasboiler (Carry-over-Phantom)

Gasboiler in 164755: y0 **gebaut** (rc=0); y1/y2 **Carry-over** mit `ratio_reduction = 2.255 > 1`
(rc 1975 > capex 876 → Break-even negativ → ±1% nicht anwendbar). Stattdessen CAPEX → 1 (gratis):

| node y | rc (life==op) | gebaut bei capex=1 | Verdikt |
|---|---|---|---|
| CH y1/y2 | 1975.4 | 0.0 | **Phantom** (baut nie, auch gratis nicht) |
| DE y1/y2 | 1975.4 | 0.0 | **Phantom** |

→ Carry-over ist ein **anderer** Fehlertyp: die Nachfrage ist durch den y0-Bau bereits gedeckt,
zusätzliche Kapazität ist auch gratis wertlos. **Die operative Spalte behebt das NICHT**
(operativ == lifetime == 1975); dafür ist der bestehende Flag `ratio_reduction > 1` zuständig.

## 9. Praktische Leitlinie

- **Immer MIT Perturbation laufen** und die operative Spalte lesen. Dann ist der Wert an
  preis-eindeutigen *und* preis-entarteten Knoten korrekt (DE y1 = 2023.4, ±1%-validiert).
- **Spalten `rc_capex_equivalent` vs. `rc_capex_equivalent_operational` vergleichen** (Diagnostik):
  - gleich → kein Kapazitäts-Leak (mit Perturbation der Normalfall; PV immer).
  - verschieden → Lifetime-RC hat den Leak; die operative ist die bessere — **aber nur
    verlässlich, wenn auch mit Perturbation gerechnet wurde** (sonst kann sie an
    preis-entarteten Knoten selbst falsch sein, s. DE-ohne-Perturbation).
- **`ratio_reduction(_operational) > 1`** → Carry-over/Phantom, beide Varianten unbrauchbar (separat behandeln).
- Ohne Perturbation ist die operative Spalte zwar besser als Lifetime (richtig an
  preis-eindeutigen Knoten wie CH, rettet die y0-Greenfield-Fälle), an preis-entarteten
  Knoten (DE) aber **nicht** korrekt — also **kein** Ersatz für die Perturbation.

## 10. Wann es mathematisch funktioniert — und wann nicht (kritisch)

Der operative RC ist
```
rc_op = capex − Σ_pay( Σ_t max_load_t·ν^cap_t − opex_fixed·δ_y ) / scaling,
ν^cap_t = max(0, λ_ref_t·η − Σ_in λ_in_t·α_in − c_var_t)
```
und stimmt mit dem **wahren Break-even** (Build/Nobuild) **nur dann exakt**, wenn vier
Bedingungen halten — jede ist falsifizierbar:

**(C1) Struktur — der Wert muss durch `constraint_capacity_factor_conversion` fließen.**
Die native RC von `capacity_addition` ist 0 (Kollaps); der Wert wird über die Kette
`capacity → [capacity_factor] → flow → [carrier_conversion] → [energy_balance]` rekonstruiert.
Das hält, weil `capacity` operativ **nur** im Kapazitätsfaktor-Constraint vorkommt (Stationarität
⇒ Wert = Σ max_load·ν^cap, netto Fix-Opex).
✗ **Bricht** für **Storage** (Wert = Lade-/Entlade-Arbitrage über Storage-Level-Constraints,
nicht im Kapazitätsfaktor) → daher bewusst `NaN`. ✗ Bricht, wenn `capacity` in einem weiteren
bindenden Constraint steckt, dessen Dual wir nicht addieren (z. B. `capacity_limit`, `min_load`).

**(C2) Dual-Eindeutigkeit — die Preise λ müssen am no-build-Dispatch eindeutig sein.**
ν^cap besteht aus den Knotenpreisen λ (Energiebilanz-Duals). Die RC ist exakt nur bei
**dual-nicht-degeneriertem** Dispatch.
✗ **Bricht** bei: **Gratis-Überschuss** (abgeregeltes PV → λ=0 in einem Intervall mehrdeutig →
λ_in·α_in unbestimmt; *das ist der DE-Fall*); **Knappheit mit Null-Mengen-Entlastung** (Boiler
exakt auf Spitzenlast → Scarcity-λ irgendwo zwischen Brennstoffkosten und VoLL; *erw. Toy IT*);
**perfekte Substitute** zu gleichen Grenzkosten. Dann ist ν^cap **vertex-abhängig** → nur korrekt,
wenn der Solve auf dem richtigen Vertex sitzt. Die **Perturbation** verschiebt den Vertex
heuristisch dahin, wo die Tech marginal ist (empirisch der richtige — DE 2023.4), ist aber
**kein Theorem**: keine Garantie, dass immer der exakt richtige Vertex getroffen wird.

**(C3) First-Order = endlicher Schritt — kein knife-edge-Wert am Eintritt.**
Die RC ist der Grenzwert der *ersten* (infinitesimalen) Einheit zu no-build-Preisen; der Test
baut eine *endliche* Menge. Gleich nur, wenn der Grenzwert über den Eintritt ~konstant ist.
✓ Hält bei glattem Price-Taker-Eintritt (heat_pump als Grundlast). ✗ **Bricht**, wenn der Wert
an einer einzelnen Knappheitsstunde hängt, die der erste endliche Bau auslöscht (erw. Toy IT:
erste kW entlastet die 1-Stunden-Spitze, Wert kollabiert → marginale RC ≫ endlicher Break-even
→ Phantom). (= C2-Knappheit in primaler Form.)

**(C4) Kein Carry-over.** Ist die Nachfrage durch einen Vorjahres-Bau gedeckt (capacity > 0,
value = 0, `ratio_reduction > 1`), ist *keine* RC-Variante eine Bau-Distanz (baut auch gratis
nicht). operativ = lifetime = Phantom. → `ratio>1`-Flag nutzen, nicht die RC.

| Bedingung | hält | bricht bei | Beispiel |
|---|---|---|---|
| C1 Struktur | Conversion | Storage, Zusatz-Constraints auf capacity | Storage → NaN |
| C2 Dual-Eindeutigkeit | strikte Merit-Order | Gratis-λ=0, Knappheit, Substitute | DE, IT |
| C3 First-Order=endlich | glatter Eintritt | knife-edge-Wert | erw. Toy IT |
| C4 kein Carry-over | Greenfield-Jahr | Vorjahres-Bau trägt über | Gasboiler y1/y2 |

**Alle vier halten ⇒ operativ = wahrer Break-even (beweisbar, ±1%-bestätigt):** heat_pump CH
(alle Jahre), DE *mit* Perturbation. **C2 bricht ⇒** Perturbation nötig (DE) oder Phantom (IT).
**C1/C4 bricht ⇒** außerhalb des Geltungsbereichs (Storage / Carry-over).

**Grundsätzliche Grenze (ehrlich):** Der ganze RC-aus-Duals-Ansatz ist eine **lokale,
First-Order-Schätzung**. Er kann höchstens so gut sein, wie die Duals eindeutig und die
Antwort lokal linear sind. Die **einzige degenerations-immune Wahrheit ist der endliche
Re-Solve (Bisektion)**. Die operative RC ist ein billiger, meist-korrekter Proxy, der die
**Bisektion seltener nötig macht — aber nicht ersetzt**: in den C2/C3-Fällen bleibt eine
punktuelle Bisektion der einzige sichere Check.

## Artefakte / Reproduktion

- Läufe: `outputs_20260620-164755` (mit Perturbation), `outputs_20260620-164925` (ohne).
- Check-ups: `outputs_*_rc_checkup_164755/checkup_164755_summary.csv` (heat_pump ±1%),
  `outputs_*_rc_checkup_gasboiler/checkup_gasboiler_summary.csv` (Gasboiler gratis).
- Ground truth via `rc_capex_file_override.py` (CAPEX-Override + Re-Run, degenerations-immun).
- Code: `zen_garden/postprocess/postprocess.py` (`_compute_rc_capex_equivalent`,
  `save_capacity_addition_analysis`, `save_capacity_addition_classified`).
