# Wann ist `rc_capex_equivalent` belastbar? — Untersuchungs-Befunde

Diese Datei bündelt die Erkenntnisse einer ausführlichen Untersuchung, **warum die
Reduced-Cost-Rekonstruktion bei manchen Technologien exakt stimmt und bei anderen
einen Phantom-Wert liefert** — inkl. der überprüften **Sackgassen**, damit sie nicht
erneut abgelaufen werden.

Sie ergänzt die Herleitung in
[`rc_reduced_cost_methodology.md`](rc_reduced_cost_methodology.md) (das *Wie* der
Berechnung) und die Degeneriertheits-Probleme in
[`rc_analysis_known_issues.md`](rc_analysis_known_issues.md). **Kurz:** der Befund hier
ist eine *konkrete, neue Ausprägung* von Methodik §D.2 (duale Degeneriertheit), die die
dortige Erkennungsheuristik **nicht** erfasst.

---

## 0. TL;DR

- Die Formel `RC = capex − Wert/scaling` ist **carrier-unabhängig** und mathematisch
  korrekt. Sie steht und fällt mit **einem** Input: dem **Wert** (Lifetime-Dual).
- Der Wert ist **eindeutig** und die RC **exakt**, solange der **Wert-Endpunkt** (=
  Kosten der marginalen/verdrängten Technologie des Referenzcarriers) **eindeutig
  bestimmt** ist.
- Bei **dualer Degeneriertheit** (mehrere Substitute am selben Break-even, symmetrische
  Knoten) wandert der abgelesene Wert im Intervall → **Phantom-Wert** → RC falsch.
- Das ist **szenario-abhängig**, **nicht** carrier-abhängig: dieselbe Tech (`heat_pump`)
  ist im Toy-Model exakt und im großen Modell potenziell degeneriert.
- **`vbasis` ist KEIN Diskriminator** (lauf-abhängig; `vbasis=0` ist oft trotzdem
  korrekt). Belegt mehrfach.
- Es fehlt **kein** Constraint-Term in der Formel (die Herleitung §A.7 ist vollständig).
- **Ground Truth** = Build/Nobuild- bzw. Bisektions-Test über den **Datei-CAPEX-Override**.

---

## 1. Die zentrale Erkenntnis: der „Wert-Endpunkt"

`RC = capex − Wert/scaling`. Der **Wert** = „was spart das System, wenn diese Kapazität
da wäre" = **Kosten der Alternative, die sie verdrängt**, abgelesen aus dem Lifetime-Dual.

An einer **ungebauten** Tech ist dieser Wert nicht ein Punkt, sondern ein **Intervall**
(Methodik §C.6): der Lifetime-Dual darf zwischen dem **Wert-Endpunkt** (richtig) und dem
**Capex-Endpunkt** (Schein-Null) liegen. Welcher gemeldet wird, hängt davon ab, ob der
Wert-Endpunkt **eindeutig** ist:

| | Wert-Endpunkt eindeutig? | RC |
|---|---|---|
| eindeutige marginale Versorgung (klare verdrängte Tech, asymmetrische Knoten) | ✅ ja | **exakt** |
| degeneriert (mehrere Substitute am selben Break-even, symmetrische Knoten) | ❌ nein | **Phantom** |

Die uniforme Perturbation (`rc_lifetime_rhs_perturbation`) pinnt den Endpunkt am
**Einzel**-Knoten, kann aber **Mehr-Knoten-/Substitutions-Symmetrie nicht brechen**
(Methodik §C.6). Genau dort entsteht das Phantom.

---

## 2. Belege

### 2.1 Toy-Model (`5_multiple_time_steps_per_year`): `heat_pump` — EXAKT ✅

2 Knoten (DE, CH), Wärme von **heat_pump + natural_gas_boiler**. Drei Läufe auf
`heat_pump @ DE`:

| Lauf | CAPEX-Eingriff | value | rc [€/kW] |
|---|---|---|---|
| Baseline | — | 0 | **107.02** |
| build | capex um > 107 gesenkt | **1.375** (gebaut, verdrängt gas_boiler 1:1) | 0 |
| nobuild | capex um **100** gesenkt | 0 | **7.02** = 107.02 − 100 |

→ RC **exakt und lokal linear**. `vbasis = 0` durchgehend — **trotzdem korrekt**.
Grund: `natural_gas_boiler` ist die **eindeutige** marginale Wärme-Tech → Wert-Endpunkt
eindeutig. Nur 2, **verschiedene** Knoten → keine Symmetrie.

