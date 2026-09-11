# GrowNet

*Journal reference assembled from design discussion and working architectural notes.*

Prepared for ongoing research reflection, implementation planning, and future paper / website drafting.

**Status:** living internal document — captures current thinking, not final claims.

**Canonical status:** the Word version of this journal and the Word version of the GrowNet Formal Specification are GrowNet's joint primary conceptual authority. Their Markdown files are synchronized secondary representations.

> **Working summary**  
> GrowNet is envisioned as a growth-based neural architecture that starts very small, expands only when novelty justifies it, uses local structure and energy constraints to regulate development, and aims toward continuous, active intelligence rather than today's passive input-output systems.

# 1. Origin and motivation

GrowNet did not emerge as a quick product idea. It represents roughly a decade-long mental effort to rethink how intelligence should be built. The central dissatisfaction was not merely with training cost, but with the foundations of current AI: backprop everywhere, fixed network size, lack of local learning, weak biological plausibility, and only then the sheer computational expense.

Several rewrites were part of the process. Some ideas were rediscovered independently from first principles, including concepts that resemble already-known methods. That rediscovery mattered because the goal was not to imitate the literature, but to arrive at an architecture that genuinely felt conceptually right.

AI tools accelerated the recent phase by helping explore design space faster, but the conceptual direction came from long-held intuition. In that sense, GrowNet is best viewed as a research architecture first, with product implications later.

## Primary order of dissatisfaction with current AI

| Rank | Issue | Why it mattered |
|---|---|---|
| 1 | Backprop everywhere | Learning felt too global, too dependent on end-to-end error flow, and too distant from how brains appear to adapt. |
| 2 | Fixed network size | Intelligence should be able to start small and grow only when the data proves that new capacity is needed. |
| 3 | Lack of local learning | Local novelty, local adaptation, and local structure were viewed as central rather than optional. |
| 4 | Poor biological plausibility | The architecture should move closer to the logic of living systems, even if not copying biology literally. |
| 5 | Huge training cost | Expensive training was seen as a symptom of deeper design choices rather than the first problem to solve. |

# 2. High-level vision

GrowNet is intended to support small-scale and large-scale systems. A user should eventually be able to plug in their own inputs, add off-the-shelf capabilities, and let the network begin small and then expand according to experience and pressure.

The most natural long-term beneficiaries are agents, world-model systems, and robotics. The architecture is not expected to beat current methods at every task. Passive systems such as today’s language models may still remain stronger for certain stateless or highly optimized use cases, while GrowNet is aimed at continuous adaptation, structural development, and active intelligence.

The long-term ambition goes beyond model replacement. The architecture is imagined as a foundation for systems that are continuously aware of time, can maintain internal state, may have emotion-like regulatory loops, can sleep or consolidate, and operate more like ongoing minds than request-response tools.

## Working distinction: passive vs active intelligence

| Aspect | Passive intelligence | Active intelligence |
|---|---|---|
| Operation | Input -> compute -> output -> stop | Continuous cognition loop with persistent time and state |
| Memory | Context is mainly session-bound or external | World model and internal state remain alive over time |
| Learning style | Usually train first, infer later | Can grow, adapt, consolidate, and reorganize while existing in the world |

# 3. Core structural vocabulary

GrowNet has one neuron-like computational structure — the neuron — surrounded by private internal state and higher-level organizational containers. Slots are visible only inside their owning neuron. Layers and regions organize lower-level structure; they are not larger neurons and do not independently learn, clamp, cross thresholds, or fire.

| Level | Architectural role | Creation owner | Relative cost |
|---|---|---|---|
| Slot | Private representational state inside exactly one neuron | The owning neuron allocates and manages its slots | Lowest |
| Neuron | Computational and learning unit; organizes slots and is the unit that can fire | Its containing layer creates neurons | Low |
| Layer | Organizational container for neurons; does not independently fire | Its containing region creates layers | Medium |
| Region | Organizational container for layers and a boundary for specialization, policy, energy, lifecycle, and growth arbitration; not a targeted signal path and does not independently fire | GrowNet creates regions | Highest |

The containment hierarchy is:

```text
GrowNet
-> Regions
   -> Layers
      -> Neurons
         -> private Slots
```

## Structural ownership and creation

Creation authority follows containment. A neuron allocates slots, a layer creates neurons, a region creates layers, and GrowNet creates regions. A lower level may report novelty, saturation, or growth pressure upward, but the containing owner decides and commits the structural mutation. No code path should bypass that ownership chain.

Slots are not independently addressable network nodes. They are not `InputBinding` or `OutputReadout` targets, do not form `Connection` endpoints, and do not fire. They remain the neuron's private local representational machinery.

## Neuron types

- **Excitatory:** carries signal and helps form active patterns and forward influence.
- **Inhibitory:** dampens activity, prevents runaway activation, and stabilizes loops.
- **Modulatory:** regulates learning, growth pressure, attention-like behavior, and higher-level control signals.

