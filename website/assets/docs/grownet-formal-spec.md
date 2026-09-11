# GrowNet Formal Specification

**Document type:** Research draft formal specification for architecture, invariants, lifecycle, and evaluation direction  
**Purpose:** Architecture and invariants reference  
**Relationship:** Joint primary conceptual authority with the GrowNet Journal Reference; tighter than the journal and broader than any applicable owner-selected versioned machine contract

**Status:** Living internal specification; some sections are normative and some remain research hypotheses

> **Working definition**  
> GrowNet is a growth-based neural architecture in which neurons privately organize slots and are the only structural elements that learn, clamp, cross firing thresholds, and fire. Layers organize neurons; regions organize layers and arbitrate bounded structural growth. GrowNet learns locally, interprets input through serial focus and anchoring, routes stable Focus Segments toward category-role Output Neurons while keeping labels separate, allocates new capacity only when novelty and saturation justify it, favors deterministic organization with proximity-biased routing, and aims toward active, continuously adapting intelligence rather than passive input-output inference.

## 1. Specification posture

This specification uses the following language:

- **MUST** indicates a core architectural invariant or intended default behavior.
- **SHOULD** indicates a strong design preference that can be overridden only with good reason.
- **MAY** indicates an optional or experimental capability.

**Neuronified** is a formal GrowNet architectural term. A concept is neuronified when its model-responsible state, interpretation, or decision is expressed through GrowNet's own structural primitives and ordinary internal behavior—local memory, routing, anchoring, firing, learning, and growth—rather than imposed by an external manager, classifier, dictionary, or hard-coded decision system. This does not mean every concern becomes a Neuron or give Slots, Layers, Regions, bindings, readouts, or Fields an independent decision or firing identity. **Neuron-native** MAY describe language or implementation aligned with this criterion; it is not a replacement for the architectural term. Host-side source mapping, contract validation, observation preparation, explicit target identification, fact recording and display, and session coordination remain valid within their declared boundaries.

This document is not the same thing as a machine contract in the repository. The two primary Word documents define conceptual architecture and acceptable behavior. Applicable owner-selected versioned machine contracts are subordinate to canon and accepted ADRs; they define machine-facing public APIs and parity only within their declared activation scopes. Handoff and continuity packages provide orientation, history, and current status; they do not override canon.

A new architectural concept or changed normative decision MUST normally be incorporated into both primary Word documents as one coordinated canonical change, then synchronized to both Markdown mirrors. A later owner-accepted ADR MAY act as a binding interim amendment only within its exact stated scope until incorporation; no model, implementation, test, contract, or majority may create or widen architecture. Any machine-facing part MUST then be represented in the applicable owner-selected versioned contract. Canonical synchronization alone MUST NOT activate a contract or authorize an implementation checkpoint. Conflicts MUST be reconciled deliberately; no artifact or implementation may silently become an alternative specification.

### 1.1 Implementation language policy

The runtime-language program order is Python, Mojo, Java, C++, TypeScript, and Rust. The order MAY change only by owner decision. Python remains the readability-first reference implementation and Mojo the strategic high-performance peer; Java and C++ retain separate runtime programs within the Java-style interface family. TypeScript and Rust require explicit role decisions before their runtime programs advance.

Python and Mojo form the **Pythonic interface family** and MUST use `snake_case` for shared public APIs. Java and C++ form the **Java-style interface family** and MUST use `camelCase` for methods and variables and `PascalCase` for types. Implementation depth MAY differ while languages mature. Once a shared concept or public interface is implemented within a family, family members MUST NOT diverge in naming, argument meaning, defaults, observable behavior, or serialization. Every executable runtime checkpoint MUST have one implementation-language owner and independent authorization, audit, and acceptance. Application Studio remains a separate C# host and integration track. No implementation language is architectural authority.

### 1.2 Pre-release clean replacement

Before public release, after an owner-approved replacement proves parity and preserves continuing value, the superseded active path SHOULD be removed. Compatibility aliases, shims, fallbacks, and alternate execution routes MUST NOT be preserved by default; any exception requires explicit owner authorization.

## 2. Architectural thesis

GrowNet exists because the current mainstream AI paradigm leaves several foundational issues unresolved. The primary dissatisfaction, in order, is:

1. Backprop everywhere
2. Fixed network size
3. Lack of local learning
4. Weak biological plausibility
5. Huge training cost

The architecture therefore aims to satisfy the following high-level goals:

- Learning SHOULD be primarily local rather than globally backpropagated.
- Capacity MUST begin small and grow only where justified.
- Structure MUST matter as much as weights or parameters.
- Growth MUST be bounded by energy, capacity, cooldown, and deterministic rules.
- The long-term architecture SHOULD support active intelligence, world models, robotics, and continuous operation.
- GrowNet is not required to outperform current systems at every task. It is intended to be stronger in domains where adaptation, structural development, and ongoing control matter most.