**Vollständige Validierung** ([`rc_validate_toy.py`](../rc_validate_toy.py)): **alle 12**
interpretierbaren RC-Fälle des Toy-Models per Build/Nobuild geprüft → **12/12 PASS**.
Abdeckung: `heat_pump` (Carrier **heat**!) und `photovoltaics copy` (Carrier
electricity), beide Knoten, alle 3 Jahre, RC von 1.8 % bis 58 %. **Auch die
heat-Carrier-Tech ist hier exakt** — der direkte Gegenbeleg dazu, dass „Carrier heat"
das Problem wäre. Im nicht-degenerierten Toy-Model gilt die Methodik für *alle* Techs.

### 2.2 Großes Modell (`Crystal_Ball`): `oil_boiler @ NL` — PHANTOM ❌

`rc = 235.88` (capex ≈ 311). Build/Nobuild-Test (Datei-Override): selbst bei **−86 %**
(capex 41) **baut sie nicht** → wahre Schwelle ≫ 86 %, RC stark **unterschätzt**.
Per-Constraint-Zerlegung (Dual-Dump): `lifetime (+4.96)` und `capacity_coupling (−4.96)`
heben sich exakt auf → **RC_true = 0** (degeneriert-basisch); die rekonstruierte 235.88
ist ein Phantom. Heat von **6 Substituten** über **28 Knoten** → Wert-Endpunkt
mehrdeutig.

### 2.3 Großes Modell: `wind_onshore`, `photovoltaics`, `nuclear`, `reservoir_hydro` — korrekt ✅

Validiert (teils händisch im 1 %-Bereich). Strom hat tiefe Merit-Order → eindeutiger
nodaler Preis → eindeutiger Wert-Endpunkt. `reservoir_hydro @ CZ` ist dabei `vbasis=0`
und **trotzdem korrekt** — weiterer Beleg, dass vbasis nichts aussagt.

---

## 3. Sackgassen — was es **nicht** ist

| Hypothese | Status | Beleg |
|---|---|---|
| **`vbasis` ist der Diskriminator** (basisch → falsch) | ❌ **falsch** | `heat_pump` (Toy) und `reservoir_hydro CZ` sind `vbasis=0` und korrekt; vbasis ist zudem **lauf-abhängig** (degeneriertes LP → nicht-eindeutige Basis). Methodik §B.2 sagt es explizit: vbasis ist kein Wirtschaftssignal. |
| **Ein fehlender Constraint-Dual** (`capacity_coupling`, `construction_time`, `min/max_capacity_addition`) | ❌ **falsch** | Dual-Dump zeigt: nur `lifetime + capacity_coupling` tragen, und `coupling` ist analytisch in `K=ασ` substituiert (Methodik §A.7a). Bei degeneriert-basischen Zeilen heben sich beide zu `RC_true=0` auf — das ist der **native-RC-Kollaps** (§B.1), kein fehlender Term. |
| **Der Referenzcarrier** (`electricity` ok, `heat`/`shipping` nicht) | ⚠️ **zu grob** | Korreliert, ist aber kein Gesetz: `heat_pump` (Carrier heat) funktioniert im Toy exakt. Der Carrier ist nur ein **Proxy** für „eindeutige marginale Versorgung". |

**Die eigentliche Ursache** ist die **duale Degeneriertheit des Wert-Endpunkts**
(Methodik §D.2) — szenario-abhängig, nicht durch ein einzelnes statisches Merkmal
erfassbar.

---

## 4. Neuer Fehlermodus: Phantom-**NONZERO** (Heuristik-Lücke)

Die Methodik-Checkliste flaggt nur `value=0 ∧ rc ≈ 0` als unzuverlässig (Schein-**Null**).
`oil_boiler` zeigt aber `rc = 235.88` (**>0**) und sieht „ehrlich unrentabel" aus — ist
aber ebenso ein Phantom. **Die rc≈0-Heuristik erfasst diesen Fall nicht.** Ursache: das
Wert-Intervall einer wertlosen, weit-aus-dem-Geld-Tech ist breit (`[−K, ≈0]`); der
gemeldete Endpunkt landet irgendwo darin — auch als plausibel aussehende positive Zahl.

→ **Konsequenz:** Eine RC > 0 ist **kein** Beweis für Verlässlichkeit. Ohne
Ground-Truth-Check ist eine plausibel große RC bei mehrfach-substituierten End-Use-Techs
mit Vorsicht zu lesen.

---

## 5. Gebaute Werkzeuge (Diagnose & Validierung)