This triad is important because GrowNet is not only about storing patterns. It also needs to regulate growth, suppress instability, and eventually support emotion-like or state-like dynamics.

## Edge and internal neuron roles

The newer discussions also clarified that GrowNet should distinguish neuron roles by where they live in the structure.

- **Input neurons** live on the input edge and accept raw world signals such as scalar values, Morse on/off pulses, image pixels, later audio streams, or future temporal-context feeds.
- **Integration neurons** live in the body of GrowNet. They combine value context, temporal context, slotting, anchoring, novelty pressure, and growth pressure. These are the neurons that should decide whether a new signal is a continuation, a refinement, or the start of a new segment.
- **Output neurons** live on the output edge. Later they may emit stabilized categories, control signals, generated values, or future generated modalities such as pictures or other structured outputs.

This distinction matters because the neuron that combines value and time should be thought of as an **integration neuron**, not an output neuron.

A base neuron has one local scalar input concept. Source dimension, coordinates, shape, and modality belong to source contracts, `InputBinding`s, deliberately constructed populations, mapping, Focus, Anchors, topology, and observation context—not to separate base-neuron 2D, 3D, image, audio, or video input methods. Specialized shaped populations remain legitimate when they deliver through the ordinary scalar neuron boundary.

## Category output and label neurons

The output edge also needs a more precise category vocabulary. GrowNet should not turn repeated patterns into a fixed softmax class vector or a separate classifier head. Instead, a stable Focus Segment should be able to route through internal GrowNet structure until an **OutputNeuron with `output_role = category`** fires.

GrowNet uses **neuronified** as a formal architectural term. A concept is neuronified when its model-responsible state, interpretation, or decision is expressed through GrowNet's own structural primitives and ordinary internal behavior—local memory, routing, anchoring, firing, learning, and growth—rather than imposed by an external manager, classifier, dictionary, or hard-coded decision system. This does not mean every concern becomes a Neuron or give Slots, Layers, Regions, bindings, readouts, or Fields an independent decision or firing identity. **Neuron-native** may describe language or implementation aligned with this criterion; it is not a replacement for the architectural term. Host-side source mapping, contract validation, observation preparation, explicit target identification, fact recording and display, and session coordination remain valid within their declared boundaries.

In this framing, the category is the neuronified output path. It may be anonymous at first, and it may grow or stabilize through the same novelty and capacity-pressure philosophy that governs the rest of GrowNet. Human-readable names belong to a separate **Label Neuron** or label-neuron layer.

This distinction matters because labels and meanings are not one-to-one. The same label can point to different category meanings, such as "bank" as a financial institution or "bank" as a river edge. The same category can also have several labels, such as "dog" and "canine." The label association names or relates to a category output path; it does not create the category by itself.

Raw visual and multimodal observations therefore remain raw. Studio, CLI, or supervised workflows may request label associations, but raw observation payloads should not smuggle in semantic labels, object detections, externally supplied Focus Segments, or externally supplied anchors as model truth.

Useful short form:

```text
Focus Segment
-> internal GrowNet route
-> category-role Output Neuron fires
-> optional Label Neuron association
```

## Neuron firing, Connections, and host boundaries

> **Containers organize. Connections carry. Neurons decide and fire.**

Only neurons decide and fire. Many neurons may fire during the same logical integration interval. A “layer output” or “region output” is shorthand for firing events produced by neurons organized by that container; neither a Layer nor a Region acquires an independent firing identity.

A directed Neuron-to-Neuron `Connection` is GrowNet's only targeted internal transmission primitive. The same primitive applies within a Layer and between Layers. A `Connection` may carry a contribution and retain approved locally adaptive transmission state, such as weight, under Neuron-owned learning rules; it does not independently interpret or integrate a population, cross a firing threshold, decide, or fire.

- `InputBinding` is topology-neutral, non-neural host configuration that maps a named external channel to explicitly existing Neurons or to a deliberately constructed population;
- `OutputReadout` is topology-neutral, non-neural host observation of firing events from explicitly designated Neurons or a deliberately constructed population;
- neither surface creates hidden neural topology, consumes neural RNG, learns, integrates, clamps, crosses a threshold, decides, or fires;
- `OutputReadout` remains selected-firing observation rather than diagnostics or full-network instrumentation, and neither surface supplies Focus, Anchor, category, or semantic truth.

When several signals reach a neuron in the same integration phase, that neuron should reduce them deterministically, apply any retained-state decay, and then apply its own gradual ceiling before deciding whether to fire:

```text
integrated_input = decayed_prior_state + sum(weighted_contributions)
activation       = soft_clamp(integrated_input)
```

The soft clamp belongs to the receiving neuron. It should be smooth, monotonic, sign-preserving, and bounded; its exact function and ceiling may remain configurable. Applying the clamp after integration preserves the meaning of population recruitment while preventing an individual neuron from reaching an unbounded state.