## 3. The Golden Rule

> **Golden Rule:** When something truly new shows up, make room. If it is not truly new, improve what already exists.

This yields the following operational rule:

| Condition | Preferred action | Meaning |
|---|---|---|
| Input matches an existing focused pattern | Adapt | Reinforce or refine existing structure |
| Input is new but local capacity still exists | Allocate slot | Add the smallest possible new local memory cell |
| A new slot is needed but the neuron is already saturated | Fallback and mark pressure | Reuse deterministically for now, but record novelty pressure |
| Fallback persists and cooldown allows it | Grow neuron | Add new same-kind local capacity exactly where pressure exists |
| Layer pressure becomes structurally meaningful | Grow layer | Add depth within the current region |
| Persistent regional overload cannot be resolved through reuse and policy permits expansion | Create a new region | Rarely create a new organizational container; cross-Region Connection behavior remains owner-gated |

The Golden Rule is the heart of GrowNet. The system SHOULD always attempt the cheapest valid adaptation first.

## 4. Core entities

GrowNet has one neuron-like computational structure — the neuron — together with its private state and higher-level organizational containers.

| Entity | Architectural role | Creation owner | Relative creation cost |
|---|---|---|---|
| Slot | Private representational state visible only inside exactly one neuron | Its owning neuron allocates and manages slots | Lowest |
| Neuron | Computational and learning unit; organizes slots and is the only structural level that can fire | Its containing layer creates neurons | Low |
| Layer | Organizational container for neurons; does not independently fire | Its containing region creates layers | Medium |
| Region | Organizational container for layers and boundary for specialization, policy, energy, lifecycle, and growth arbitration; not a targeted signal path and does not independently fire | GrowNet creates regions | Highest |

The containment and ownership hierarchy is:

```text
GrowNet
-> Regions
   -> Layers
      -> Neurons
         -> private Slots
```

A Slot MUST be private to its owning Neuron. It MUST NOT be a publicly addressable network node, be targeted by an `InputBinding` or `OutputReadout`, form a `Connection` endpoint, or fire. A Neuron MAY allocate and organize its Slots. A Layer MAY create and organize Neurons. A Region MAY create and organize Layers. GrowNet MAY create and organize Regions. Lower levels MAY report novelty, saturation, or growth pressure upward, but MUST NOT bypass the owner that commits the structural mutation.

Only Neurons fire. A “layer output” or “region output” is shorthand for firing events produced by Neurons organized by that container. Layers and Regions MUST NOT independently learn, clamp, cross a firing threshold, or acquire a firing identity.

### 4.1 Neuron types

GrowNet currently defines three neuron types:

| Type | Primary purpose |
|---|---|
| Excitatory | Carry signal, support active patterns, drive downstream computation |
| Inhibitory | Dampen instability, suppress runaway activation, stabilize loops |
| Modulatory | Regulate learning, attention-like pressure, growth, and higher-level state |

A complete GrowNet system MUST be able to support all three types, even if some experiments initially emphasize only a subset.

### 4.2 Edge and internal neuron roles

GrowNet SHOULD also distinguish neuron roles by where they live in the structure.

| Role | Meaning |
|---|---|
| Input Neuron | Edge neuron that accepts raw world signals or modality-surface input |
| Integration Neuron | Internal neuron that combines value context, temporal context, anchoring, slotting, novelty, and growth pressure |
| Output Neuron | Edge neuron that emits external-facing outputs, categories, control signals, or future generated modalities |

This distinction matters because the neuron that combines value and temporal context is not an output neuron. It is an integration neuron or local integration circuit inside the active structure.

A base Neuron MUST expose one local scalar input concept. Source dimension, coordinates, shape, and modality belong to source contracts, `InputBinding`s, deliberately constructed populations, mapping, Focus, Anchors, topology, and observation context—not to separate base-Neuron 2D, 3D, image, audio, or video input methods. Specialized shaped populations remain legitimate when they deliver through the ordinary scalar Neuron boundary.

### 4.3 Category Output Neurons and Label Neurons

GrowNet SHOULD distinguish category output from human-readable labels.

| Concept | Meaning | Requirement |
|---|---|---|
| Category Output Neuron | OutputNeuron with `output_role = category` that fires when internal GrowNet structure routes a Focus Segment into a stable category-like output path | MUST be treated as neuronified output structure, not as a softmax class or external classifier slot |
| Category Output Layer | Output-edge layer containing category-role Output Neurons | MAY grow when persistent output-edge novelty and capacity pressure justify new structure |
| Label Neuron | Symbol-side neuron representing a surface name, word, token, or external handle | MUST NOT be treated as the category itself |
| Label Association | Explicit relationship between a Label Neuron and a category-role Output Neuron | SHOULD support one label to many category-role outputs and one category-role output to many labels |

The required conceptual flow is:

```text
Focus Segment
-> internal GrowNet route
-> category-role Output Neuron fires
-> optional Label Neuron association
```

Category output MUST NOT be implemented as a separate classifier algorithm that bypasses GrowNet routing. Category output SHOULD use neuron-native language such as `category.neuron.fire`, `category.neuron.created`, and `category.output.summary`.

Raw visual and multimodal observation payloads MUST NOT carry category labels, object labels, detections, externally supplied Focus Segments, or externally supplied anchors as model truth. Studio, CLI, or supervised workflows MAY request explicit Label Associations, but that surface is separate from raw observation ingestion.

### 4.4 Neuron firing, Connections, and host boundaries

> **Containers organize. Connections carry. Neurons decide and fire.**

Many Neurons MAY fire during the same logical integration interval. A directed Neuron-to-Neuron `Connection` is GrowNet's only targeted internal transmission primitive. The same primitive applies within a Layer and between Layers. A `Connection` MAY carry a contribution and retain approved locally adaptive transmission state under Neuron-owned learning rules; it MUST NOT independently interpret or integrate a population, cross a firing threshold, decide, or fire.

- `InputBinding` MUST remain topology-neutral, non-neural host configuration mapping a named external channel to explicitly existing Neurons or a deliberately constructed population.
- `OutputReadout` MUST remain topology-neutral, non-neural observation of firing events from explicitly designated Neurons or a deliberately constructed population, and MUST remain distinct from diagnostics and full-network instrumentation.
- Neither host surface MAY create hidden neural topology; consume neural RNG; learn, integrate, clamp, cross a threshold, decide, or fire; or supply Focus, Anchor, category, or semantic truth. Creating, deleting, serializing, or reconstructing configuration alone MUST NOT mutate neural structure.

When several contributions reach a Neuron in the same integration phase, the Neuron MUST reduce them deterministically at one declared phase boundary:

```text
integrated_input_j(t) =
    decay_j(prior_state_j) + sum_i(weight_ij * contribution_i(t))

activation_j(t) = soft_clamp_j(integrated_input_j(t))
```

The clamp belongs to the receiving Neuron and is applied after integration. Its exact function and ceiling MAY be configured, but the default clamp SHOULD be smooth, monotonic, sign-preserving, and bounded. This preserves the behavioral meaning of recruiting more Neurons while preventing one Neuron's retained state from becoming unbounded.

Population contributions MUST NOT be averaged by default. Recruitment count can carry information: ten participating Neurons should ordinarily be able to exert more influence than one. Energy cost, local competition, decay, and the receiving Neuron's clamp are the preferred controls on runaway population dynamics.

If several Neurons must jointly produce one thresholded output, their directed `Connection`s MUST converge on an actual relay, release, or output Neuron. That Neuron performs ordinary integration, learning, clamping, thresholding, and firing. An `OutputReadout` only observes the resulting firing event.

A diffuse Modulatory Field remains a separate owner-gated research proposal, distinct from settled Anchor Fields and covert / field Focus. It is not part of the accepted Portless Connectivity runtime. If later accepted, thresholded release MUST originate in Neurons; the Field itself MUST NOT become a hidden Neuron, cross a firing threshold, decide, or fire. Its ownership, delivery, and decay semantics remain unresolved.

## 5. Resource economics and growth ladder

Growth in GrowNet is not free. The architecture assumes increasing energy cost as structural scope increases.

| Creation event | Relative cost | Intended use |
|---|---|---|
| New Slot | Lowest | Cheapest local accommodation of novelty |
| New Neuron | Low | New local computation when slots are insufficient |
| New Layer | Medium | More organized representational depth inside a region |
| New Region | Highest | Rare new domain after persistent unresolved overload or permitted specialization pressure |

This ordering creates a structural economy:

- GrowNet MUST prefer reuse before creation.
- GrowNet MUST prefer smaller structural changes before larger ones.
- Pre-allocation MAY be used for practical experiments.
- The more regions are pre-created, the less likely new regions need to be created later.

The intended cost ordering is strict in principle:

```text
E_slot << E_neuron << E_layer << E_region
```

Exact reserves, multipliers, and ceilings are implementation-defined and belong in configuration or the applicable owner-selected versioned contract when made public.

### 5.1 Structural adaptability controls

Each containment level MUST support a declared structural policy appropriate to the implementation:

- **fixed:** no runtime creation at that level;
- **capped-adaptive:** runtime creation is allowed up to a declared maximum;
- **adaptive:** no user-specified count ceiling, while all physical and architectural constraints remain active.

These policies MAY be selected independently for Slots within Neurons, Neurons within Layers, Layers within Regions, and Regions within GrowNet. “Adaptive” MUST NOT mean physically unlimited: energy availability, creation cost, novelty requirements, cooldowns, deterministic arbitration, memory, and available compute still constrain growth.

