# Discussion draft — How usable are these reduced costs?

*Draft text for §6 (Discussion). English, report voice. Grounded in `fig:pv-ramp` (showcase)
and the Crystal-Ball findings (`docs/rc_crystalball_conversion_failure.md`). Not yet in the
.tex. Two core arguments (the user's), sharpened and connected to our results.*

---

### Argument 1 — A reduced cost is a tipping point, not a deployment forecast

> A reduced cost answers a single, marginal question: by how much must a technology's cost
> fall before it *begins* to enter the optimal solution. It says nothing about how much
> capacity is then built, nor how steeply deployment scales as the cost falls further.
> Figure~\ref{fig:pv-ramp} makes this concrete for photovoltaics in DE: lowering its
> \ac{CAPEX} to the reduced cost (86\,EUR/kW, \SI{17.5}{\percent}) admits the first new unit,
> but installed capacity then grows only gradually --- about \SI{58}{\giga\watt} at a
> \SI{26}{\percent} reduction, \SI{128}{\giga\watt} at \SI{47}{\percent}, and the
> \SI{250}{\giga\watt} hard limit only as \ac{CAPEX} approaches zero. The reduced cost
> locates the threshold on the cost axis; the slope above it and where it tops out are set by
> the system (export capacity, build limits, the variability of \ac{PV}) and are deliberately
> outside a first-order quantity. Any statement about *relevant-scale* deployment therefore
> requires a re-solve at the reduced cost --- it cannot be read off the reduced cost itself.

### Argument 2 — The first-unit-to-relevant-build gap is mild for robust technologies, severe for self-cannibalizing ones

> How far the "first unit" threshold sits from a *relevant* build depends on whether the
> technology moves the prices it earns. For a price-taker in a well-connected node the
> post-threshold ramp is smooth, so the reduced cost is also a good guide to where meaningful
> build begins (\ac{PV} in DE). For a technology whose own entry shifts its price --- baseload
> at an import-constrained node, flexible demand on cheap surplus --- the marginal unit sits on
> a knife-edge: its value is a scarcity rent that the first finite build extinguishes. The
> reduced cost still marks where the *infinitesimal* unit becomes attractive, but relevant-scale
> build needs a far larger cost cut (nuclear at ES: a reconstructed \SI{2.3}{\percent} versus a
> true ${>}\,\SI{11.8}{\percent}$). Because the optimal-cost function is convex in capacity, the
> reduced cost can only ever *under*-state this distance --- it is a lower bound, never a pessimistic
> one. The same marginal-versus-finite axis that produces the gentle \ac{PV} ramp produces, at its
> extreme, an over-optimistic closeness signal; the firm gas turbine in the showcase keeps it at
> the mild end by pinning a unique price, an anchor that the bare Crystal-Ball nodes lack.

### Argument 3 — As a screening signal it is most informative at the two ends of the spectrum

> The natural use is therefore triage across a large (technology, node, year) space, where the
> reduced cost is a cheap first pass that decides which cells deserve an expensive re-solve. It is
> most trustworthy at the extremes. At the far end, a relative reduction above one (``never built
> even at zero \ac{CAPEX}'') is a robust, correctly-classified verdict: the technology is far from
> competitive and needs no further attention. At the near end, a small reduction flags a candidate
> that is close to entering the solution and is worth a closer look --- with the caveat from
> Argument~2 that, at degenerate nodes, ``close'' is a lower bound and may be optimistic. The
> least informative region is the broad middle, and the degenerate cells within it are exactly the
> ones the perturbation-sensitivity flag isolates (a reduced cost that moves between a clean and a
> perturbed solve is not to be trusted as a point value).

### Argument 4 — The precise "when and how much" always comes from a targeted re-solve

> In every case the step from a reduced cost to an actual deployment statement --- the exact
> threshold, and how much builds beyond it --- is made by re-solving, not by the reduced cost. The
> $\pm 1\%$ build/nobuild bisection recovers the threshold exactly and is degeneracy-immune; a
> one-parameter \ac{CAPEX} sweep (as in Figure~\ref{fig:pv-ramp}) recovers the deployment curve.
> The value of the reduced cost is not that it removes these re-solves but that it makes them
> *rare and targeted*: from one solve it ranks a whole technology fleet, so the re-solves are spent
> only on the handful of cells that the screening flags as close --- or as degenerate.

### Argument 5 — When the signal is genuinely useful

> The reduced cost is most useful precisely where a full sweep is infeasible: large screening
> exercises over many technologies, nodes and years, where the question is the relative one ---
> *which* options are almost competitive and *which* are hopeless --- rather than an exact capacity.
> It answers that question cheaply, consistently across the three cost drivers (\ac{CAPEX}, fixed
> \ac{OPEX}, \ac{CF}; Table~\ref{tab:pvclones}), and from a single solve. Its limits are equally
> clear and should be stated alongside it: it is a marginal, ceteris-paribus, lower-bound signal
> that is exact for robust price-takers, optimistic at price-degenerate nodes, and silent on
> deployment magnitude --- so it is a guide to where to look, not a substitute for looking.

---

## Notes for integration
- **Connect to §5.1, not duplicate.** Arg. 2 is the conversion/price analogue of the transport
  marginal-vs-finite paragraph already in §5.1; phrase as ``the same effect, now triggered by
  price degeneracy that the showcase deliberately avoided''.
- **Existing Discussion hooks covered:** ``when genuinely useful'' (Arg. 5), ``limits: degeneracy''
  (Arg. 2/3), ``what would have to change'' (firm capacity / flagging / perturbation where needed —
  Arg. 2/3/4), ``generalisability'' (Arg. 5).
- **Solid vs pending:** all five arguments are solid from existing results; the Crystal-Ball
  positive screening claim (Arg. 3/5) is reinforced by the running 5-case validation.
- **Numbers to re-check before final:** PV-DE ramp values (86 EUR/kW, 17.5%, 58/128/250 GW) from
  `fig:pv-ramp`; nuclear ES 2.3% vs >11.8% from the CB validation.

---

## Candidate further additions to the Discussion (brainstorm — pick what fits ~1–2 p)

*Priorität: ★★★ stark/eigenständig · ★★ gut · ★ optional/Outlook. Die 5 Kern-Argumente sind
schon in `06_Discussion.tex`; das hier ist die Auswahl-Liste für „was noch".*

**Ehrliche Garantie / Risiko (spin)**
- ★★★ **Die untere-Schranke-Eigenschaft als (bescheidene) Garantie.** Der Fehler hat *immer dieselbe
  Richtung*: die RC unterschätzt die Distanz nie überschätzt sie. ⇒ sie erklärt eine Tech **nie
  fälschlich für hoffnungslos**, höchstens fälschlich für „nah dran". Fürs Screening ist genau das
  der *sichere* Fehler (die nahen werden ohnehin nachgerechnet). Starkes, positives Framing.
- ★★ **Missbrauchsrisiko / Guard-Rails.** Eine kleine RC als „bau das" zu lesen ist der typische
  Fehler. Empfehlung: RC immer *mit* Reliability-Flag und als untere Schranke ausgeben, nie als
  Ausbaumenge.
- ★★ **Die zwei Modelle als Methodik-Bogen.** Showcase ist *konstruiert*, um Preis-Degeneration zu
  vermeiden (Firm-Gasturbine); CB legt sie offen. Zusammen umreißen sie exakt die Verlässlichkeits-
  Grenze — schöner Meta-Punkt.

**Einordnung / Literatur**
- ★★ **Verhältnis zu Near-Optimal / MGA.** RC = billige, lokale, marginale Screening-Größe aus *einem*
  Solve; MGA / near-optimal feasible space = teure globale Exploration. Komplementär, nicht konkurrierend.
- ★★ **SP als Begleiter-Signal.** RC (Variable) + Shadow Price (Constraint) ergeben zusammen das
  Randbild; die Arbeit fokussiert RC, der SP-Zweig ist der duale Partner („was kostet ein Constraint
  marginal"). Im Intro/Background schon angelegt — hier zusammenführen.
- ★ **Ökonomische Deutung der Überbewertung.** Der Effekt ist die *Kannibalisierung / „missing money"*
  der Strommarkt-Theorie: eine marginale Knappheitsrente ist kein nachhaltiger Wert für einen
  Price-Maker. Optional zitierfähig.

**Reichweite / Generalisierung der Metrik**
- ★★ **Andere Politik-Hebel statt nur CAPEX.** „Distance to build" lässt sich auch als CO₂-Preis,
  Subvention, OPEX oder CF ausdrücken — dieselbe Dual-Maschinerie. Z. B. „welcher CO₂-Preis baut X"
  über den Schattenpreis des Emissions-Constraints.
- ★ **Übertrag auf andere Investitionsvariablen.** Transport ist schon dabei; Retrofit, Storage-Bundle
  als weitere Kandidaten (Outlook).

**Methoden-Kosten / praktische Caveats**
- ★★ **Solve-Zeit-Aufpreis.** „Billig" ist relativ: Presolve aus + Crossover ist teurer als ein
  Default-Solve. Bei sehr großen Modellen nicht-trivial — Overhead vs. eingesparte Reruns abwägen.
- ★★ **Ceteris-paribus / Nicht-Komponierbarkeit.** RC gilt für *ein* (Tech,Knoten,Jahr). Reale
  Entscheidungen ändern viele Dinge gleichzeitig / eine Kostengröße überall / über Jahre — RC
  komponiert nicht; das braucht koordinierte Reruns. Fundamentale Scope-Grenze.
- ★ **Solver-/Versions-Abhängigkeit.** Das Signal ist nur so gut wie das gemeldete Dual (SE PV 166 vs 0);
  Reproduzierbarkeits-Caveat. (Steht im Appendix — hier als praktische Discussion-Note.)

**Modellstruktur-Wechselwirkungen**
- ★★ **Zeit-Scope: Snapshot vs. Mehrperioden / Carry-over.** Sauber im Greenfield/Snapshot; Vintage-
  Kopplung über Jahre erzeugt Phantom/unzuverlässige RC (schon geflaggt); Foresight (perfekt vs.
  myopisch) interagiert.
- ★★ **TSA-Wechselwirkung.** Zeitliche Auflösung ist mit RC-Verlässlichkeit verschränkt: grobe TSA lässt
  Knappheitsstunden den Tech-Wert dominieren → marginales Signal aufgebläht (Transport 24 vs 96 h).
  Trade-off Auflösung vs. Rechenkosten.
- ★★ **Vollständigkeits-Caveat (MILP/min-load/Reserve).** Bekäme das Modell On/Off-/min-load- oder
  Reserve-/Adequacy-Constraints, verlöre die operative Rekonstruktion einen Faktor und das Lifetime-Dual
  wäre vollständiger. (In Methodology als Caveat; hier als praktische Grenze.)
- ★ **Bidirektionaler Transport als *eine* Kapazität** statt zwei gerichteter RC (schon in §5.1 angerissen).

**Decision-Maker-Actionability (Bogen zum Intro)**
- ★★ **Human-in-the-loop-Workflow.** RC screent → Flag → gezielter Rerun → menschliche Entscheidung.
  Kein automatisches Orakel — verbindet die Ergebnisse mit der Intro-Motivation.