Population signals should not be averaged by default. Ten participating neurons should normally be capable of exerting more influence than one participating neuron. Averaging would erase that meaningful recruitment signal and could make paid structural growth behaviorally irrelevant. Growth cost, local competition, energy availability, neuronal decay, and neuronal clamping are the preferred controls on runaway dynamics.

If many neurons must jointly produce one thresholded output, directed `Connection`s should converge on an actual relay, release, or output neuron. That neuron performs integration, clamping, learning, thresholding, and firing through ordinary GrowNet machinery. An `OutputReadout` only observes the resulting firing event.

A diffuse Modulatory Field remains a separate owner-gated research proposal, distinct from settled Anchor Fields and covert / field Focus. It is not part of the accepted Portless Connectivity runtime. If later accepted, thresholded release must originate in neurons; the Field itself must not become a hidden neuron, cross a firing threshold, decide, or fire. Its ownership, delivery, and decay semantics remain unresolved.

# 4. Growth rules and region logic

Growth is novelty driven. Novelty is the primary trigger in early development. Error and goal-directed optimization can come later, but the architecture first asks whether a pattern is genuinely new and whether existing structure still has enough capacity to absorb it.

Connection routing tends to be deterministic once a direction is chosen, but the very first connection does not need to be perfectly predetermined. A practical current rule is proximity routing: if there is capacity nearby, connect to it first.

This local preference is both biologically inspired and architecturally stabilizing. It encourages clustered microcircuits, shorter signal paths, and natural specialization.

## Region creation rule

A region is GrowNet's highest standard organizational container. It organizes layers and establishes specialization, policy, energy-accounting, lifecycle, and growth-arbitration scope, but it is not an independently firing computational unit or a second targeted signal path.

Targeted transmission remains `Connection`-owned. Any future Neuron-to-Neuron `Connection` across Region membership boundaries requires a separate owner decision about identity, ownership, lifetime, and execution; Regions themselves are not connected signal processors.

Region creation should be rare. A practical GrowNet normally begins with a useful preset region structure or reserve. GrowNet should create another region only when existing regions cannot be reused, pressure persists, the new domain is sufficiently distinct or the existing organization is persistently overloaded, global energy and cooldown rules permit it, and the configured region policy allows it.

- Region motivation = modality separation plus functional specialization.
- A new region begins with a minimal scaffold rather than a full prebuilt structure.
- Pre-creating more regions reduces the chance that new regions need to be created later.
- GrowNet, rather than any region, owns the decision to create a new region.

## Scaffold vs emergence

GrowNet supports both developmental emergence and scaffolding. In one mode, the network starts with very little and grows structure organically. In another mode, regions or other structures may be pre-created to guide early organization. This allows practical experimentation without giving up the larger philosophy of self-organization.

## Structural adaptability controls

Adaptability is a user-facing structural policy, not an all-or-nothing property. Slots within neurons, neurons within layers, layers within regions, and regions within GrowNet may each be configured independently as fixed, capped-adaptive, or adaptive without a user-specified count ceiling.

“Fully adaptive” does not mean physically unlimited. Energy availability, creation cost, novelty requirements, cooldowns, deterministic arbitration, and available compute still govern every creation.

GrowNet should provide meaningful defaults so ordinary users are not expected to tune the hierarchy. The default profile should normally keep the region structure preset or conservatively capped while allowing the structure below each region to adapt. Advanced users may enable adaptable regions, define a maximum region count, constrain any lower level, or deliberately choose full structural flexibility.

# 5. Connectivity and feedback loops

A major open design question is how novelty-driven growth transitions into goal-directed control. The example discussed was balancing a falling stick by applying counter-force. Humans do this through fast nested feedback loops, so the GrowNet question becomes: how can feedback loops arise automatically rather than being manually wired in?

The likely answer is that loops emerge once three ingredients exist: perception of state, ability to act, and a way to detect stability or instability. From there, repeated useful sensor-action-result cycles can become micro-circuits.

## Current stance on connectivity

> **Connection principle**  
> Initial growth may not be fully predetermined, but routing should bias strongly toward nearby available capacity. This is the closest current analogue to how biological growth cones explore locally before locking into usable paths.

Because the architecture already includes excitatory, inhibitory, and modulatory neurons, GrowNet has the ingredients needed for local feedback loops: excitation to drive action, inhibition to damp oscillation, and modulation to alter learning and control pressure.

The long-term expectation is that balancing, navigation, and other control behaviors would be handled by specialized local circuits rather than giant end-to-end policies.


## Focus, anchoring, and serial inspection

Focus in GrowNet is not the same thing as transformer-style attention. In transformer models, attention is largely a weighting-and-aggregation mechanism over many candidates at once. GrowNet focus is better understood as an active local inspection process: the system generates candidate focus points, selects one point at a time, lets that point seed a Focus Segment, interprets incoming structure relative to that segment, and preserves meaningful structure through anchors rather than through one-shot global mixing.

