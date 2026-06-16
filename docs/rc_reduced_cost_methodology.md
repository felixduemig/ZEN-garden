# Methodik der Reduced-Cost-Berechnung (`rc_capex_equivalent`) inkl. Perturbation

Dieses Dokument beschreibt **exakt und nachvollziehbar**, wie in diesem Repository
der wirtschaftliche Reduced Cost einer Technologie berechnet wird — die Größe
`rc_capex_equivalent` bzw. `rc_capex_equivalent_input_units` in der Datei
`capacity_addition_analysis.csv`. Sie beantwortet die Frage:

> **Um wie viel muss die spezifische CAPEX einer (noch nicht gebauten)
> Technologie an einem Knoten sinken, damit ihr Zubau optimal wird?**
> (`= 0` für gebaute Technologien, `> 0` für unrentable, in €/kW.)

Zielgruppe: Energiesystem-Modellierer:innen mit LP-Grundwissen, die das Verfahren
mathematisch und logisch vollständig nachvollziehen und gegenüber Dritten
verteidigen können müssen.

> **Abgrenzung zu [`rc_analysis_known_issues.md`](rc_analysis_known_issues.md):**
> Jenes Dokument katalogisiert die drei *Degeneriertheits-Probleme* und ihre
> Symptome. Dieses Dokument leitet die *Berechnung selbst* her und erklärt, warum
> sie so und nicht anders aufgebaut ist. Wo sich Inhalte berühren, wird auf die
> Known-Issues verwiesen statt sie zu wiederholen.

Jede Behauptung ist mit einer konkreten `Datei:Zeile`-Stelle belegt. Stand des
referenzierten Codes: Branch zum Zeitpunkt der Erstellung; bei Abweichungen gilt
der Code.

---

## 0. Notation und Symbole

| Symbol | Bedeutung | Quelle im Code |
|---|---|---|
| $h$ | Technologie (`set_technologies`) | — |
| $n$ | Knoten / Standort (`set_location`) | — |
| $y$ | Planungsjahr (`set_time_steps_yearly`) | — |
| $y_\text{inv}$ | Investitionsjahr (Index der betrachteten `capacity_addition`-Zeile) | [postprocess.py:575](../zen_garden/postprocess/postprocess.py) |
| $y_0$ | erstes Planungsjahr `years[0]` | [postprocess.py:516](../zen_garden/postprocess/postprocess.py) |
| $\Delta S_{h,n,y}$ | `capacity_addition` — Zubau in Jahr $y$ | [technology.py:1514](../zen_garden/model/technology/technology.py) |
| $S_{h,n,y}$ | `capacity` — installierte Kapazität am Jahresende | [technology.py:1520](../zen_garden/model/technology/technology.py) |
| $\alpha_{h,n,y}$ | `capex_specific` — spezifische Investitionskosten [Kosten/Kapazität] | [postprocess.py:553](../zen_garden/postprocess/postprocess.py) |
| $r$ | `discount_rate` — Diskontsatz | [postprocess.py:513](../zen_garden/postprocess/postprocess.py) |
| $\mathrm{dy}$ | `interval_between_years` — Jahre zwischen Planungsperioden | [postprocess.py:514](../zen_garden/postprocess/postprocess.py) |
| $l_h$ | `depreciation_time` — Abschreibungsdauer | [postprocess.py:578](../zen_garden/postprocess/postprocess.py) |
| $a_h$ | Annuitätsfaktor (CRF) | [postprocess.py:581](../zen_garden/postprocess/postprocess.py) |
| $N_h$ | `n_periods` — Anzahl Perioden in der Lebensdauer | [postprocess.py:582](../zen_garden/postprocess/postprocess.py) |
| $\mathrm{PY}(y_\text{inv})$ | `pay_years` — Jahre, in denen $\Delta S_{h,n,y_\text{inv}}$ aktiv ist | [postprocess.py:585](../zen_garden/postprocess/postprocess.py) |
| $\delta(y)$ | `discount_factors[y]` — Diskontfaktor des Jahres $y$ | [postprocess.py:520](../zen_garden/postprocess/postprocess.py) |
| $\sigma$ | `scaling` $= a_h \sum_{y\in\mathrm{PY}}\delta(y)$ | [postprocess.py:587](../zen_garden/postprocess/postprocess.py) |
| $\lambda^{\text{lt}}_{h,n,y}$ | Dual von `constraint_technology_lifetime` | [postprocess.py:529](../zen_garden/postprocess/postprocess.py) |
| $\mu^{\text{tot}}_{h,y}$ | Dual von `constraint_technology_diffusion_limit_total` | [postprocess.py:540](../zen_garden/postprocess/postprocess.py) |
| $\mu^{\text{an}}_{h,n,y}$ | Dual von `constraint_technology_diffusion_limit` (mit Spillover) | [postprocess.py:546](../zen_garden/postprocess/postprocess.py) |
| $\vartheta_{h,y}$ | `max_diffusion_rate` | [postprocess.py:645](../zen_garden/postprocess/postprocess.py) |
| $\text{tdr}_{h,y}$ | technology diffusion rate $=(1+\vartheta_{h,y})^{\mathrm{dy}}-1$ | [postprocess.py:650](../zen_garden/postprocess/postprocess.py) |
| $\rho_h$ | `knowledge_depreciation_rate` | [postprocess.py:625](../zen_garden/postprocess/postprocess.py) |
| $\text{kdr}_{h}(y_\text{inv}\!\to\! y)$ | Wissens-Abschreibung $=(1-\rho_h)^{\mathrm{dy}(y-1-y_\text{inv})}$ | [postprocess.py:641](../zen_garden/postprocess/postprocess.py) |
| $\omega_h$ | `knowledge_spillover_rate` (`sr`) | [postprocess.py:630](../zen_garden/postprocess/postprocess.py) |
| $f$ | `fraction_year` — Skalierung interne ↔ Eingabe-Einheiten | [postprocess.py:773](../zen_garden/postprocess/postprocess.py) |
| $d$ | wirtschaftlicher Reduced Cost in NPV-/Modelleinheiten | hergeleitet, §3.4 |