| Werkzeug | Zweck |
|---|---|
| [`rc_capex_file_override.py`](../rc_capex_file_override.py) | robuste per-(tech,node,year) CAPEX-Override via **Daten-CSV-Swap** (Kontextmanager, byte-genaues Restore). Basis aller Build/Nobuild-/Bisektions-Tests. |
| [`rc_stresstest_conversion.py`](../rc_stresstest_conversion.py) | Build/Nobuild-Stresstest: pickt buildable_rc-Fälle und prüft `−1.1×RC` baut / `−0.9×RC` baut nicht. |
| [`rc_validate_electricity.py`](../rc_validate_electricity.py) | dasselbe, gefiltert/auto-entdeckt für **electricity**-Conversion-Techs (Thesis-Nachweis der zuverlässigen Klasse). |
| `Postprocess.dump_rc_decomposition()` ([postprocess.py](../zen_garden/postprocess/postprocess.py)) + [`rc_dual_dump_run.py`](../rc_dual_dump_run.py) | **exakte per-Constraint-Zerlegung** `RC_true = obj − Σ(coef×dual)` für gewählte Ziele. Opt-in via `analysis.rc_dual_dump`/`rc_dual_dump_targets`. |
| [`rc_classify_existing.py`](../rc_classify_existing.py), [`rc_heatmaps.py`](../rc_heatmaps.py) | klassifizierte CSVs + Heatmaps (siehe [`rc_capacity_addition_classified.md`](rc_capacity_addition_classified.md), [`rc_heatmaps.md`](rc_heatmaps.md)). |

**Ground-Truth-Methode** (degeneriertheits-immun): CAPEX schrittweise senken (Bisektion)
bzw. Build/Nobuild um ±x % und prüfen, ob `value > 0` kippt — misst die **wahre**
Schwelle ohne Duale. Teuer (2+ Modelllaufe je Fall), aber der einzige belastbare Beweis.

---

## 6. Praktische Zuverlässigkeits-Leitlinie

1. **Verlässlich (direkt nutzbar):** Techs, deren Referenzcarrier eine **eindeutige
   marginale Versorgung** hat — empirisch `electricity` (tiefe Merit-Order, nodale
   Preise). Im Crystal_Ball validiert: PV, wind on/off, nuclear, reservoir_hydro,
   run-of-river, fuel_cell, … (Storage: battery via Bundle, separat).
2. **Verdächtig (vor Nutzung prüfen):** mehrfach-substituierte End-Use-Carrier
   (`heat`, `shipping`, `passenger/truck_mileage`, `fuel_for_cement`, …) **in
   Szenarien mit vielen symmetrischen Knoten**. Nicht per se falsch (Toy zeigt heat_pump
   exakt), aber degeneriertheits-gefährdet.
3. **Nie blind vertrauen bei:** großen `rc` an weit-aus-dem-Geld-Techs (§4) — Phantom
   möglich trotz `rc > 0`.
4. **Belastbarer Nachweis:** Build/Nobuild bzw. Bisektion (§5) für genau die Techs, die
   man in einer Aussage zitiert.

> Für eine **Arbeit** ist die verteidigbare Formulierung nicht „funktioniert für Carrier
> X", sondern: *„Die RC ist exakt, solange der Wert-Endpunkt eindeutig ist; wir weisen
> das per Build/Nobuild-Test für die zitierten Technologien nach."* — der carrier-Bezug
> ist nur eine nützliche **Heuristik**, kein Beweis.

---

## 7. Offene Punkte / Empfehlungen

- **Bessere Unzuverlässigkeits-Flagge** als `rc≈0`: erfasst den Phantom-**Nonzero** nicht.
  Kandidaten: (a) node-resolved **CAPEX-Jitter** (Methodik §C.6/Problem 3) → bricht
  Symmetrie → eindeutige Duale; (b) automatischer **1-Schritt-Bisektions-Spot-Check** je
  gemeldetem RC; (c) Heuristik „Referenzcarrier mit ≥k Substituten am Break-even".
- **Vollständiger Build/Nobuild-Test des großen Modells** ist unpraktikabel (≈ ein Tag
  Rechenzeit für alle interessanten RC) — gezielt für zitierte Fälle einsetzen.
- Doc-String von `perturb_objective_for_rc` ist laut Methodik §C.2 veraltet (behauptet
  Endpunkt-Selektion); `rc_perturbation` bleibt korrekt auf 0.

---

*Querverweise: [`rc_reduced_cost_methodology.md`](rc_reduced_cost_methodology.md) (Herleitung),
[`rc_analysis_known_issues.md`](rc_analysis_known_issues.md) (Degeneriertheits-Probleme),
[`rc_capacity_addition_classified.md`](rc_capacity_addition_classified.md) und
[`rc_heatmaps.md`](rc_heatmaps.md) (Auswertungs-Pipeline).*