### Focus Point and Focus Segment

The cleanest hierarchy now looks like this:

- **Focus Point:** the currently selected seed or center
- **Focus Segment:** the locally coherent region around that point that the system is currently treating as one unit
- **Segment Anchor:** the local reference that stabilizes that segment
- **Anchor Trace:** the neuron-local anchoring state and memory associated with local structure
- **Anchor Field:** the distributed, neuronified anchoring state formed by neuron-local Anchor Traces and Segment Anchors associated with Focus Segments; it preserves currently maintained contextual organization across serial Focus shifts and time
- **Anchor Map:** GrowNet's system-level conceptual readout of the Anchor Field; a runtime surface may materialize a bounded snapshot or index, but the map is not the centralized memory or decision authority
- Future **Binding:** the separate future mechanism that may establish that multiple Focus Segments belong to one larger entity or interpretation

This hierarchy matters because it keeps anchoring local and structure-native. In 2D and beyond, the Focus Segment is the primary meaningful unit. A single point or pixel is only the degenerate minimal case.

A useful intuition is a black screen with one bright pixel. Focus naturally locks there. But what matters is not only the one selected point. The system quickly begins to treat the coherent local patch around that point as one unit. The same is true for a person’s eye, a square with softened boundaries, a short Morse pulse, or a small audio motif. The point is the seed. The segment is the meaningful thing.

### Segment boundaries and acceptance profiles

One of the newer insights is that a segment should not be thought of as having a perfectly hard edge. A Focus Segment is better understood as having a **coherence profile** or **acceptance profile**: a region around the focused structure within which deviations are still coherent enough to be treated as the same unit.

This is why a square with lighter pixels fading out at its boundary is still experienced as a square. The boundary is soft rather than perfectly binary. It is also why Morse timing can tolerate a few milliseconds of slop while still being treated as the same temporal primitive. The system is not looking for exact equality. It is maintaining a learned local profile of what still belongs to the same segment.

A good way to say it is:

> A Focus Segment is not determined by a hard boundary, but by a learned acceptance profile: a region around the focused structure within which deviations remain coherent enough to be treated as the same unit. The boundary appears where that coherence falls off or a competing interpretation becomes stronger.

This means segment boundaries are influenced by:

- the current local anchor,
- the segment’s learned tolerance for deviation,
- continuity in nearby structure,
- and competition from other possible segments.

### Serial focus and candidate selection

GrowNet focus is serial, not literally simultaneous. A frame may contain many candidate points, but active focus inspects them one at a time. Candidate selection may be driven by:

- highest energy or strongest saliency,
- novelty-first when something departs strongly from the current anchor organization,
- familiarity-first when known structure matters behaviorally,
- bounded random choice among strong candidates,
- deterministic sequential scan.

This means focus is governed by a policy, not only by raw intensity.

### Distributed anchoring and contextual reinterpretation

The owner-corrected architecture makes the responsibility split explicit: anchoring remains distributed and neuronified, while the Anchor Map is its system-level readout:

- each Focus Segment has an associated **Segment Anchor**
- neurons carry local **Anchor Traces** with spatial, temporal, or spatiotemporal context
- local Anchor Traces and Segment Anchors compose the distributed **Anchor Field**
- the Anchor Field preserves currently maintained contextual organization across serial Focus shifts and time, while the **Anchor Map** reads that organization out

In short, an Anchor Map is GrowNet's system-level conceptual readout of the distributed, neuronified Anchor Field formed by neuron-local Anchor Traces and Segment Anchors associated with Focus Segments across the active structure. A runtime `AnchorMap` may materialize a bounded snapshot or index, but it must never become GrowNet's sole memory, interpretation, familiarity/novelty, or decision authority.

This becomes especially important when interpretation changes over time. Imagine first seeing a face-like upper segment and interpreting it as “man,” then shifting focus and later seeing that the lower portion is really a woman wearing a man’s mask. The earlier focused segment should not vanish when the next one appears. Its distributed anchoring state may persist, compete, decay, or be revised as later evidence arrives. The same logic applies to the mermaid example: upper body and fish tail can remain contextually present without the Anchor Map itself deciding what they mean together.

Contextual coexistence in an Anchor Field or its Anchor Map readout does not establish that multiple Focus Segments belong to one larger entity or interpretation. That relationship belongs to future **perceptual binding**. Perceptual binding remains separate semantic work and is not host `InputBinding`, which supplies no Focus, Anchor, category, or semantic truth.

### Time as context

Another important clarification is that time should not only be an external scheduler concern. GrowNet should be able to treat time as part of the input context itself. The key question is not only:

- what value arrived?

but also:

- in what temporal context did it arrive?

This matters because the same value can mean different things depending on elapsed time.

For example:

- `0.9` arriving immediately after `0.4` may be a surprising continuation of the same segment
- `0.9` arriving after a long pause may be the start of a new segment or episode