**Konvention.** Das Modell **minimiert** den Net Present Cost (NPC). Eine Variable
an ihrer unteren Schranke ($\Delta S = 0$, „nicht gebaut") ist im Optimum nur dann
zulässig nicht-basisch, wenn ihr Reduced Cost $d \ge 0$ ist.

---

## 1. Modellkontext: Wo `capacity_addition` in Kosten und Constraints auftaucht

Der zentrale, oft übersehene Punkt: **`capacity_addition` hat keinen direkten
Zielfunktionskoeffizienten.** Ihre Kosten erreichen den NPC erst über eine Kette
von Kopplungs-Constraints. Das ist der ganze Grund, warum der Reduced Cost
*rekonstruiert* werden muss (§2/§B) und nicht abgelesen werden kann.

### 1.1 Die Kostenkette (Zielfunktionsbeitrag)

```
capacity_addition
   └─(constraint_capacity_coupling)→ capacity_approximation
   └─(PWA / capex_specific)        → capex_approximation = cost_capex_overnight
   └─(constraint_cost_capex_yearly)→ cost_capex_yearly        (× Annuität a, über Abschreibungs-Range)
   └─(…_total → cost_total)        → net_present_cost          (× Diskontfaktor δ(y))
```

- `capacity_addition = capacity_approximation` und
  `cost_capex_overnight = capex_approximation` werden in
  [conversion_technology.py:837–846](../zen_garden/model/technology/conversion_technology.py)
  gekoppelt; im linearen Fall (konstantes `capex_specific`) gilt
  $\text{cost\_capex\_overnight} = \alpha_{h,n,y}\,\Delta S_{h,n,y}$.
- Die **Annualisierung** mit dem Annuitätsfaktor $a_h$ über die Abschreibungs-Range
  geschieht in `constraint_cost_capex_yearly`
  ([technology.py:1827–1830](../zen_garden/model/technology/technology.py),
  Annualisierung [technology.py:1862](../zen_garden/model/technology/technology.py)).
- Die **Diskontierung** zum NPC erfolgt in `constraint_net_present_cost`
  ([energy_system.py:707–717](../zen_garden/model/energy_system.py)).

> **Konsequenz:** In der LP-Matrix ist der Zielkoeffizient von
> `capacity_addition` exakt $0$. Der ökonomisch relevante „Preis" pro zugebauter
> Einheit ist über mehrere Constraints und Hilfsvariablen verteilt. Gurobis
> nativer Reduced Cost auf `capacity_addition` misst deshalb etwas strukturell
> anderes als die ökonomische Größe, die wir wollen (siehe §B).

### 1.2 Die Wert-Constraints (woher der Nutzen einer Einheit Kapazität kommt)

**(a) `constraint_technology_lifetime`** —
[technology.py:1471–1543](../zen_garden/model/technology/technology.py).
Mit `lt_range`-Daten $=-1$ ([technology.py:1508](../zen_garden/model/technology/technology.py))
und `expr = (lt_range * capacity_addition).sum(prev)`
([technology.py:1518](../zen_garden/model/technology/technology.py)),
`lhs = capacity + expr` ([technology.py:1519](../zen_garden/model/technology/technology.py)),
`rhs = existing_capacities` ([technology.py:1535](../zen_garden/model/technology/technology.py)),
`constraints = lhs == rhs` ([technology.py:1536](../zen_garden/model/technology/technology.py)):

$$
S_{h,n,y} \;-\; \sum_{\tilde y \in \mathrm{LT}(y)} \Delta S_{h,n,\tilde y}
\;=\; s^{\text{ex}}_{h,n}
\qquad\Bigl(\text{Greenfield: } s^{\text{ex}}=0\Bigr)
$$

Hieraus folgt die **erste Schlüsseltatsache**: In jeder Constraint-Zeile für ein
Jahr $y$ mit $y_\text{inv}\in\mathrm{LT}(y)$ — d.h. für alle
$y \in \mathrm{PY}(y_\text{inv})$ — taucht $\Delta S_{h,n,y_\text{inv}}$ mit
Koeffizient **$-1$** auf.

**(b) `constraint_technology_diffusion_limit[_total]`** —
[technology.py:1545–1782](../zen_garden/model/technology/technology.py).
Mit
$\text{tdr}=(1+\vartheta)^{\mathrm{dy}}-1$ ([technology.py:1581](../zen_garden/model/technology/technology.py)),
$\text{kdr}=(1-\rho)^{\mathrm{dy}(y-1-\tilde y)}$ ([technology.py:1626–1628](../zen_garden/model/technology/technology.py)),
`term_knowledge_no_spillover = tdr * (capacity_addition * kdr).sum(prev)`
([technology.py:1642](../zen_garden/model/technology/technology.py)),
und der LHS-Form `capacity_addition − term_knowledge − …` mit `<=`
([technology.py:1725–1747](../zen_garden/model/technology/technology.py)):

$$
\Delta S_{h,n,y} \;-\; \text{tdr}_{h,y}\!\!\sum_{\tilde y < y}\!\text{kdr}_h(\tilde y\!\to\! y)\,\Delta S_{h,n,\tilde y}\;-\;(\dots)\;\le\; \text{RHS}_{h,n,y}
$$

Hieraus die **zweite Schlüsseltatsache**: $\Delta S_{h,n,y_\text{inv}}$ taucht in
allen **zukünftigen** Diffusions-Constraints ($y>y_\text{inv}$) mit Koeffizient
**$-\text{tdr}_{h,y}\,\text{kdr}_h(y_\text{inv}\!\to\! y)$** auf (Wissensbasis).
Bei endlicher Spillover-Rate $\omega_h$ kommt der Cross-Node-Term
([technology.py:1665–1670](../zen_garden/model/technology/technology.py)) mit
Koeffizient **$-\text{tdr}_{h,y}\,\omega_h\,\text{kdr}_h(y_\text{inv}\!\to\! y)$**
in den Constraints *anderer* Knoten hinzu.

---

## A. Mathematische Herleitung der RC-Formel

Wir leiten die Formel
([postprocess.py:693–696](../zen_garden/postprocess/postprocess.py))

$$
\boxed{\;\text{rc\_capex\_equivalent} \;=\; \alpha_{h,n,y_\text{inv}} \;-\; \frac{\text{elec\_value} - \text{diff\_contribution}}{\sigma}\;}
$$

aus der LP-Dualtheorie her und definieren jeden Term.

### A.1 Kostenseite: was eine Einheit Zubau im NPC kostet

Eine Einheit $\Delta S_{h,n,y_\text{inv}}$ verursacht Overnight-CAPEX
$\alpha_{h,n,y_\text{inv}}$ (§1.1). Diese wird annualisiert mit dem **Annuitätsfaktor
(CRF)** ([postprocess.py:581](../zen_garden/postprocess/postprocess.py),
identisch [technology.py:1828](../zen_garden/model/technology/technology.py)):

$$
a_h \;=\; \frac{(1+r)^{l_h}\, r}{(1+r)^{l_h}-1}
\qquad(\text{bzw. } a_h = 1/l_h \text{ für } r=0).
$$

Die Annuität wird in jedem Jahr der Lebensdauer fällig und mit $\delta(y)$
diskontiert. Die **pay_years** ([postprocess.py:585](../zen_garden/postprocess/postprocess.py))

$$
\mathrm{PY}(y_\text{inv}) = \{\,y : y_\text{inv} \le y \le y_\text{inv}+N_h-1\,\},
\qquad N_h = \max\!\Bigl(\bigl\lfloor l_h/\mathrm{dy}\bigr\rfloor,\,1\Bigr)
$$

([postprocess.py:582](../zen_garden/postprocess/postprocess.py)) sind genau die
Jahre, in denen die in $y_\text{inv}$ gebaute Anlage noch existiert — also genau
die Lifetime-Zeilen aus §1.2(a). Der **Diskontfaktor**
([postprocess.py:520–526](../zen_garden/postprocess/postprocess.py)) ist
bit-identisch zu `constraint_net_present_cost`
([energy_system.py:707–717](../zen_garden/model/energy_system.py)):

$$
\delta(y) \;=\; \sum_{i=0}^{\iota(y)-1}\Bigl(\tfrac{1}{1+r}\Bigr)^{\mathrm{dy}\,(y-y_0)+i},
\qquad \iota(y)=\begin{cases}1 & y=\text{letztes Jahr}\\ \mathrm{dy} & \text{sonst}\end{cases}
$$

Der gesamte **diskontierte, annualisierte CAPEX-Beitrag pro Einheit Zubau** ist
damit der effektive Zielkoeffizient von $\Delta S_{h,n,y_\text{inv}}$:

$$
K(y_\text{inv}) \;=\; \alpha_{h,n,y_\text{inv}}\; \underbrace{a_h \sum_{y\in\mathrm{PY}}\delta(y)}_{=\,\sigma\;([postprocess.py:587])} \;=\; \alpha_{h,n,y_\text{inv}}\cdot \sigma.
$$

### A.2 Werteseite aus dem Lifetime-Dual

Für eine nicht-basische Variable an der unteren Schranke lautet die
LP-Optimalitätsbedingung (Minimierung, KKT/Reduced-Cost):

$$
d_j \;=\; c_j \;-\; \sum_i A_{ij}\,\lambda_i \;\ge\; 0,
$$

wobei $c_j$ der Zielkoeffizient, $A_{ij}$ die Constraint-Koeffizienten und
$\lambda_i$ die zugehörigen Duale sind. Wir setzen den **effektiven**
Zielkoeffizienten $c_j=K(y_\text{inv})$ aus §A.1 ein (die Kette aus §1.1 ist
linear, ihr Nettobeitrag pro Einheit Zubau ist genau $K$).

Aus §1.2(a) ist der Lifetime-Koeffizient $A_{ij}=-1$ in jeder Zeile
$y\in\mathrm{PY}$. Der Beitrag der Lifetime-Duale zu $\sum_i A_{ij}\lambda_i$ ist
also $\sum_{y\in\mathrm{PY}}(-1)\,\lambda^{\text{lt}}_{h,n,y} = -\sum_y \lambda^{\text{lt}}_{h,n,y}$.

Der Code definiert spiegelbildlich
([postprocess.py:598–608](../zen_garden/postprocess/postprocess.py)):

$$
\text{elec\_value} \;=\; \sum_{y\in\mathrm{PY}} \bigl(-\lambda^{\text{lt}}_{h,n,y}\bigr) \;=\; -\sum_{y\in\mathrm{PY}} \lambda^{\text{lt}}_{h,n,y}.
$$

Folglich ist $\text{elec\_value}$ **exakt der Lifetime-Anteil von
$\sum_i A_{ij}\lambda_i$**. Ökonomisch: $-\lambda^{\text{lt}}$ ist der marginale
Systemwert einer Einheit Kapazität in Jahr $y$ (die Lifetime-Gleichung „liefert"
Kapazität, die in der kapazitätsbeschränkten Operation Wert hat). Da Kapazität
wertvoll ist, ist $\lambda^{\text{lt}}\le 0$ und damit $\text{elec\_value}\ge 0$.

> Die NaN-Behandlung in dieser Schleife
> ([postprocess.py:609–611](../zen_garden/postprocess/postprocess.py)) ist
> ökonomisch begründet: Ist die Lifetime-Zeile dual degeneriert (NaN, weil eine
> Diffusions-Constraint die aktive Schranke ist), wird der Beitrag als $0$
> behandelt — der Wert steckt dann im Diffusionsterm (§A.3).

### A.3 Diffusionsbeitrag (Wissensbasis + Spillover)

Aus §1.2(b): $\Delta S_{h,n,y_\text{inv}}$ erscheint in jeder zukünftigen
Diffusions-Constraint ($y_\text{fut}>y_\text{inv}$) mit Koeffizient
$A_{ij}=-\text{tdr}_{h,y_\text{fut}}\,\text{kdr}_h(y_\text{inv}\!\to\!y_\text{fut})$.
Mit $\text{coeff} \equiv \text{tdr}\cdot\text{kdr}$
([postprocess.py:654](../zen_garden/postprocess/postprocess.py)) akkumuliert der
Code ([postprocess.py:658–692](../zen_garden/postprocess/postprocess.py)):

$$
\text{diff\_contribution} \;=\;
\sum_{y_\text{fut}>y_\text{inv}}
\Bigl[
\underbrace{\mu^{\text{tot}}_{h,y_\text{fut}}\,\text{coeff}}_{\text{total, [:665]}}
\;+\;
\underbrace{\mu^{\text{an}}_{h,n,y_\text{fut}}\,\text{coeff}}_{\text{same-node, [:677]}}
\;+\;
\underbrace{\sum_{n'\neq n}\mu^{\text{an}}_{h,n',y_\text{fut}}\,\text{tdr}\,\omega_h\,\text{kdr}}_{\text{cross-node, [:679–692]}}
\Bigr].
$$

- Der **Total**-Term ([postprocess.py:658–665](../zen_garden/postprocess/postprocess.py))
  hat keine Knotendimension (über Knoten summierte Constraint,
  [technology.py:1734](../zen_garden/model/technology/technology.py)).
- Der **Same-Node**- und **Cross-Node**-Term existieren nur bei endlichem
  $\omega_h$ ([postprocess.py:668](../zen_garden/postprocess/postprocess.py),
  Guard `not np.isinf(sr)`), entsprechend dem Spillover-Zweig
  [technology.py:1752](../zen_garden/model/technology/technology.py).
- $\text{kdr}$ ([postprocess.py:641](../zen_garden/postprocess/postprocess.py)) und
  $\text{tdr}$ ([postprocess.py:650](../zen_garden/postprocess/postprocess.py))
  sind identisch zu [technology.py:1628](../zen_garden/model/technology/technology.py)
  bzw. [:1581](../zen_garden/model/technology/technology.py).

Da die Diffusions-Constraints `<=` sind, gilt im Min-Problem
$\mu^{\text{diff}}\le 0$. Mit $\text{coeff}>0$ ist
$\text{diff\_contribution}\le 0$. **Ökonomische Deutung:** Bauen *heute* erhöht
die Wissensbasis und **lockert** zukünftige Diffusionslimits — das senkt den
Reduced Cost (siehe Code-Kommentar
[postprocess.py:616–617](../zen_garden/postprocess/postprocess.py)).

### A.4 Zusammenführung

Der Diffusionskoeffizient ist negativ ($A_{ij}=-\text{coeff}$), daher ist sein
Beitrag zu $\sum_i A_{ij}\lambda_i$ gleich $-\text{diff\_contribution}$. Einsetzen
in die Optimalitätsbedingung mit $c_j=K=\alpha\sigma$:

$$
\begin{aligned}
d &= c_j - \sum_i A_{ij}\lambda_i
   = \alpha\sigma \;-\;\Bigl[\underbrace{-\text{elec\_value}}_{\text{lifetime}} \;+\; \underbrace{(-\text{diff\_contribution})}_{\text{diffusion}}\Bigr] \\[4pt]
  &= \alpha\sigma \;-\; \bigl(\text{elec\_value} - \text{diff\_contribution}\bigr).
\end{aligned}
$$

$d$ ist der Reduced Cost in **NPV-/Modelleinheiten**. Division durch $\sigma$
liefert den Code-Ausdruck in **CAPEX-Einheiten**:

$$
\boxed{\;\text{rc\_capex\_equivalent} = \frac{d}{\sigma} = \alpha_{h,n,y_\text{inv}} - \frac{\text{elec\_value}-\text{diff\_contribution}}{\sigma}\;}
\quad\text{— exakt [postprocess.py:695].}
$$

**Interpretation.** Für eine gebaute Technologie ist $d=0$ (basisch, Kosten =
Wert) $\Rightarrow$ `rc_capex_equivalent` $=0$. Für eine unrentable ist $d>0$, und
$d/\sigma$ ist **genau** der Betrag, um den $\alpha$ fallen müsste, damit $d=0$
wird — also die gesuchte CAPEX-Senkung in CAPEX-Einheiten. Die Division durch
$\sigma$ macht das Maß invariant gegen Lebensdauer/Diskontierung und damit über
Technologien vergleichbar.

### A.5 Einheitenkette → €/kW

ZEN-garden speichert `capex_specific` intern als
$\text{input} \times f$ (`fraction_year`), siehe Kommentar
[postprocess.py:767–771](../zen_garden/postprocess/postprocess.py). Da
`rc_capex_equivalent` das interne $\alpha$ verwendet, ist es in internen
Einheiten. Rückumrechnung
([postprocess.py:773–777](../zen_garden/postprocess/postprocess.py)):

$$
f = \frac{\text{unaggregated\_time\_steps\_per\_year}}{\text{total\_hours\_per\_year}},
\qquad
\text{rc\_capex\_equivalent\_input\_units} = \frac{\text{rc\_capex\_equivalent}}{f}.
$$

Ist das Modell zeitlich nicht aggregiert, gilt $f=1$ und beide Spalten sind
gleich (Hinweis [postprocess.py:769–771](../zen_garden/postprocess/postprocess.py)).
**`rc_capex_equivalent_input_units` [€/kW] ist das Primärergebnis.**

### A.6 Konsistenz-Check gegen `save_rc_components`

`save_rc_components` ([postprocess.py:791–1002](../zen_garden/postprocess/postprocess.py))
schreibt pro Beitrag eine Zeile mit
`contribution_to_rc`:

- Lifetime ([postprocess.py:917](../zen_garden/postprocess/postprocess.py)):
  $\lambda^{\text{lt}}_{y}/\sigma$ (coefficient $1{,}0$).
- Diffusion total/an ([postprocess.py:969](../zen_garden/postprocess/postprocess.py)/[:989](../zen_garden/postprocess/postprocess.py)):
  $\mu\cdot\text{coeff}/\sigma$.

Summe plus `capex_specific`:

$$
\alpha + \sum \text{contribution\_to\_rc}
= \alpha + \frac{\sum_y\lambda^{\text{lt}}_y + \sum\mu\cdot\text{coeff}}{\sigma}
= \alpha - \frac{\text{elec\_value}-\text{diff\_contribution}}{\sigma},
$$

was **exakt `rc_capex_equivalent` reproduziert** — die Herleitung ist intern
konsistent (Doc-String-Behauptung [postprocess.py:816–819](../zen_garden/postprocess/postprocess.py)
bestätigt).

> ⚠️ **Eine dokumentierte Ausnahme.** `save_rc_components` schreibt **keinen**
> Cross-Node-Spillover-Beitrag (der Block [postprocess.py:679–692] fehlt im
> Komponenten-Export). `_compute_rc_capex_equivalent` enthält ihn dagegen. Die
> Abstimmung „Summe der Komponenten + CAPEX = `rc_capex_equivalent`" stimmt daher
> **nur exakt**, wenn $\omega_h=\infty$ (dann fällt `diffusion_an` in *beiden*
> Funktionen weg) **oder** bei nur einem Knoten. Bei endlichem Spillover mit
> mehreren Knoten ist `rc_components.csv` um die Cross-Node-Terme zu niedrig in
> der Rekonstruktion. Für Audits relevant; für das Primärergebnis
> `rc_capex_equivalent` unkritisch (dort ist der Term enthalten).

### A.7 Vollständigkeit: warum genau zwei Dual-Familien genügen

`capacity_addition` steht in **mehr** Constraints als nur Lifetime und Diffusion —
per Code-Audit auch in: `constraint_capacity_coupling`
([conversion_technology.py:837](../zen_garden/model/technology/conversion_technology.py)),
`constraint_cost_capex_yearly`/`…_total`/`constraint_net_present_cost`,
`constraint_capacity_investment` (Construction-Time,
[technology.py:1444](../zen_garden/model/technology/technology.py)),
`constraint_technology_min_capacity_addition`/`…_max_…`
([technology.py:1315](../zen_garden/model/technology/technology.py)/[:1351](../zen_garden/model/technology/technology.py)),
`constraint_technology_lifetime_previous`
([technology.py:1529](../zen_garden/model/technology/technology.py)).

Der **vollständige** Reduced Cost ist $d = c_{\Delta S} - \sum_i A_i\,\lambda_i$ über
*alle* diese $i$. Dass das Skript nur Lifetime + Diffusion liest, ist trotzdem
erschöpfend, weil sich die Constraint-Menge sauber in drei Klassen zerlegt:

**(a) Kostenkette — analytisch erfasst, nicht über Duale.** Die Gleichungen
`capacity_coupling → capex_coupling → cost_capex_yearly → …_total →
net_present_cost` definieren *freie Hilfsvariablen* und lassen sich aus dem LP
**heraussubstituieren** (Standard-LP-Transformation; ändert weder Optimum noch die
Reduced Costs der übrigen Variablen). Nach der Substitution trägt $\Delta S$ den
Zielkoeffizienten $K=\alpha\sigma$ — genau die geschlossene Form aus §A.1. Ihre
Duale werden also nicht ignoriert, sondern ihr Beitrag ist analytisch ausgerechnet.

**(b) Wert-Constraints — als Duale gelesen.** Nach (a) verbleiben als einzige
Constraints mit $\Delta S$: **Lifetime** (Koeff. $-1$) und **Diffusion**
(Koeff. $-\text{tdr}\cdot\text{kdr}$). Genau deren Duale nutzt §A.2/§A.3.

**(c) Restliche Constraints — beweisbar Dual $=0$ an einer ungebauten Technologie:**

| Constraint | Grund für Beitrag $=0$ |
|---|---|
| `max_capacity_addition` | Unrentable Technologie *will* nicht mehr bauen → Cap effektiv inaktiv → Dual 0. Bindet er, ist die Technologie *gebaut* → `rc_capex ≈ 0` ohnehin. |
| `min_capacity_addition` | Bei nicht installierter Technologie reduziert sich die Schranke auf $\Delta S\ge0$ → schlaff → Dual 0. |
| `capacity_investment` (Construction-Time) | Reine Umetikettierung $\Delta S\leftrightarrow$ `capacity_investment`; letztere trägt keine eigenen Kosten/Limits → freie Basisvariable → Dual 0. |
| `lifetime_previous` | Definiert `capacity_previous`, das nur in den `market_share_unbounded`-Term der Diffusion eingeht. Bei `market_share_unbounded = 0` → Dual 0. |

**Geltungsbedingungen.** Die Rekonstruktion ist *exakt* unter: (1) linearem Capex
(kein aktiver PWA-Segmentwechsel → $K=\alpha\sigma$ wohldefiniert); (2) keiner
*bindenden* Jahres-Zubaugrenze an der analysierten Zeile; (3) kosten-/limit-neutraler
Construction-Time; (4) `market_share_unbounded = 0`; (5) `lifetime =
depreciation_time` (sonst weichen die Lifetime-Constraint-Jahre,
[technology.py:1499](../zen_garden/model/technology/technology.py), von den
`pay_years`, [postprocess.py:582](../zen_garden/postprocess/postprocess.py), ab). Für
eine ungebaute, unrentable Technologie sind (1)–(5) praktisch immer erfüllt →
Lifetime + Diffusion sind die **erschöpfende** Dual-Menge. Verletzt eine Annahme,
fehlt ein Term und der RC wird zur Näherung (siehe §D.4). Der prüffreie Beleg, dass
nichts fehlt: §B.3.

---

## B. Warum die native Gurobi-RC-Variante nicht genügt

Die „mathematisch saubere", in Gurobi eingebaute Variante wäre: Reduced Cost
direkt über das `RC`-Attribut auslesen
(`save_reduced_costs`, [postprocess.py:446](../zen_garden/postprocess/postprocess.py)).
Das **scheitert** für `capacity_addition` an den *degeneriert-basischen* Stellen
(`vbasis = 0`): dort ist der native RC mechanisch **0** (§B.1). An *nicht-basischen*
Stellen (`vbasis = -1`) ist er dagegen korrekt — und stimmt dann exakt mit der
dual-basierten Rekonstruktion überein (§B.3).

### B.1 Ursache: primale Degeneriertheit durch die Lifetime-Gleichung

Drei LP-Grundregeln:

1. Eine Basis hat genau $m$ basische Variablen ($m$ = Zahl der Constraint-Zeilen);
   die Basismatrix muss invertierbar sein.
2. Jede Gleichungszeile muss aufgespannt sein → **mindestens eine** ihrer
   Variablen muss basisch sein.
3. **Basische Variable $\Rightarrow$ Reduced Cost $=0$**, per Definition.

Die Lifetime-Gleichung (§1.2a) existiert **pro (Technologie, Knoten, Jahr)** —
tausende Gleichungen, jede zwingt eine ihrer Variablen in die Basis. Der Crossover
greift dabei häufig `capacity_addition`; ist nichts gebaut, ist sie eine
**degenerierte Basisvariable bei Wert 0** → nativer RC $=0$, obwohl die
Technologie ökonomisch weit vom Bau entfernt ist. (Ausführliche Herleitung und
Zahlenbeispiel: [`rc_analysis_known_issues.md` §Problem 1](rc_analysis_known_issues.md).)

### B.2 Der entscheidende Unterschied

| | Nativer Gurobi-RC | Dual-basiertes Skript |
|---|---|---|
| **Informationsquelle** | Basis-**Status** der Variablen | Constraint-**Duale** |
| **Robust gegen primale Degeneriertheit?** | **Nein** — Basisstatus ist genau das, was kaputtgeht | **Ja** — Duale bleiben verlässlich |
| **Misst** | RC im vollen LP (inkl. aller Kopplungs-Constraints), $c_j=0$ | ökonomischen CAPEX-Abstand $d/\sigma$ |
| **Ergebnis** | ≈ 0 fast überall → unbrauchbar | €/kW-Abstand zum Bau |

Die wirtschaftliche Information steckt **nicht** im Basisstatus, sondern im
Lifetime-Dual $\lambda^{\text{lt}}$. Das Skript liest genau diesen aus
([postprocess.py:529](../zen_garden/postprocess/postprocess.py)) und rekonstruiert
$d$ über §A. Auch `vbasis` (im CSV,
[postprocess.py:749–757](../zen_garden/postprocess/postprocess.py)) ist deshalb
**kein** Wirtschaftlichkeitssignal, sondern nur ein Buchhaltungs-Tie-Break (welche
Seite der Gleichung der Crossover basisch macht).

> **Kurz:** Der native RC ist nicht „falsch" — er beantwortet eine andere Frage in
> einem degenerierten Modell. Wir brauchen den *ökonomischen* CAPEX-Abstand, und
> der ist nur über die Duale stabil zugänglich.

### B.3 Wo der native RC korrekt ist — und die Kreuzvalidierung

Die Perturbation (§C) schiebt ungebaute `capacity_addition` von `vbasis = 0`
(degeneriert-basisch) nach `vbasis = -1` (nicht-basisch an der unteren Schranke).
**An nicht-basischen Zeilen ist der native Gurobi-RC wohldefiniert und korrekt** —
und identisch mit der dual-basierten Rekonstruktion, nur in anderen Einheiten:

$$
\text{nativer reduced\_cost} \;=\; d \;=\; \text{rc\_capex\_equivalent}\times\sigma.
$$

**Durchgerechnet** (`photovoltaics, power, IE, 0` aus
`Baseline_Crystalball_Snapshot2050`; 1-Jahres-Snapshot $\Rightarrow \delta=1
\Rightarrow \sigma = a_{\text{PV}} = \text{CRF}$):

| Spalte | Wert |
|---|---|
| `value` | $0$ (ungebaut) |
| `vbasis` | $-1$ (nicht-basisch) |
| `reduced_cost` (nativ, $=d$) | $1{,}55971$ |
| `rc_capex_equivalent` ($=d/\sigma$) | $23{,}97658$ €/kW |

Probe: $23{,}97658 \times 0{,}0650514 = 1{,}55971$ (auf 6 Stellen;
$\text{CRF}_{\text{PV}}$ für $r=5\%,\,n=30$). Das ist die stärkste
*modellunabhängige* Bestätigung der gesamten §A-Herleitung: Gurobis **eigener**
nativer RC — der *implizit alle* Constraints enthält (auch die in §A.7 als Dual-0
argumentierten) — reproduziert exakt $d=\text{rc\_capex\_equivalent}\times\sigma$.
Nativer RC und Skript sind **dieselbe Größe**, keine Konkurrenten; das Skript ergänzt
nur die `vbasis = 0`-Zeilen, an denen der native RC kollabiert.

> Hinweis: Die zitierte CSV stammt aus einer Code-Version mit Zusatzspalten
> (`reduced_cost`, `…_per_kw_eff`), die der aktuelle
> `save_capacity_addition_analysis` nicht erzeugt. Die Relation
> nativ $=$ rekonstruiert $\times\sigma$ ist davon unabhängig (reine LP-Identität).

---

## C. Die Rolle der Perturbation $+\varepsilon\sum \Delta S$

Code: `perturb_objective_for_rc`
([optimization_setup.py:663–692](../zen_garden/optimization_setup.py)), aufgerufen
in [runner.py:144](../zen_garden/runner.py) **nach** dem Modellaufbau und **vor**
Skalierung/Solve. Aktiviert über `solver_options["rc_perturbation"]`
([main_rc_simplex.py:67](../main_rc_simplex.py), Wert `1e-4`).

$$
\min\; \text{NPC} \;+\; \varepsilon \sum_{h,n,y}\Delta S_{h,n,y}, \qquad \varepsilon = 10^{-4}.
$$

### C.1 Das Problem: duale Degeneriertheit an ungebauten Technologien

An einer ungebauten Technologie ist die Lifetime-Gleichung degeneriert: Die
Aufteilung der CAPEX-Zurechnung zwischen dem **Lifetime-Dual** und dem
**Linear-CAPEX-Dual** ist ein **objective-flacher Freiheitsgrad** — eine ganze
*degenerierte Dual-Fläche* von Optima. Welchen Endpunkt der Solver greift, ist
numerischer Tie-Break, keine Ökonomie. Das trifft **auch das dual-basierte Skript**,
denn der ausgelesene $\lambda^{\text{lt}}$ kann je nach Ecke variieren (siehe
[`rc_analysis_known_issues.md` §Problem 3](rc_analysis_known_issues.md)).

### C.2 Was $+\varepsilon$ wirklich tut — und was nicht

> ⚠️ **Korrektur.** Frühere Fassungen — und der Doc-String
> [optimization_setup.py:663–678](../zen_garden/optimization_setup.py) — behaupteten,
> $\varepsilon$ *selektiere den korrekten Dual-Endpunkt*. Das ist **falsch** und
> widerspricht [Known Issues §Problem 3](rc_analysis_known_issues.md:186).

$\varepsilon$ kann den Dual-Endpunkt **nicht durch Optimierung** wählen, denn die
**Dual-Zielfunktion ist flach in $\lambda^{\text{lt}}$**: ihr Koeffizient ist die
Primal-RHS der Lifetime-Gleichung, und die ist im Greenfield $=0$
([technology.py:1536](../zen_garden/model/technology/technology.py)). $\varepsilon$
steht in den Primal-*Kosten* $c$; es verschiebt die Dual-Nebenbedingungen (das
Intervall), **kippt die flache Dual-Zielfunktion aber nie** → kein Endpunkt wird
bevorzugt, auch nicht im Grenzwert $\varepsilon\to0$ (Nachweis am Minimal-LP: §C.6).

Was $\varepsilon$ **tatsächlich** bewirkt, sind zwei eng begrenzte Dinge:

1. **`vbasis`-Tie-Break (kosmetisch).** Indem $\varepsilon$ dem Zubau strikt positive
   Kosten gibt, *stupst* es den Crossover, $\Delta S$ als **nicht-basisch** (`vbasis`
   $0\to-1$) zu melden. Beide Basen bleiben optimal (§C.6) — eine numerische Tendenz,
   **kein** erzwungener Wechsel.
2. **Primal-Selektion (nur bei echten Alternativ-Optima).** Gibt es mehrere optimale
   Lösungen mit *unterschiedlichem* $\sum\Delta S$, wählt $\varepsilon$ die mit
   minimalem Gesamtzubau — ein *anderer* Vertex, also *andere* Duale. Bei
   *eindeutigem* Primal-Optimum (typischer ungebauter Knoten) greift das nicht.

Der praktische Nutzen ist Punkt 1: Weil der gemeldete Dual basis-konsistent ist, kann
der `vbasis`-Stups den *gemeldeten* $\lambda^{\text{lt}}$ (und damit native RC-Spalte
**und** Skript-Wert) von der Schein-Null auf den Wert-Endpunkt bringen — **als
fragilen Tie-Break, nicht als Garantie.** Das robuste Ergebnis liefern `Presolve=0` +
`Crossover=1` + die dual-basierte Rekonstruktion, nicht $\varepsilon$.

### C.3 Warum die Lösung dadurch nicht verfälscht wird (Grenzwertargument)

Die Perturbation ist eine **lexikografische / Tie-Break-Technik**. Für
$\varepsilon\to 0^+$:

- Das **primale Optimum** bleibt unverändert: Über alle ursprünglich optimalen
  Lösungen wählt $+\varepsilon\sum\Delta S$ diejenige mit *minimaler* Summe der
  Zubauten. Da ungebaute Technologien dort ohnehin $\Delta S=0$ haben, ändert sich
  am Optimalwert nichts (der Zusatzterm ist $O(\varepsilon)$ und am gewählten
  Vertex exakt 0 für die betroffenen Variablen).
- Die optimale Dual-*Menge* bleibt: $\varepsilon$ konvergiert **nicht** gegen einen
  bestimmten Endpunkt (flaches Dual-Ziel, §C.2/§C.6). Welcher Endpunkt *gemeldet*
  wird, ist Basis-/Crossover-Sache, kein Grenzwert.

Deshalb ist $\varepsilon=10^{-4}$ „klein genug, um die Lösung nicht zu stören,
groß genug, um die Symmetrie numerisch zu brechen". Es ist **kein** Modellparameter
mit physikalischer Bedeutung. (Der genaue Geltungsbereich dieses Arguments — und
wann es *nicht* greift — steht in §C.6.)

### C.4 Warum $\varepsilon$ nur über die Basis eingeht

`rc_capex_equivalent` enthält **keinen** expliziten $\varepsilon$-Term — es wird
allein aus $\alpha$, $\sigma$ und den Dualen gebildet (§A). $\varepsilon$ wirkt
ausschließlich **indirekt**, indem es die Basis (`vbasis`) und damit den *gemeldeten*
$\lambda^{\text{lt}}$ beeinflusst (§C.2). Sobald die Basis feststeht, fällt
$\varepsilon$ aus der Formel heraus. Genau das meint der Doc-String mit „enters `rc_capex_equivalent`
only through the basis, not as an explicit term"
([postprocess.py:725–727](../zen_garden/postprocess/postprocess.py)).

### C.5 Implementierungsdetails

- **Key wird gepoppt** ([optimization_setup.py:679](../zen_garden/optimization_setup.py)):
  `solver_options.pop("rc_perturbation")`. Grund: `rc_perturbation` ist **keine**
  Gurobi-Option; würde sie durchgereicht, würde Gurobi mit „unknown parameter"
  abbrechen. Sie wird abgefangen, in einen Zielfunktionsterm übersetzt
  ([optimization_setup.py:685–689](../zen_garden/optimization_setup.py)) und dann
  entfernt, bevor `solver_options` an Gurobi geht
  ([optimization_setup.py:698–702](../zen_garden/optimization_setup.py)).
- **`use_scaling=0`** ([main_rc_simplex.py:61](../main_rc_simplex.py)): Die
  Perturbation wird in [runner.py:144](../zen_garden/runner.py) **vor**
  `run_scaling()` ([runner.py:145–146](../zen_garden/runner.py)) addiert. Bei
  aktiver Skalierung würde $\varepsilon$ mitskaliert und seine effektive Größe
  unkontrolliert verändert. Mit `use_scaling=0` wirkt $\varepsilon$ in **rohen
  Zielfunktionseinheiten** — die Größenordnung $10^{-4}$ ist dann direkt
  interpretierbar.
- **Per Horizont-Schritt**: Der Aufruf steht in der Horizont-Schleife
  ([runner.py:133–144](../zen_garden/runner.py)); bei Rolling Horizon wird in
  jedem Schritt neu perturbiert (für den 1-Jahres-Snapshot: genau einmal).
- **Deaktivierung**: `rc_perturbation = None` (oder Key weglassen) → Frühausstieg
  ([optimization_setup.py:680–681](../zen_garden/optimization_setup.py)), no-op.

### C.6 Geltungsbereich und Grenze

Eine *Zielfunktions*-Perturbation bricht **duale** Degeneriertheit — sie wählt unter
mehreren *Primal*-Optima dasjenige mit minimalem $\sum\Delta S$. Sie kann ein
*echtes* Dual-Intervall bei *eindeutigem* Primal-Optimum (reine **primale**
Degeneriertheit) **nicht** kollabieren. Ein minimales LP zeigt beides.

**Minimal-LP** (1 Jahr, Greenfield, 1 Knoten, $\delta=1\Rightarrow\sigma=a$): zwei
Technologien decken Nachfrage $D$; A billig ($K_A$), B teurer ($K_B>K_A$, die
analysierte ungebaute). Nach Substitution der Kostenkette (§A.7a):

$$
\min\; K_A\Delta S_A + K_B\Delta S_B \quad\text{s.t.}\quad
S_A+S_B\ge D\ (\pi),\quad S_t-\Delta S_t = 0\ (\lambda_t),\quad \text{alle }\ge 0.
$$

Optimum: $\Delta S_A=S_A=D$, $\Delta S_B=S_B=0$, $\pi=K_A$. Optimalität für die auf 0
stehenden B-Variablen ($\text{rc}(\Delta S_B)=K_B+\lambda_B\ge0$,
$\text{rc}(S_B)=-\pi-\lambda_B\ge0$) liefert ein ganzes **Dual-Intervall**:

$$
\lambda_B \in [-K_B,\,-K_A], \qquad \text{rc\_capex} = \alpha_B + \lambda_B/\sigma.
$$

| Endpunkt | Basis-Bild | nativer RC $=d$ | `rc_capex_equivalent` |
|---|---|---|---|
| $\lambda_B=-K_A=-\pi$ | $\Delta S_B$ **nicht-basisch** | $K_B-K_A>0$ | $\alpha_B-\alpha_A$ ✅ korrekt |
| $\lambda_B=-K_B$ | $\Delta S_B$ **basisch(0)** | $0$ | $0$ ❌ Schein-Null |

Beide Basen sind **derselbe Primalpunkt** (degenerierter Pivot); ohne Hilfe ist die
Wahl ein Tie-Break. (An *beiden* Endpunkten gilt nativ $=$ `rc_capex`$\times\sigma$ —
die §A/§B.3-Identität hält immer, nur der *Wert* hängt vom Endpunkt ab.)

**Warum $\varepsilon$ den Endpunkt nicht wählt.** Setzt man $\varepsilon$ ein,
verschiebt sich das Intervall auf $[-(K_B{+}\varepsilon),\,-(K_A{+}\varepsilon)]$, die
**Breite $K_B-K_A$ bleibt** — beide Endpunkte bleiben optimale Basen. Grund: Die
Dual-Zielfunktion $\max\, b^\top y = D\pi + 0\cdot\lambda_B$ ist **flach in
$\lambda_B$** (Lifetime-RHS $=0$). $\varepsilon$ verändert nur die Dual-Nebenbedingungen,
nie den flachen Dual-Zielkoeffizienten → es gibt keinen Optimierungs-Hebel für die
Endpunkt-Wahl. Welcher Endpunkt *gemeldet* wird, entscheidet allein der Crossover.

**Wo $\varepsilon$ trotzdem etwas bewegt — und wo nicht.**

- **Einzelner marginaler Knoten:** Der `vbasis`-Stups bringt den Crossover dazu,
  $\Delta S$ nicht-basisch zu melden → gemeldeter $\lambda_B$ = Wert-Endpunkt →
  Schein-Null verschwindet. *Empirisch* zuverlässig, aber als Tie-Break, nicht
  beweisbar (zur Absicherung: A/B-Test, nur `rc_perturbation` umschalten).
- **Mehrere symmetrische Knoten am selben Break-even (Problem 3):** $\varepsilon$ ist
  *uniform* (gleicher Bump auf jeden Knoten) → kann die Knoten-Symmetrie nicht
  brechen, die Null *wandert*. Hier hilft es **nicht**.

**Der robuste Fix (statt sich auf $\varepsilon$ zu verlassen).**

1. **CAPEX-Jitter** — deterministische, knotenweise Störung $\pm0{,}01$ €/kW auf
   `capex_specific`. *Nicht-uniform* → bricht die Knoten-Symmetrie → eindeutiges
   Primal-Optimum → eindeutige Duale → belastbarer RC überall. Richtiges Werkzeug für
   Problem 3.
2. **Erkennungs-Flag** `rc_unreliable = (|value|<1e-9) ∧ (|rc_capex_equivalent|<1e-6)`
   — nie eine Schein-Null stillschweigend vertrauen.
3. **Bisektion auf CAPEX** (schrittweise senken bis `value>0`) — misst die *wahre*
   Schwelle ohne Duale, also **degeneriertheits-immun**. Ground Truth zur Validierung
   jedes geflaggten Falls.

$\varepsilon$ darf bleiben (harmlos, $O(\varepsilon)$; macht die native RC-Spalte als
Kreuzcheck brauchbar), ist aber **kein** Ersatz für 1–3. Details:
[`rc_analysis_known_issues.md` §Problem 3](rc_analysis_known_issues.md:175).

---

## D. Wann der Code scheitern könnte (Annahmen & Bruchstellen)

### D.1 Solver-Voraussetzungen (ohne sie bricht das Verfahren)

| Voraussetzung | Konfiguriert in | Folge bei Verletzung |
|---|---|---|
| **`Crossover = 1`** | [main_rc_simplex.py:60](../main_rc_simplex.py) | Ohne Vertex-Lösung **keine exakte Basis/Duale** → `vbasis` und ggf. RC = NaN; Barrier-Interior-Duale sind verrauscht. |
| **`Presolve = 0`** | [main_rc_simplex.py:62](../main_rc_simplex.py) | Presolve substituiert genau die Lifetime-Gleichung weg → Dual per Label nicht mehr auslesbar → `dual_lifetime` NaN/falsch → RC unbrauchbar. (Details: [Known Issues §Problem 2](rc_analysis_known_issues.md).) |
| **`save_duals = True`** | [main_rc_simplex.py:57](../main_rc_simplex.py) | Ohne Duale keine Werteseite. |
| **Solver = `gurobi`** | [main_rc_simplex.py:56](../main_rc_simplex.py) | `save_reduced_costs` und `VBasis`/`RC`-Attribute sind Gurobi-spezifisch ([postprocess.py:425](../zen_garden/postprocess/postprocess.py), [:749](../zen_garden/postprocess/postprocess.py)). |
| **`use_scaling = 0`** *(oder `D_r_inv`-Rückkorrektur)* | [main_rc_simplex.py:61](../main_rc_simplex.py) | Bei aktiver Skalierung müssen Duale mit `D_r_inv` zurückskaliert werden ([postprocess.py:530–532](../zen_garden/postprocess/postprocess.py)); zusätzlich verändert Skalierung das wirksame $\varepsilon$ (§C.5). |

> ⚠️ **Doc-String-vs.-Config-Diskrepanz.** Der Datei-Header von `main_rc_simplex.py`
> behauptet „Primal Simplex (Method=0)"
> ([main_rc_simplex.py:2–8](../main_rc_simplex.py)), die Live-Config setzt jedoch
> **`Method = -1`** (automatisch, [main_rc_simplex.py:59](../main_rc_simplex.py)).
> Das ist **kein Fehler**, aber die Begründung im Header stimmt nicht mehr: Exakte
> Duale garantiert hier **`Crossover = 1`** (Vertex-Lösung), nicht eine bestimmte
> Methode. Bei sehr großen Modellen wählt `Method=-1` oft Barrier+Crossover.

### D.2 Echte (duale) Degeneriertheit — Restrisiko trotz Perturbation

Die Perturbation (§C) bricht die Symmetrie an *einzelnen* ungebauten
Technologien. Den Grenzfall **„mehrere Knoten am exakt selben Break-even"**
(uniforme CAPEX → mehrere optimale Dual-Ecken) löst sie **nicht garantiert**: Ein
marginaler Knoten kann weiterhin eine irreführende **exakte 0** liefern, und
welcher Knoten „auf 0 sitzt", kann zwischen Läufen *wandern* (Fingerabdruck von
Alternativ-Optima). Vollständige Herleitung inkl. bit-genauer Null und
empfohlener Symmetriebrechung (Mini-Jitter $\pm0{,}01$ €/kW auf node-resolved
CAPEX): [`rc_analysis_known_issues.md` §Problem 3](rc_analysis_known_issues.md).