GrowNet SHOULD provide meaningful defaults that require no structural tuning from ordinary users. The default profile SHOULD normally use a useful preset, fixed, or conservatively capped Region structure and allow adaptation below each Region. Advanced users MAY enable adaptive Regions, set a maximum Region count, constrain any lower level, or opt into full structural flexibility.

## 6. Learning model

GrowNet is novelty-first.

### 6.1 Novelty before error

The primary trigger for early growth is **novelty in input patterns**, not global prediction error. Error correction and goal-directed optimization may arrive later in development, but the first question GrowNet asks is:

> Have I seen something like this before, and do I still have room for it?

This means GrowNet follows:

**novelty first -> structure first -> optimization later**

rather than:

**error first -> global weight update -> fixed structure forever**

### 6.2 Local learning

GrowNet learning SHOULD remain local whenever possible. The architecture is explicitly motivated by dissatisfaction with fully global backpropagation. This does not forbid future error-based components, but they SHOULD be layered on top of local growth and local adaptation rather than replacing them as the central principle.

### 6.3 Focus Point, Focus Segment, and anchor hierarchy

Repository materials now distinguish a fuller hierarchy:

- **Focus Point:** the currently selected seed or center.
- **Focus Segment:** the locally coherent unit around that point.
- **Segment Anchor:** the local reference that stabilizes that segment.
- **Anchor Trace:** the neuron-local anchoring state and memory associated with local structure.
- **Anchor Field:** the distributed, neuronified anchoring state formed by neuron-local Anchor Traces and Segment Anchors associated with Focus Segments; it preserves currently maintained contextual organization across serial Focus shifts and time.
- **Anchor Map:** GrowNet's system-level conceptual readout of the Anchor Field; a runtime surface MAY materialize a bounded snapshot or index, but the map is not the centralized memory or decision authority.
- Future **Binding** is the separate future mechanism that may establish that multiple Focus Segments belong to one larger entity or interpretation.

This hierarchy SHOULD be maintained because it keeps anchoring local and structure-native. In 2D and beyond, the Focus Segment is the primary meaningful unit, while the Focus Point is usually the seed or center from which that segment is determined. A single pixel is only the degenerate minimal case of a Focus Segment.

### 6.4 Segment boundaries, coherence profiles, and tolerated deviation

GrowNet SHOULD treat segment boundaries as soft rather than purely hard. A Focus Segment is best understood as having a local **coherence profile** or **acceptance profile**: the region around the focused structure within which deviations are still coherent enough to be treated as the same unit.

This means:

- the local anchor or prototype matters,
- tolerated deviation matters,
- continuity in nearby structure matters,
- and competing segment interpretations matter.

A useful working statement is:

> A Focus Segment is not determined by a hard boundary alone, but by a learned local acceptance profile. The segment boundary appears where coherence falls off or a competing interpretation becomes stronger.

This section is partly architectural intent and partly research hypothesis. Exact runtime mechanics for acceptance-profile learning remain open.

### 6.5 Temporal context, signal gaps, observation gaps, and segmented anchoring

Time SHOULD be represented inside GrowNet as contextual input rather than only as an external scheduling rule. An integration neuron or local circuit SHOULD be able to react to:

- the value input,
- the temporal context in which that value arrived.

This leads to segmented anchoring semantics:

- within a coherent short-time segment, the active Segment Anchor SHOULD remain stable by default,
- after sufficiently long elapsed-time context, the next meaningful observation MAY refresh or rebase the active segment anchor.

A crucial distinction is that not all gaps are the same:

- A **signal gap** is part of the signal itself. Morse low-runs are the canonical example.
- An **observation gap** is elapsed time since the last new external observation. Timed scalar interaction is the canonical example.

Timed scalar paths SHOULD distinguish observation gaps from mere repeated held values. Morse paths SHOULD preserve low-run signal-gap semantics.

### 6.6 Serial focus and candidate generation

GrowNet focus SHOULD be treated as a serial active process rather than a dense simultaneous weighting operation. At any instant, the system SHOULD have one active Focus Point seeding one current Focus Segment, even if multiple candidate points are available.

The system MAY maintain multiple candidate focus points at once. Candidate points MAY be generated from:

- energy or saliency,
- novelty relative to current anchors,
- familiarity or recognized usefulness,
- task relevance,
- bounded random choice among strong candidates,
- deterministic sequential scan.

The exact focus policy remains a research parameter, but the architecture SHOULD make the policy explicit.

### 6.7 Neuronified anchoring, anchor fields, and anchor maps

GrowNet SHOULD distinguish between the currently active Focus Point, the active Focus Segment, the local Segment Anchor that stabilizes it, and the more distributed anchoring organization that persists across structure.

The preferred philosophy is neuronified anchoring:

> GrowNet SHOULD prefer local, distributed, neuronified anchoring over centralized bookkeeping.

This means:

- Anchor Traces SHOULD remain close to neuron and segment structure and MAY carry spatial, temporal, or spatiotemporal local anchoring state,
- Segment Anchors SHOULD stabilize their associated Focus Segments,
- Anchor Fields SHOULD emerge from many local Anchor Traces and Segment Anchors and preserve currently maintained context across serial Focus shifts and time, allowing earlier evidence to persist, compete, decay, or be revised,
- Anchor Maps SHOULD be treated as system-level conceptual readouts of those fields. A runtime `AnchorMap` MAY materialize a bounded snapshot or index, but it MUST NOT become GrowNet's sole memory, interpretation, familiarity/novelty, or decision authority.

Contextual coexistence in an Anchor Field or its Anchor Map readout does not establish that multiple Focus Segments belong to one larger entity or interpretation. That relationship belongs to future perceptual Binding. Perceptual Binding is separate semantic work and is not `InputBinding`; host configuration supplies no Focus, Anchor, category, or semantic truth.

### 6.8 Temporal compression

Explicit time at lower levels SHOULD be allowed to remain explicit. Ticks, pulse runs, gaps, frame-to-frame continuity, and local temporal segments MAY all be represented directly at low levels. Later, higher levels MAY absorb that explicit temporal structure into more compact stabilized representation.

This temporal compression is expected rather than contradictory. Time may begin explicit and later become compressed.

### 6.9 Covert vs overt focus

GrowNet SHOULD support **covert / field focus**, meaning a shift in processing priority without mechanical movement. Embodied or robotic GrowNet systems MAY additionally support **overt / mechanical focus**, meaning a physical reorientation of sensors or effectors toward a selected target.

Overt focus SHOULD be treated as more expensive than covert focus and MAY be reserved for cases where recentering perception or action is useful.

### 6.10 Revisit and inhibition of return

To avoid pathological fixation on one salient point, GrowNet MAY implement bounded revisit suppression or inhibition of return. This would bias the focus policy away from immediately reselecting the same point unless task relevance or persistent evidence justifies it.


## 7. Connectivity and routing

### 7.1 Default routing principle

GrowNet currently supports **proximity connections**. The default rule is:

> If nearby capacity exists, connect to it first.

This rule is important for three reasons:

- It reduces latency and structural sprawl.
- It encourages clustered microcircuits.
- It supports stable specialization.

### 7.2 Determinism vs initial exploration

Connection routing SHOULD tend toward determinism, but the very first connection does not need to be perfectly predetermined. A practical working view is:

- Initial connection formation MAY involve bounded exploratory choice.
- Once a usable routing pattern is established, replay and future routing SHOULD be deterministic.

This mirrors the observation that biological growth looks exploratory at first but stabilizes later.

### 7.3 Cross-region connections

GrowNet MAY later support sparse Neuron-to-Neuron `Connection`s across Region membership boundaries. Their identity, ownership, lifetime, delivery ordering, and execution remain separately owner-gated; Regions themselves MUST NOT become connected signal processors.

## 8. Tick and state semantics

GrowNet uses a conceptual phase-separated tick discipline so that every receiver integrates a stable set of contributions and every growth candidate is evaluated against the same pre-growth structure.

Here, a tick is a logical integration and growth-arbitration boundary. It is not automatically a wall-clock instant, source tick, temporal-context tick, Focus step, timestamp, Region logical-operation identity, or global synchronous scheduler step. Those authorities answer different questions and MUST NOT be substituted for one another. This conceptual discipline does not select or rewrite cross-Region delivery ordering.

### 8.1 Tick structure

A complete tick SHOULD conceptually contain:

1. **Collect and deliver:** buffer all contributions assigned to the current integration phase.
2. **Integrate locally:** deterministically reduce contributions per Neuron, apply retained-state decay, perform Slot selection or reinforcement, apply the Neuron's soft clamp, and decide whether that Neuron fires.
3. **Propagate:** buffer the resulting Neuron firing events for their declared destination phase.
4. **End-of-tick arbitration:** evaluate growth requests from the stable pre-growth state and commit the permitted structural transaction.

Many Neurons MAY fire in the same tick. Contribution reduction, firing, and growth selection MUST NOT depend on collection traversal order, thread scheduling, or container iteration order.

### 8.2 Growth timing

Neuron and Layer growth MUST occur at the deterministic end-of-tick arbitration point, not in the middle of signal propagation. A structural addition MUST become visible only at the phase boundary declared by the runtime.

### 8.3 Safety invariant

Within one tick, a Region MAY collect any number of Neuron-growth and Layer-growth requests. The Region MUST deterministically select and commit **at most one Neuron-or-Layer structural growth transaction per tick**. Stable identifiers, declared priorities, persistence, energy, and cooldown MAY participate in the arbitration; traversal order MUST NOT.