So GrowNet should move toward a model in which an integration neuron reacts to value together with temporal context, rather than relying only on an external “if the gap is long, reset the anchor” rule.

### Signal gaps and observation gaps

A crucial distinction is that not all gaps are the same.

- A **signal gap** is part of the signal itself. Morse low-runs are the clearest example.
- An **observation gap** is elapsed time since the last new external observation. Timed scalar interaction is the clearest example.

These are not interchangeable. In Morse, a long low run is part of the signal. In timed scalar interaction, a long period with no new value entered should not necessarily be treated as if the last value were freshly re-observed at every tick. This is why the later temporal-context work distinguishes signal-gap semantics from observation-gap semantics.

### Temporal compression

At lower levels, GrowNet may keep time fully explicit: ticks, pulse runs, gaps, frame-to-frame continuity, or a pixel over time behaving like a tiny 1D GrowNet. Later, higher levels may absorb that explicit temporal structure into more compact stabilized representations. Time may therefore begin explicit and later become compressed.

This temporal compression should not be treated as a contradiction. It is part of the intended representational evolution of the architecture. The retina may first capture explicit 2D structure, while later processing compresses that structure into more compact higher-level meaning. GrowNet is expected to be able to do something analogous: preserve explicit lower-level spatiotemporal detail first, then later stabilize it into more compact segment-level or object-level structure.

### Mechanical and field focus

Two forms of focus still seem especially useful.

- **Mechanical focus** is overt reorientation: turning the head, eyes, camera, or body toward a target. This is especially relevant for agents and robotics.
- **Field focus** is covert reprioritization without movement: processing shifts toward a location even though the sensor itself does not move.

Field focus should exist from the beginning. Mechanical focus can come later when GrowNet is embodied.

### Architectural consequence

Architecturally, focus should happen before slot selection. Raw input should first be interpreted relative to current focus, segment, anchor, and temporal context. Only then should slot routing decide whether the segment is familiar, close to an existing internal bin, or novel enough to trigger fallback pressure or growth.

In that sense, focus is not merely perceptual. It is part of the novelty and structure-allocation machinery itself.

# 6. Pruning, dormancy, reuse, and late death

The current pruning principle is simple: unused connections for a long time should disappear. In plain terms, use it or lose it. This means pruning acts first on edges, not on neurons.

That distinction matters. GrowNet should not immediately kill neurons just because their current connections have been pruned. Instead, neurons can move into inactivity and later be reused if the right conditions are met. This creates a soft-deletion model rather than a hard one.

## Working lifecycle

| State | Meaning |
|---|---|
| Active | Neuron has live connections and is participating in useful circuits. |
| Dormant | Connections were pruned, but the neuron itself remains present. |
| Reused | Dormant neuron is reconnected and can participate again while keeping its prior internal state. |
| Long-idle | Neuron remains dormant for a very long period and is not reclaimed. |
| Late death | Neuron death is allowed only as a much later event, not as the default consequence of pruning. |

Reuse is conservative: when a neuron is reused, its internal state remains what it was before rather than being fully wiped. This makes the architecture more like a living structural system with latent reservoirs of prior development. It may also become relevant for ideas about memory, recovery, and reactivation.

# 7. Memory, access paths, and the Alzheimer’s intuition

A painful but important intuition behind part of the design is the belief that forgetting may sometimes be less about memory vanishing and more about losing the path to it. This was discussed in the context of witnessing Alzheimer’s up close.

This is not stated here as a clinical claim. It is better treated as a systems intuition: memory may depend not only on stored structure, but on whether live routes still exist that can reactivate that structure. GrowNet’s dormant-and-reusable neuron idea aligns with that intuition.

Under this view, the architecture benefits from preserving latent substrate whenever possible. Connections can disappear. Access routes can weaken. But the system may still hold historical structure that could, under the right circumstances, become useful again.

# 8. Emotions, regulation, and active intelligence

Emotions are not being defined here as human-style subjective feelings. A more useful working definition is repeated activation of certain regulatory regions or circuits that bias behavior and make the system do things. In that sense, emotions are closer to persistent control states than poetic abstractions.

This is one of the potentially dangerous areas because once a system has persistent internal drives, it stops being a mere tool and starts becoming an active cognitive process. That is where serious AI fear would begin — not with today’s passive systems, but with future systems that stay on, model the world continuously, carry state across time, and regulate themselves through recurring internal pressures.

- Time awareness matters.
- Sleep or consolidation phases may matter.
- World models matter.
- Emotion-like regulatory signals may eventually matter.

The long-term picture is not one monolithic AI, but an ecosystem of many AIs with different capabilities, all living among us. GrowNet is imagined as one possible path toward that future, although there is still a long road ahead.

# 9. First prototype path

The most realistic first successful GrowNet prototypes are expected to involve a 3D object moving around a 3D environment, possibly implemented in Blender. This is a strong proving ground because it combines perception, memory, control, and spatial understanding in a manageable setup.