**Erkennungsheuristik:** `rc_unreliable = (|value| < 1e-9) ∧ (|rc_capex_equivalent| < 1e-6)`.

### D.3 Numerische / strukturelle Bruchstellen im Skript

- **Breites `except`** ([postprocess.py:698–699](../zen_garden/postprocess/postprocess.py)):
  *jede* Exception pro Zeile → `np.nan`, ohne Logging. Fehlende Parameter,
  unerwartete Indexformen oder Solver-Eigenheiten erscheinen **stumm** als NaN
  statt als Fehler. Bei flächigen NaN zuerst diesen Block verdächtigen.
- **Fehlende `capex_specific`-Lookups** ([postprocess.py:592–596](../zen_garden/postprocess/postprocess.py)):
  Findet die Lookup-Tabelle (gebaut aus `capex_specific_{conversion,storage,transport}`,
  [postprocess.py:553–568](../zen_garden/postprocess/postprocess.py)) keinen
  Eintrag → NaN. Greift z. B. bei Technologien mit nicht-konstantem (PWA-)CAPEX,
  wo kein einzelnes $\alpha$ existiert.
- **`scaling <= 0`** ([postprocess.py:588–590](../zen_garden/postprocess/postprocess.py)):
  z. B. wenn keine pay_years existieren → NaN (Division undefiniert).