Creation of the selected element together with its required initial wiring counts as one atomic transaction. Private Slot allocation is owned by its Neuron and MUST NOT consume the Region-wide action. Neuron firing, weight updates, reinforcement, decay, and other non-structural learning MUST NOT consume it. Region creation is a separate, rare GrowNet-level action and is not charged to an existing Region's budget.

No Neuron, Layer, Region, `Connection`, host binding or readout, or implementation shortcut MAY bypass the Region's arbiter for a Neuron-or-Layer creation. Valid requests not selected MAY remain eligible on later ticks.

This invariant:

- makes all candidates observe one pre-growth regional state;
- prevents a single novelty event from cascading through multiple structural levels in one tick;
- bounds instantaneous energy and allocation work;
- and preserves reproducibility across traversal orders, parallel schedules, and language implementations.

## 9. Formal growth rules

The following are the current intended rules.

### 9.1 Slot allocation

A Neuron MAY allocate a new private Slot when:

- the input pattern maps to a genuinely new local bin or concept, and
- strict slot capacity has not yet been reached.

If the input can be handled by an existing slot, GrowNet SHOULD adapt that slot instead.

Slot allocation is a private Neuron mutation. It does not create a public network node and does not consume the Region-wide growth transaction.

### 9.2 Neuron growth

A Layer SHOULD submit or accept a request to create a new Neuron when:

- a new slot is required,
- the seed neuron is already at strict slot capacity,
- fallback or overflow pressure persists, and
- cooldown and energy rules allow growth.

The containing Layer owns the Neuron creation commit. Neuron growth SHOULD create a Neuron of the **same kind** unless a future policy explicitly states otherwise.

### 9.3 Layer growth

A Region SHOULD create a new Layer when Neuron-level pressure has become structurally meaningful within that Region. This is expected to reflect repeated local saturation, not a single novelty event. The Region owns the Layer creation commit.

### 9.4 Region growth

A new Region SHOULD be rare. GrowNet MAY create one only when all applicable conditions hold:

- existing Regions and dormant capacity cannot be reused adequately;
- pressure or overload persists rather than appearing for one transient event;
- the proposed organization is sufficiently distinct, or existing organization remains persistently overloaded;
- global energy, resource, and cooldown rules permit creation;
- and the configured Region policy and maximum permit creation.

A newly created region SHOULD begin with a **minimal scaffold**, not a full mature architecture.

GrowNet, not an existing Region, owns Region creation. A Region MAY report pressure upward but MUST NOT create a peer Region directly.

### 9.5 Pre-creation

Slots, Neurons, Layers, or Regions MAY be pre-created if an experiment benefits from scaffolding. Pre-creation is a practical option, not a rejection of GrowNet's self-organizing philosophy. In normal use, Regions SHOULD generally be preset, fixed, reserved, or conservatively capped, while structure below them remains adaptive under the selected policy.

## 10. Feedback loops and control

A major open design theme in GrowNet is how novelty-driven growth turns into goal-directed control.

### 10.1 Control intuition

Balancing a stick is the canonical example. A stable system must:

- sense current state,
- act on the environment,
- observe whether stability improved or worsened,
- repeat rapidly.

Humans balance through nested feedback loops. GrowNet is expected to form such loops rather than having them entirely hand-designed.

### 10.2 Automatic loop formation

Feedback loops are expected to emerge when three ingredients exist:

1. Perception of state
2. Ability to act
3. Detection of stability or instability

Once those exist, local sensor -> action -> result circuits can become specialized microcircuits.

### 10.3 Role of neuron types in control

- Excitatory neurons drive action paths.
- Inhibitory neurons damp oscillation and stabilize loops.
- Modulatory neurons adjust pressure, learning, and regulatory state.

### 10.4 First control benchmark

An inverted pendulum or similar balancing problem SHOULD be treated as a primary early control benchmark for GrowNet.

## 11. Regions, specialization, and plasticity

A Region is a first-class organizational boundary, not a larger Neuron, an independently firing computational unit, or a second targeted signal path. Its significance comes from the Layers it organizes and the policy, energy, specialization, lifecycle, and growth-arbitration scope it establishes.

### 11.1 Why regions exist

Region boundaries may be useful for two reasons:

- Different input type or modality
- Functional specialization over time

Regions are organizational containers that MAY carry functional or modality-level policy. The function is realized by their Neurons and circuits, not by a Region-level firing mechanism.

### 11.2 Region structure

A Region SHOULD support dense organization among its contained structure and selective `Connection` policy across organizational boundaries. It MUST remain an organizational container: directed `Connection`s carry targeted contributions, and only Neurons integrate, learn, clamp, threshold, decide, and fire. Cross-Region `Connection` execution remains separately owner-gated.

### 11.3 Plasticity analogy

The observation that other brain areas can sometimes take over after damage is conceptually important for GrowNet. This suggests that functions can migrate or be re-established elsewhere when the architecture preserves reusable latent structure.

GrowNet SHOULD therefore value reorganization and takeover over immediate deletion.