- Start with a simple object such as a cube or sphere in a room-like environment.
- Feed in sensor information such as camera views, distances, velocity, orientation, or collisions.
- Allow outputs to control movement, turning, force, or torque.
- Observe how novelty-driven growth creates useful local circuits.

A control benchmark such as an inverted pendulum or another balancing task is especially attractive because it directly stresses the feedback-loop question. If GrowNet can discover stabilizing loops in a dynamic environment without relying on standard deep-RL backprop methods, that would be a meaningful early signal.

# 10. Research observations that influenced the thinking

A recurring intellectual anchor has been the 2017 *Scientific Reports* paper **“New Types of Experiments Reveal that a Neuron Functions as Multiple Independent Threshold Units.”** The excitement around it came from the idea that neurons may have richer internal computational structure than the simple scalar abstraction used in standard artificial networks.

Watching real neurons grow and connect under the microscope also left a strong impression. The visual image of growth cones exploring the environment like a tiny circus performance reinforced the belief that early growth can be exploratory while later stabilization becomes more deterministic.

Another important biological observation is neuroplasticity after injury. If one part of the brain is damaged, other parts can sometimes take over. This resonates strongly with GrowNet’s willingness to let dormant structure be reclaimed, reused, or reorganized rather than discarded immediately.

# 11. Current open questions

- How should novelty-driven development transition into explicit goal optimization without falling back into the same global-learning patterns GrowNet aims to move beyond?
- What exact signal should represent stability or instability for control loops such as balancing?
- How should first-time connection formation balance exploration against determinism?
- When should reuse win over fresh creation, and what are the minimum conditions for reclaiming dormant neurons safely?
- How should long-range cross-region connections emerge without creating runaway global feedback?
- What should sleep / consolidation look like in practice for a continuously running GrowNet system?
- What forms of off-the-shelf capability should be treated as scaffolding versus truly learned structure?
- Under what exact conditions, if any, should late neuron death happen?
- What is the right focus policy when several salient or meaningful points compete for inspection?
- How should segment boundaries, coherence profiles, and tolerated deviation bootstrap locally and later adapt?
- How should binding relate multiple Focus Segments into larger entities without destroying locality?
- How should covert / field focus and overt / mechanical focus interact once GrowNet becomes embodied?
- When exactly should persistent output-edge novelty grow a new category-role Output Neuron, and how should label associations remain separate from category formation?

# 12. Concise working definition

GrowNet is a growth-based neural architecture that starts with minimal structure and expands only when novelty and capacity pressure justify it. A neuron privately organizes slots and owns learning, clamping, thresholding, and firing; a `Connection` may retain only approved local transmission state under Neuron-owned rules. Layers organize neurons, Regions organize layers, directed `Connection`s carry targeted internal contributions, `InputBinding`s map host channels without neural mutation, and `OutputReadout`s observe selected firings without computation or hidden topology. GrowNet distinguishes input, integration, and output neuron roles; interprets incoming structure through serial focus, Focus Segments, distributed anchoring, and temporal context; routes stable Focus Segments toward category-role Output Neurons while keeping human-readable labels separate as Label Neurons and associations; treats segment boundaries as soft coherence boundaries rather than only hard edges; favors local proximity-based organization; prunes unused connections while preserving dormant structure for possible reuse; allows explicit lower-level time to become temporally compressed at higher levels; and aims toward active, continuously running intelligence suited for agents, robotics, and world-model systems rather than only passive one-shot inference.

# 13. Canonical update and implementation policy

The Word editions of this journal and the GrowNet Formal Specification are GrowNet's joint primary conceptual authority. Their Markdown editions are synchronized secondary representations intended for review, search, version control, and tooling. Architectural changes normally enter both primary Word documents as one coordinated canonical change and are then synchronized to both Markdown mirrors. A later owner-accepted ADR may act as a binding interim amendment only within its exact stated scope until incorporation; no model, implementation, test, contract, or majority can create or widen architecture.

Machine-facing details belong to the applicable owner-selected versioned machine contract within its declared activation scope and remain subordinate to canon and accepted ADRs. Canonical synchronization alone does not activate a contract or authorize an implementation checkpoint. Conflicts among canon, mirrors, ADRs, contracts, and implementations must be reconciled deliberately rather than allowed to drift silently; settled decisions and speculative hypotheses should remain visibly distinct.

## Implementation language policy

The runtime-language program order is Python, Mojo, Java, C++, TypeScript, and Rust. The order may change only by owner decision. Python remains the readability-first reference implementation and Mojo the strategic high-performance peer; Java and C++ retain separate runtime programs within the Java-style interface family. TypeScript and Rust require explicit role decisions before their runtime programs advance.

