# GrowNet

*Journal reference assembled from design discussion and working architectural notes.*

Prepared for ongoing research reflection, implementation planning, and future paper / website drafting.

**Status:** living internal document — captures current thinking, not final claims.

> **Working summary**  
> GrowNet is envisioned as a growth-based neural architecture that starts very small, expands only when novelty justifies it, uses local structure, serial focus and anchoring, and energy constraints to regulate development, and aims toward continuous, active intelligence rather than today’s passive input-output systems.

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

The architecture currently revolves around four scales of structural creation. Each step up the ladder is more expensive, so the system naturally tries the cheapest form of adaptation first.

| Level | Meaning | Typical use | Relative cost |
|---|---|---|---|
| Slot | Small local memory cell inside a neuron | Store / route a new local pattern before larger structural change | Lowest |
| Neuron | Local computational unit | Add specialized local capacity when slots are no longer enough | Low |
| Layer | Feature / abstraction organization inside a region | Increase depth and representational capacity inside a domain | Medium |
| Region | Higher-order organizational domain | Create or connect to a new functional container when a region has become too deep | Highest |

## Neuron types

- **Excitatory:** carries signal and helps form active patterns and forward influence.
- **Inhibitory:** dampens activity, prevents runaway activation, and stabilizes loops.
- **Modulatory:** regulates learning, growth pressure, attention-like behavior, and higher-level control signals.

This triad is important because GrowNet is not only about storing patterns. It also needs to regulate growth, suppress instability, and eventually support emotion-like or state-like dynamics.

# 4. Growth rules and region logic

Growth is novelty driven. Novelty is the primary trigger in early development. Error and goal-directed optimization can come later, but the architecture first asks whether a pattern is genuinely new and whether existing structure still has enough capacity to absorb it.

Connection routing tends to be deterministic once a direction is chosen, but the very first connection does not need to be perfectly predetermined. A practical current rule is proximity routing: if there is capacity nearby, connect to it first.

This local preference is both biologically inspired and architecturally stabilizing. It encourages clustered microcircuits, shorter signal paths, and natural specialization.

## Region creation rule

A region is not merely another stack of layers. It is a higher-level organizational boundary, often corresponding to a substantially different type of input or computation. In practice, region pressure is driven by layer capacity: if one region accumulates too many layers, the system should create or connect to a new region rather than keep deepening the same one indefinitely.

- Region motivation = modality separation plus functional specialization.
- A new region begins with a minimal scaffold rather than a full prebuilt structure.
- Pre-creating more regions reduces the chance that new regions need to be created later.

## Scaffold vs emergence

GrowNet supports both developmental emergence and scaffolding. In one mode, the network starts with very little and grows structure organically. In another mode, regions or other structures may be pre-created to guide early organization. This allows practical experimentation without giving up the larger philosophy of self-organization.

# 5. Connectivity and feedback loops

A major open design question is how novelty-driven growth transitions into goal-directed control. The example discussed was balancing a falling stick by applying counter-force. Humans do this through fast nested feedback loops, so the GrowNet question becomes: how can feedback loops arise automatically rather than being manually wired in?

The likely answer is that loops emerge once three ingredients exist: perception of state, ability to act, and a way to detect stability or instability. From there, repeated useful sensor-action-result cycles can become micro-circuits.

## Current stance on connectivity

> **Connection principle**  
> Initial growth may not be fully predetermined, but routing should bias strongly toward nearby available capacity. This is the closest current analogue to how biological growth cones explore locally before locking into usable paths.

Because the architecture already includes excitatory, inhibitory, and modulatory neurons, GrowNet has the ingredients needed for local feedback loops: excitation to drive action, inhibition to damp oscillation, and modulation to alter learning and control pressure.

The long-term expectation is that balancing, navigation, and other control behaviors would be handled by specialized local circuits rather than giant end-to-end policies.


## Focus, anchoring, and serial inspection

Focus in GrowNet is not the same thing as transformer-style attention. In transformer models, attention is largely a weighting-and-aggregation mechanism over many candidates at once. GrowNet focus is better understood as an active local inspection process: the system generates candidate focus points, selects one point at a time, interprets incoming structure relative to that point, and preserves meaningful locations through anchors rather than through one-shot global mixing.

A useful intuition is a black screen with one bright pixel. Focus naturally locks there. If several bright pixels appear, focus does not need to process them literally simultaneously. A more realistic view is rapid serial inspection: the system picks one candidate point, anchors briefly, updates its internal map, and then moves to the next point. This lets GrowNet build a remembered map of multiple important locations while still keeping active focus singular at any moment.

Candidate focus points may be chosen by several policies:

- highest energy or strongest saliency first,
- novelty-first when something strongly departs from current anchors,
- familiarity-first when known structure is behaviorally important,
- bounded random choice among strong candidates,
- sequential scan or convolution-like traversal for structured scenes.

This means focus is governed by a policy, not only by raw intensity.

Two forms of focus seem especially useful. **Mechanical focus** is overt reorientation: turning the head, eyes, camera, or body toward a target. This is especially relevant for agents and robotics. **Field focus** is covert reprioritization without movement: processing shifts toward a location even though the sensor itself does not move. Field focus should exist from the beginning. Mechanical focus can come later when GrowNet is embodied.