## 12. Pruning, dormancy, reuse, and late death

### 12.1 Pruning rule

Unused connections for a long time SHOULD be pruned.

In plain terms:

> Use it or lose it.

Pruning applies first to **connections**, not directly to neurons.

### 12.2 Neuron lifecycle

| State | Meaning |
|---|---|
| Active | Participating in live circuits |
| Dormant | Neuron still exists but currently lacks useful active connections |
| Reused | Dormant neuron is reconnected and participates again |
| Long-idle | Dormant for a very long time, never reclaimed |
| Late death | Optional later-stage removal after extreme inactivity |

### 12.3 Reuse rule

A dormant neuron MAY be reused if conditions are met. Importantly, when a neuron is reused, it keeps its **previous internal state** rather than being wiped clean.

This is a defining design choice.

### 12.4 Late neuron death

Neuron death is not the default outcome of pruning. Late death MAY occur only much later if a neuron remains dormant, never reconnects, and continued retention no longer makes structural or energy sense.

## 13. Memory and access paths

One guiding intuition behind GrowNet is that memory is not just storage, but also routing.

A useful design belief is:

> A system may fail to retrieve something not because the underlying memory vanished, but because the path to it degraded.

This is inspired by observing degenerative memory loss up close, but here it is used only as a systems intuition, not as a clinical claim.

GrowNet's dormant-neuron model aligns with this intuition by preserving latent substrate whenever possible. This may allow reactivation, faster relearning, or takeover by other circuits.

## 14. Knowledge Units and Bad Knowledge Units

The repository introduces **Knowledge Units (KU)** and **Bad Knowledge Units (BKU)** as evaluation concepts.

### 14.1 Knowledge Units

A Knowledge Unit measures how much **correct, generalizable structure** the model extracts from a training example.

- Approximately **1.0 KU per sample** corresponds to literal memorization and little else.
- Greater than **1.0 KU** indicates that the model extracted correct implications beyond the literal sample.

### 14.2 Bad Knowledge Units

BKU measures how much **incorrect or harmful structure** the model extracts from a sample, such as hallucinated facts or biased stereotypes.

### 14.3 Desired profile

GrowNet should aim for:

- high KU
- low BKU

A useful derived measure is knowledge precision:

**Knowledge Precision ≈ KU / (KU + BKU)**

### 14.4 Why KU/BKU matter for GrowNet

Because GrowNet literally allocates new structure when novelty appears, evaluation should not only ask whether it performs well after training. It should also ask:

- how much good knowledge was gained per sample,
- how much bad knowledge was created per sample,
- and how efficiently structural growth translated into reusable understanding.

## 15. Prototype roadmap

The most realistic first successful GrowNet prototypes are expected to be in simulated 3D environments.

### 15.1 First proving ground

A simple 3D object moving around a 3D space, possibly in Blender, is the preferred early prototype. The environment may provide:

- camera or image input,
- distance / collision information,
- velocity and orientation,
- action outputs such as movement, turning, force, or torque.

### 15.2 Target behaviors

Early experiments SHOULD focus on:

- exploration,
- spatial memory,
- obstacle avoidance,
- balancing / stabilization,
- eventually manipulation and robotics-oriented control.

### 15.3 Why robotics matters

Robotics and world models are expected to benefit the most from GrowNet because they stress:

- ongoing time,
- novelty,
- adaptation,
- control,
- and structural development under open-ended conditions.

## 16. Long-term direction

GrowNet is aimed at more than passive intelligence.

### 16.1 Active intelligence

Active intelligence means the system remains aware of time, carries state, maintains a world model, and does not simply wake up for a single query and then disappear.

### 16.2 Emotion-like regulation

In GrowNet, emotions are best viewed not as human-style subjective feelings, but as repeated activation of regulatory circuits or regions that bias behavior and learning.

This is powerful and potentially dangerous. It suggests a future class of systems that are more agent-like than today's tools.

### 16.3 Sleep and consolidation

Future GrowNet systems MAY include sleep-like or consolidation phases during which circuits are stabilized, reorganized, or replayed.

### 16.4 Ecosystem view

The long-term future is not expected to be one giant AI, but many different AIs living among us with different strengths. GrowNet is one possible path toward more active, structured, and adaptive forms of artificial intelligence.

## 17. Non-goals

The following are explicitly **not** current requirements:

- GrowNet is not required to replace all deep learning.
- GrowNet is not required to beat transformers at every language task.
- GrowNet does not currently claim true consciousness.
- GrowNet does not require that every biological mechanism be copied literally.
- GrowNet is not yet a finalized architecture.

## 18. Open questions

The following remain open:

1. How exactly should novelty-driven development transition into goal optimization?
2. What is the best stability or homeostasis signal for balancing-type control?
3. How exploratory should first-time connection formation be?
4. When should reuse win over fresh creation?
5. How should long-range cross-region routing evolve without destabilizing the system?
6. What should sleep / consolidation look like operationally?
7. Under what exact conditions should late neuron death happen?
8. What is the right benchmark suite to show GrowNet's advantages clearly and fairly?
9. How should modulatory neurons be formalized for emotion-like regulatory loops without making the system unsafe?
10. What focus policy should dominate when strong saliency, novelty, and familiarity all compete?
11. How should coherence profiles or receptive widths bootstrap locally and later adapt?
12. How should signal gaps, observation gaps, and segment rebasing interact without becoming ad hoc?
13. How should future Binding relate multiple Focus Segments into larger entities without breaking locality?
14. How should covert focus and overt focus interact once GrowNet is embodied?
15. When should persistent output-edge novelty grow a new category-role Output Neuron, and how should Label Associations remain separate from category formation?

## 19. Concise formal definition

> **GrowNet** is a novelty-driven, growth-based neural architecture in which local structure is the primary adaptive medium. It begins with a minimal scaffold and allocates capacity only when local saturation and persistent novelty justify it. Neurons privately organize Slots and own learning, clamping, thresholding, and firing; `Connection`s may retain only approved local transmission state under Neuron-owned rules. Layers organize Neurons, Regions organize Layers, directed `Connection`s carry targeted internal contributions, and topology-neutral host bindings and readouts map or observe explicit neuronal populations without hidden topology or computation. GrowNet interprets incoming structure through serial focus and anchoring, routes stable Focus Segments toward category-role Output Neurons while keeping human-readable labels separate as Label Neurons and associations, regulates behavior through excitatory, inhibitory, and modulatory dynamics, prunes unused `Connection`s while preserving dormant reusable substrate, and aims toward active, continuously adapting intelligence for agents, world models, and robotics.

## Appendix A. Minimal invariants

The following are the current minimal invariants for the architecture:

- Learning SHOULD be local-first.
- Novelty SHOULD trigger growth before global error does.
- Slots MUST remain private to their owning Neuron; they MUST NOT be `InputBinding` or `OutputReadout` targets, form `Connection` endpoints, or fire.
- Neurons MUST own learning, integration, clamping, thresholding, and firing; `Connection`s MAY retain only approved local transmission state under Neuron-owned rules, and Layers and Regions MUST remain organizational containers.
- A directed Neuron-to-Neuron `Connection` MUST remain the only targeted internal transmission primitive. `InputBinding`s and `OutputReadout`s MUST remain topology-neutral, non-neural host configuration and selected-firing observation surfaces.
- A receiving Neuron MUST deterministically integrate same-phase weighted contributions before applying its local clamp and firing decision.
- Population contributions MUST NOT be averaged by default.
- Growth MUST prefer smaller structural changes before larger ones.
- Structural creation ownership MUST follow containment: Neuron creates Slot, Layer creates Neuron, Region creates Layer, GrowNet creates Region.
- Each Region MUST commit at most one Neuron-or-Layer growth transaction per tick through deterministic end-of-tick arbitration.
- Private Slot allocation and normal neuronal activity MUST NOT consume the Region-wide growth transaction.
- Region creation MUST remain a separate, rare GrowNet-level decision governed by policy, resources, persistence, and cooldown.
- Every structural level MUST support a declared fixed, capped-adaptive, or adaptive policy where implemented; meaningful defaults SHOULD keep Regions stable and allow adaptation below them.
- Proximity SHOULD be the default connection bias.
- Active focus SHOULD be serial even when multiple candidate points are remembered.
- Covert / field focus SHOULD be supported before overt / mechanical focus is required.
- Category output SHOULD be represented by category-role Output Neurons, not by an external classifier head.
- Label Neurons and Label Associations SHOULD remain separate from category formation and raw observation truth.
- Pruning SHOULD remove unused connections before removing neurons.
- Neuron reuse SHOULD preserve prior internal state.
- Region creation SHOULD begin from a minimal scaffold.
- KU and BKU SHOULD be part of future evaluation.
- Active intelligence is a long-term direction, not a present claim.

## Appendix B. Relationship to the journal

The Word edition of the journal and the Word edition of this specification are GrowNet's joint primary conceptual authority. Their Markdown editions are synchronized secondary representations.

- The journal captures origin, intuition, philosophical motive, and exploratory thought.
- The formal spec captures structure, invariants, lifecycle, and implementation-guiding language.
- Applicable owner-selected versioned machine contracts capture machine-facing interfaces within their declared activation scopes and the conceptual limits set here.
- Handoff packages capture orientation, history, and current implementation status; they are not canonical authority.

Both primary documents MUST evolve together. New concepts normally enter both Word editions as one coordinated change, then synchronize to Markdown and, where machine-facing, to the applicable owner-selected versioned contract. A later owner-accepted ADR MAY temporarily amend only exact named wording until incorporation; synchronization alone MUST NOT activate a contract or authorize implementation.