- **NaN-Duale** ([postprocess.py:533](../zen_garden/postprocess/postprocess.py),
  [:609–611](../zen_garden/postprocess/postprocess.py)): `dropna()` entfernt
  degenerierte Lifetime-Zeilen; deren Beitrag wird 0 gesetzt (ökonomisch
  vertretbar, §A.2, aber bei massenhaftem Auftreten ein Warnsignal für §D.2).
- **`fraction_year` Edge Cases** ([postprocess.py:773–780](../zen_garden/postprocess/postprocess.py)):
  Fehlende `system`-Felder → `input_units`-Spalte NaN. Bei $f=1$ identisch zur
  internen Spalte (kein Fehler, nur Hinweis).
- **`rc_perturbation_eps` ungenutzt**: Wird gesetzt
  ([optimization_setup.py:684](../zen_garden/optimization_setup.py)), aber im
  Postprocessing **nie ausgelesen**. Der im Header angekündigte „reduced_cost
  minus eps"-Korrekturwert ([main_rc_simplex.py:66](../main_rc_simplex.py),
  [optimization_setup.py:682–683](../zen_garden/optimization_setup.py)) ist
  **nicht implementiert** → der native `reduced_cost` in `reduced_costs_dict`
  enthält das `+eps` unkorrigiert. Für das Primärergebnis irrelevant (es nutzt den
  nativen RC nicht), aber relevant, falls jemand den nativen RC interpretiert.