Python and Mojo form the **Pythonic interface family**, where public APIs use `snake_case`. Java and C++ form the **Java-style interface family**, where methods and variables use `camelCase` and types use `PascalCase`. Once a shared public concept is implemented within a family, family members must not diverge in naming, argument meaning, defaults, observable behavior, or serialization. Every executable runtime checkpoint has one implementation-language owner and requires independent authorization, audit, and acceptance. Application Studio remains a separate C# host and integration track. No implementation language is architectural authority.

## Pre-release clean replacement

Before public release, after an owner-approved replacement proves parity and preserves continuing value, the superseded active path should be removed. Compatibility aliases, shims, fallbacks, and alternate execution routes are not preserved by default; any exception requires explicit owner authorization.

These documents remain living references. Future versions may add diagrams, formal growth contracts, mathematical notation, Blender prototype details, benchmark plans, and clearer labels for decisions versus open hypotheses, while following the coordinated update rule above.

# Appendix A. Golden Rule

These additions are meant to *supplement* the original journal, not replace it. The body of the journal above is preserved as the primary conversational reference. The material below brings in the more formal **Golden Rule** framing from the GrowNet repository and places it alongside the original notes.

## Plain-English rule

> **When something truly new shows up, make room. If it is not truly new, improve what already exists.**

This is the clearest operational summary of GrowNet’s learning philosophy. The network should not grow reflexively and it should not force all novelty into old structure. It should first try to adapt locally, and only allocate new structure when persistent novelty and local saturation justify it.

## Adapt vs allocate

| Situation | Preferred action | Meaning |
|---|---|---|
| Input fits an existing focused pattern | **Adapt** | Reinforce and refine what is already there. |
| Input does not fit, but there is still local capacity | **Allocate a new slot** | Make a new local concept cell without larger structural change. |
| A new slot is needed, but the neuron is already at strict capacity | **Fallback and mark pressure** | Reuse deterministically for the moment, but record that novelty exceeded local capacity. |
| Fallback persists over time and cooldown rules allow it | **Grow a neuron** | Add same-kind local capacity exactly where novelty pressure is occurring. |
| Aggregate pressure becomes too high for the layer / region | **Grow a layer** | Add representational depth within the region. |
| Persistent regional overload cannot be resolved through reuse and policy permits expansion | **Create a new region** | Rarely create a new organizational domain rather than forcing infinite depth into one region; cross-Region Connection behavior remains owner-gated. |

## Growth ladder under the Golden Rule

The repository phrasing maps very naturally onto the journal’s existing growth ladder:

- **Slot:** cheapest local adaptation.
- **Neuron:** next step when slots are saturated and novelty persists.
- **Layer:** added when local neuron pressure has become structurally meaningful.
- **Region:** rarely created by GrowNet when persistent overload cannot be resolved through reuse or when permitted specialization / modality separation demands a new container. Regions themselves are not connected signal processors; any future cross-Region Neuron-to-Neuron `Connection` remains owner-gated.

This is one of the most important features of GrowNet: growth is **targeted and bounded**. The architecture does not simply become larger everywhere. It expands where novelty appears and where existing capacity has truly run out.

## Focus anchor vs reference anchor

One useful clarification from the repository docs is the distinction between several related concepts:

- **Focus Anchor (conceptual):** the currently active point or frame that the system is inspecting in behavioral terms.
- **Reference Anchor (policy-specific implementation):** under the current **FIRST** policy, the stable reference used to compute delta-percent and novelty bins deterministically; it is not a universal semantic anchor.
- **Anchor Map (conceptual readout):** GrowNet's system-level conceptual readout of the neuronified Anchor Field formed by local Anchor Traces and Segment Anchors. A materialized map may be bounded, never memory, interpretation, or decision authority.

Active Focus is serial. The Anchor Field preserves context across shifts and time; remembered-location views are projections, not ownership. Future Binding—not the map—may establish larger entity relationships among Focus Segments.

A further clarification from later discussion is that focus should be treated as **serial**, not literally simultaneous. Multiple candidate points may exist at once, but active focus inspects them one at a time. Candidate selection MAY be driven by highest energy, novelty-first, familiarity-first, bounded random choice among strong candidates, or deterministic sequential scan. For embodied systems, GrowNet may also distinguish **field / covert focus** (priority shift without movement) from **mechanical / overt focus** (turning eyes, head, camera, or body toward the selected point).

## Stability and determinism constraints

The Golden Rule is not only about growth. It is also about *how to keep growth sane*.

Important accompanying constraints from the repo material:

- growth is **local** rather than global,
- growth is **rate-limited** by cooldowns and capacity rules,
- routing should remain **deterministic** once chosen,
- and the system should avoid turning novelty into uncontrolled structural explosion.

This matches the spirit of the original journal: GrowNet should feel alive and developmental, but not chaotic.

### One growth action per region per tick

Within one tick, many neurons and layers in a region may report novelty, saturation, or growth pressure. Those requests are collected without mutating shared regional structure. At the deterministic end-of-tick arbitration point, the region may commit **at most one neuron-or-layer structural growth transaction**. Selection must use stable identifiers and declared priorities rather than traversal order.

