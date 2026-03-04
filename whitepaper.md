# Proof of Legacy Memory (PoLM)
## Whitepaper v1.0

---

# Abstract

Proof of Legacy Memory (PoLM) introduces a new category of consensus based on bounded latency-weighted probabilistic selection. Unlike traditional Proof-of-Work systems that reward computational throughput and parallel scaling, PoLM limits structural dominance by weighting block selection probability using a clamped latency factor.

By bounding influence within strict mathematical limits, PoLM restores competitive relevance to legacy hardware without penalizing modern systems. Block rewards follow a deterministic halving schedule independent of latency, preventing dual structural bias.

Simulation results demonstrate convergence toward stable probabilistic equilibrium with mathematically enforced dominance limits.

PoLM represents a shift from computational escalation to structural balance.

---

# 1. Introduction

Modern distributed consensus systems reward throughput, parallelism, and hardware specialization. This has led to:

- ASIC centralization  
- GPU farm dominance  
- Hardware arms races  
- Economic barriers to participation  

PoLM challenges this trajectory.

> Restore relevance to legacy hardware.

Rather than maximizing computational escalation, PoLM reduces structural dominance by introducing bounded latency-weighted probability.

---

# 2. Design Philosophy

## 2.1 Restore Relevance to Legacy Hardware

Technological progress has created economic obsolescence for functional machines. PoLM restores structural competitiveness without enforcing artificial equality.

Latency becomes signal.  
Throughput becomes secondary.

## 2.2 Structural Fairness Without Artificial Equality

PoLM does not:

- Identify hardware types  
- Classify CPUs or memory  
- Apply artificial penalties  

Instead, it introduces bounded probabilistic weighting.

## 2.3 Diversity as Decentralization

True decentralization requires hardware diversity, not just node distribution. PoLM promotes computational diversity by limiting structural amplification.

---

# 3. System Model

PoLM is not a variant of PoW or PoS.  
It defines a new category: Latency-Weighted Probabilistic Consensus (LWPC).

## 3.1 Network Assumptions

- Open participation  
- No trusted hardware identification  
- Local latency measurement  

## 3.2 Latency as Physical Constraint

Throughput scales economically.  
Latency scales physically.

PoLM anchors consensus to bounded latency influence.

---

# 4. The LWPC Model

## 4.1 Latency Normalization

Let:

- Lᵢ = measured latency  
- L₀ = baseline latency  

Raw ratio:

rᵢ = Lᵢ / L₀

Clamped factor:

fᵢ = min(max(rᵢ, α), β)

Where:

α = 0.90  
β = 1.10  

Thus:

fᵢ ∈ [0.90, 1.10]

## 4.2 Probabilistic Block Selection

Block probability:

Pᵢ = fᵢ / Σ fⱼ

## 4.3 Dominance Bound

For two nodes:

Pₘₐₓ = β / (β + α)

With α = 0.90 and β = 1.10:

Pₘₐₓ ≈ 55%

No node can exceed structural dominance beyond this bound due to latency alone.

## 4.4 Emission Model

Block reward:

R(n) = R₀ / 2^(floor(n / H))

Reward is independent of latency.

---

# 5. Security and Attack Analysis

## 5.1 Threat Model

- Open network  
- Rational actors  
- No trusted hardware reporting  

PoLM bounds structural advantage; it does not eliminate adversarial behavior.

## 5.2 Latency Manipulation

Latency factor is clamped. Artificial delay beyond upper bound yields no additional benefit. Structural gain is capped at 10%.

## 5.3 Throughput Amplification

Parallel scaling does not increase latency factor beyond β. Structural dominance remains bounded.

## 5.4 Sybil Behavior

Splitting hardware into multiple nodes does not increase aggregate structural weight under equal resource constraints.

## 5.5 Early Emission Skew

Halving schedules create early reward asymmetry. This is consistent with emission-based systems.

## 5.6 Structural Dominance Bound

Latency weighting alone cannot exceed approximately 55% dominance in two-node competition.

## 5.7 Limitations

- Requires empirical benchmarking  
- No adaptive baseline yet  
- Network-layer Sybil resistance not implemented  

---

# 6. Conclusion

PoLM introduces a new consensus paradigm grounded in bounded probabilistic latency weighting. It restores structural relevance to legacy hardware while preserving competitive equilibrium.

Rather than enforcing equality, PoLM limits inevitability.

From throughput supremacy to structural balance.  
From hardware privilege to hardware diversity.

---

# 7. Future Work

- Empirical hardware benchmarking  
- Adaptive baseline calibration  
- Full P2P network implementation  
- Extended economic simulations  
- Formal game-theoretic analysis  

---

**Proof of Legacy Memory — Restore relevance to legacy hardware.**