### D.4 Modell-Konfigurationen, in denen Annahmen kippen

- **Brownfield (`existing_capacities ≠ 0`)**: Die saubere Gleichung
  $S=\sum\Delta S$ wird zu $S=\sum\Delta S + s^{\text{ex}}$
  ([technology.py:1535](../zen_garden/model/technology/technology.py)). Die
  $d$-Herleitung bleibt formal gültig (konstanter RHS-Shift), aber der
  Break-even-Begriff vermischt sich mit Bestandskapazität — Interpretation mit
  Vorsicht.
- **Multi-Year vs. 1-Jahres-Snapshot**: Im Snapshot ist
  $\delta(\text{einziges Jahr})=1$ und $\sigma=a_h$ — die bit-genaue Null aus §D.2
  tritt dann besonders leicht auf. Multi-Year glättet das, kann aber die
  Lifetime-/Diffusions-Kopplung über Jahre verschränken (mehr NaN-Duale).
- **Ohne Diffusions-Constraints** (`max_diffusion_rate = ∞`): `diff_contribution`
  fällt komplett weg ([technology.py:1587–1588](../zen_garden/model/technology/technology.py)
  überspringt den Constraint) → RC rein lifetime-basiert. Korrekt, aber dann
  fehlt der Wissensbasis-Wert; relevant nur, falls Diffusion ökonomisch bindet.
