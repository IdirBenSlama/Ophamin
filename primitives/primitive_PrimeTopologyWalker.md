# Primitive Profile — `Walker`

**Canonical class:** `PrimeTopologyWalker`  
**Family:** brain, topology, coordination  
**Kimera commit:** `179edd233c15`  
**Captured at:** 2026-05-15T14:13:06.004021+00:00

## Location

- File: `kimera_swm/domain/cognitive/prime_topology_walker.py`
- Line: 242

## Docstring

```
Physics-driven agentic graph-search agent.

The walker traverses a prime-topology graph using the four neuromorphic
mechanisms from Phase 58 as its decision logic. Decision-making (which
concept to commit to, when to halt, when to roll back, when to leap)
emerges from the oscillator dynamics of CognitiveRhythm. Three documented
safety nets — death_debounce (transient-coherence filter), neighborhood-
exhaustion fallback (jump to nearest_unvisited when local edges are
fully visited), and stall-jump after 20 idle ticks (prevent budget
exhaustion when gamma never leads) — provide bounded escape from
pathological substrate states without overriding the M1-M4 gates that
fire when conditions are met.

Usage
-----
::

    walker = PrimeTopologyWalker(n_nodes=30, start_node=0)
    state  = walker.traverse(max_steps=50, latency_per_hop=0.003)
    print(state.trajectory, state.rollbacks, state.halt_reason)
```

## Methods

- `__init__`
- `traverse`

## Adapter wiring

- Target: `walker` (unavailable)

## Callers

- Total mentions in the repo: 35
- Top references:
  - `kimera_swm/domain/cognitive/pulse.py:15` — `↓ Step 3-4: TRAVERSAL      PrimeTopologyWalker.traverse() → WalkerState`
  - `kimera_swm/domain/cognitive/pulse.py:75` — `from kimera_swm.domain.cognitive.prime_topology_walker import PrimeTopologyWalke`
  - `kimera_swm/domain/cognitive/pulse.py:76` — `return PrimeTopologyWalker`
  - `kimera_swm/domain/cognitive/pulse.py:734` — `Wires SemanticGeoidBridge (Phase 60) → PrimeTopologyWalker (Phase 59/60)`
  - `kimera_swm/domain/cognitive/pulse.py:5762` — `Run PrimeTopologyWalker on the GeoidGraph.`
  - `kimera_swm/domain/cognitive/pulse.py:5795` — `PrimeTopologyWalker = _get_walker_class()`
  - `kimera_swm/domain/cognitive/pulse.py:5906` — `walker = PrimeTopologyWalker(start_node=start_nid, graph=graph)`
  - `kimera_swm/domain/cognitive/takwin.py:15` — `↓ Step 3-4: TRAVERSAL      PrimeTopologyWalker.traverse() → WalkerState`
  - `kimera_swm/domain/cognitive/takwin.py:196` — `from kimera_swm.domain.cognitive.prime_topology_walker import PrimeTopologyWalke`
  - `kimera_swm/domain/cognitive/takwin.py:198` — `return PrimeTopologyWalker`