Under this view, anchoring becomes critical. Focus answers: *what point is active right now?* Anchoring answers: *what important points or frames have already been established?* GrowNet likely needs not only an active focus point, but also a small anchor map of currently meaningful locations. That map can support revisit, comparison, and control without forcing the system to recompute the whole scene globally at each tick.

Architecturally, focus should happen before slot selection. Raw input should first be interpreted relative to current focus and anchor state. Only then should slot routing decide whether the pattern is familiar, close to an existing bin, or novel enough to trigger fallback pressure or growth. In this sense, focus is not merely perceptual; it is part of the novelty and structure-allocation machinery itself.

Some practical consequences follow naturally:

- repeated nearby inputs should encourage reuse of the same slots,
- large departures from current anchors should raise fallback pressure,
- anchor maps should let GrowNet preserve several meaningful locations while inspecting them one at a time,
- future sensorimotor systems may use covert focus first and overt focus second.

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

# **7. Memory, access paths, and retrieval failure**

An important intuition behind part of the design is that forgetting may sometimes be less about memory disappearing and more about losing the path to it.
This is not presented as a scientific or clinical claim. It is better understood as a systems intuition: memory may depend not only on stored structure, but also on whether active routes still exist that can reactivate that structure. GrowNet’s dormant-and-reusable neuron idea aligns with that view.

From this perspective, the architecture benefits from preserving latent substrate whenever possible. Connections can fade. Access routes can weaken. Yet the system may still retain historical structure that could, under the right conditions, become useful again.

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
- How should covert / field focus and overt / mechanical focus interact once GrowNet becomes embodied?

# 12. Concise working definition

> **GrowNet, in one paragraph**  
> GrowNet is a growth-based neural architecture that starts with minimal structure and expands only when novelty and capacity pressure justify it. It uses slots, neurons, layers, and regions as different scales of development; relies on excitatory, inhibitory, and modulatory neurons for computation and regulation; uses serial focus and anchoring to interpret input relative to active local reference frames; favors local proximity-based organization; prunes unused connections while preserving dormant structure for possible reuse; and aims toward active, continuously running intelligence suited for agents, robotics, and world-model systems rather than only passive one-shot inference.

# 13. Notes for future updates

This document should be treated as a living journal reference. It captures the state of the ideas expressed in the discussion that produced it. Future versions could add diagrams, formal growth contracts, mathematical notation, Blender prototype details, benchmark plans, and a separate section distinguishing settled design decisions from speculative hypotheses.

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
| One region accumulates too much depth | **Create or connect to a new region** | Expand into a new organizational domain rather than forcing infinite depth into one region. |

## Growth ladder under the Golden Rule

The repository phrasing maps very naturally onto the journal’s existing growth ladder:

- **Slot:** cheapest local adaptation.
- **Neuron:** next step when slots are saturated and novelty persists.
- **Layer:** added when local neuron pressure has become structurally meaningful.
- **Region:** added or connected when a region has become too deep or when specialization / modality separation demands a new container.

This is one of the most important features of GrowNet: growth is **targeted and bounded**. The architecture does not simply become larger everywhere. It expands where novelty appears and where existing capacity has truly run out.

## Focus anchor vs reference anchor

One useful clarification from the repository docs is the distinction between several related concepts:

- **Focus Anchor (conceptual):** the currently active point or frame that the system is inspecting in behavioral terms.
- **Reference Anchor (implementation):** the stable **FIRST** anchor used to compute delta-percent and novelty bins deterministically.
- **Anchor Map (working extension):** a small remembered set of meaningful locations or frames that remains available while active focus moves serially.

This is a subtle but valuable distinction. It allows GrowNet to talk naturally about current focus while still preserving a stable internal reference point for repeatable slot selection and routing.

A further clarification from later discussion is that focus should be treated as **serial**, not literally simultaneous. Multiple candidate points may exist at once, but active focus inspects them one at a time. Candidate selection MAY be driven by highest energy, novelty-first, familiarity-first, bounded random choice among strong candidates, or deterministic sequential scan. For embodied systems, GrowNet may also distinguish **field / covert focus** (priority shift without movement) from **mechanical / overt focus** (turning eyes, head, camera, or body toward the selected point).

## Stability and determinism constraints

The Golden Rule is not only about growth. It is also about *how to keep growth sane*.

Important accompanying constraints from the repo material:

- growth is **local** rather than global,
- growth is **rate-limited** by cooldowns and capacity rules,
- routing should remain **deterministic** once chosen,
- the system should avoid turning novelty into uncontrolled structural explosion,
- and at the region level there should be a strong safety invariant such as **one growth action per region per tick**.

This matches the spirit of the original journal: GrowNet should feel alive and developmental, but not chaotic.

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

Conceptually, KU and BKU can become the evaluation language for GrowNet’s long-term claims:

- how much useful structure is gained from each novel input,
- how cleanly local growth converts novelty into knowledge,
- whether GrowNet can outperform conventional architectures in *knowledge yield per sample* rather than merely final benchmark score.

That makes KU / BKU a very strong fit for GrowNet’s broader research narrative.