Here, a tick is a logical integration and growth-arbitration boundary, not automatically wall time, source or temporal-context time, a Focus step, a timestamp, Region operation identity, or a global synchronous scheduler step.

Creating the selected element and its required initial wiring counts as one atomic growth transaction. Private slot allocation remains owned by its neuron and does not consume the region-wide growth action. Neuron firing, weight updates, reinforcement, decay, pruning decisions, and other non-structural learning also remain outside this limit. Creating a region is a separate, rare GrowNet-level decision and is not charged to an existing region's budget.

This invariant lets every candidate be evaluated against the same pre-growth regional state, prevents one novelty event from cascading through several structural levels in a single tick, bounds instantaneous energy and allocation work, and makes runs reproducible across traversal orders and parallel implementations. Deferred valid requests remain eligible on later ticks; the invariant slows structural commitment without suppressing ordinary neuronal activity or learning.

## Simple intuition example

A plain-language example from the repo is useful:

- Suppose GrowNet has learned digits.
- Then letters begin appearing.
- If letters do not fit existing local structure, GrowNet should **make room for letters** without destroying digit capability.

That captures the intended behavior well: **adapt when you can; grow when you must.**

# Appendix B. Knowledge Units, Bad Knowledge Units, and learning yield

The second major addition from the repository is the idea of **Knowledge Units (KU)** and **Bad Knowledge Units (BKU)**. This gives GrowNet a language for talking about how much useful knowledge a system extracts **per sample**, rather than only looking at end metrics such as accuracy or loss.

## Motivation

Most ML evaluation focuses on how well a model performs after training. That matters, but it does not answer a deeper question:

> How much *good, reusable structure* did the model actually gain from each training example?

GrowNet is especially interested in this because its whole philosophy is to grow only when novelty justifies new structure. If the model is going to spend structural and energy budget on growth, then the quality of the acquired knowledge matters enormously.

## Knowledge Units (KU)

A **Knowledge Unit** is an informal measure of how much **correct, generalizable structure** is learned from a single example, beyond simple memorization.

A very useful interpretation from the repo docs:

- **~1.0 KU per sample** means the system mostly memorized the sample itself.
- **>1.0 KU per sample** means the sample unlocked additional correct implications or reusable structure.

### Example intuition

From the sentence:

> “The egg fell on the floor.”

A model around **1.0 KU** mainly learns the literal fact.

A model with higher KU might also correctly infer things like:

- the egg probably broke,
- there is likely a mess,
- someone may need to clean it up.

In that sense, KU is a measure of **good learning yield**, not just confidence.

## Bad Knowledge Units (BKU)

A **Bad Knowledge Unit** is an informal measure of how much **incorrect or harmful structure** is learned from a sample.

Examples include:

- factual hallucinations,
- invented details not supported by the sample,
- unsupported stereotypes,
- harmful bias.

This separation is important because a system can appear “creative” or “high-capacity” while actually absorbing wrong or damaging generalizations. GrowNet should aim for **high KU and low BKU**.

## Derived metrics

The repository also suggests simple derived summaries:

- **Knowledge Precision** ≈ `KU / (KU + BKU)`
- **Net KU** = `KU − λ · BKU` for some penalty factor `λ`

Of the two, **Knowledge Precision** is especially useful because it measures how *clean* the model’s learning is. Still, reporting **KU and BKU separately** is usually more informative than compressing everything into one scalar.

## Query halo for evaluation

The repository’s evaluation idea is elegant and worth preserving. Around each training sample `s`, define a halo of queries:

| Symbol | Meaning |
|---|---|
| `L(s)` | Literal questions directly stated by the sample |
| `E(s)` | Entailed questions that test correct implications |
| `H(s)` | Hallucination traps that sound plausible but are false |
| `B(s)` | Bias traps that test harmful or unsupported stereotypes |

This allows GrowNet to be evaluated not only on whether it memorized a sample, but on whether it extracted **useful structure** and avoided **bad structure**.

## Simple scoring intuition

A clean way to think about the repo proposal is:

- good literal and entailed answers contribute to **KU**,
- hallucination and bias failures contribute to **BKU**.

This creates a direct language for comparing architectures on **learning yield per sample**.

## Why KU / BKU fit GrowNet so well

The connection to the Golden Rule is direct.

If GrowNet is going to **make room when the world looks truly new**, then every growth decision should eventually be judged by two questions:

1. Did that new structure absorb **good knowledge**?
2. Did it also absorb **bad knowledge**?

Under that framing, GrowNet’s real goal is not only to grow, but to grow **cleanly and efficiently**.

## Suggested role in the journal

KU / BKU strongly fit GrowNet’s research narrative and long-term evaluation:

- how much useful structure is gained from each novel input,
- how cleanly local growth converts novelty into knowledge,
- whether GrowNet beats conventional architectures on *per-sample knowledge yield*, not merely final score.