- **Endlicher Spillover + mehrere Knoten**: Cross-Node-Term aktiv → §A.6-Caveat
  (Komponenten-Export unvollständig).
- **PWA-/segmentierter CAPEX**: Kein eindeutiges $\alpha$ → Lookup-NaN (§D.3).

---

## Cheat-Sheet: Solver-Konfiguration

| Einstellung | Wert | Zweck | Quelle |
|---|---|---|---|
| `save_duals` | `True` | Werteseite (Lifetime-/Diffusions-Duale) | [main_rc_simplex.py:57](../main_rc_simplex.py) |
| `save_reduced_costs` | `True` | nativen RC + `VBasis` exportieren (Kontrast/Diagnose) | [main_rc_simplex.py:58](../main_rc_simplex.py) |
| `Method` | `-1` | automatische Methode (Header sagt „0" — veraltet, §D.1) | [main_rc_simplex.py:59](../main_rc_simplex.py) |
| `Crossover` | `1` | **Vertex-Lösung → exakte Duale** (der eigentliche Garant) | [main_rc_simplex.py:60](../main_rc_simplex.py) |
| `use_scaling` | `0` | Duale + $\varepsilon$ in Originaleinheiten | [main_rc_simplex.py:61](../main_rc_simplex.py) |
| `Presolve` | `0` | Lifetime-/Diffusions-Duale per Label auslesbar halten | [main_rc_simplex.py:62](../main_rc_simplex.py) |
| `rc_perturbation` | `1e-4` | dualen Endpunkt an ungebauten Technologien selektieren | [main_rc_simplex.py:67](../main_rc_simplex.py) |

## Checkliste: Wann ist der ausgegebene RC vertrauenswürdig?

Pro Zeile in `capacity_addition_analysis.csv`:

- ✅ **`value > 0`** → gebaut; `rc_capex_equivalent ≈ 0` erwartet und korrekt.
- ✅ **`value = 0` und `rc_capex_equivalent > 0`** → ehrlich unrentabel; der Wert
  ist die benötigte CAPEX-Senkung in €/kW. **Verlässlich.**
- ⚠️ **`value = 0` und `rc_capex_equivalent ≈ 0`** → Warnsignal für duale
  Degeneriertheit (§D.2). **Nicht interpretieren**; wahre Schwelle per
  Perturbation/Bisektion messen oder Symmetrie brechen.
- ⚠️ **`rc_capex_equivalent = NaN`** → eine Bruchstelle aus §D.3 (fehlender
  Lookup, NaN-Dual, `scaling ≤ 0`, oder das stumme `except`).
- 🚫 **`vbasis`** ist **kein** Wirtschaftlichkeitssignal (§B.2) — nicht zur
  Degeneriertheits-Erkennung verwenden.

Voraussetzungen-Quickcheck (sonst ist die *gesamte* Spalte unzuverlässig):
`gurobi` + `Crossover=1` + `Presolve=0` + `save_duals=True`
(siehe `solver.log` / `solver.json` zur Verifikation).

---

*Querverweise: [`rc_analysis_known_issues.md`](rc_analysis_known_issues.md) für die
Degeneriertheits-Probleme und ihre Symptome; dieses Dokument für Herleitung und
Aufbau der Berechnung.*
