# AI Risk Analyst — Methodology & Mathematical Scoring Framework

## 1. Overview
The **AI Risk Analyst** platform relies on an objective, reproducible, and explainable risk quantification engine aligned with the **ISO 31000:2018 Enterprise Risk Management** and **COSO ERM** standards.

---

## 2. Multi-Factor Risk Severity Formula

Severity is determined through a multi-factor composite formula evaluated on a continuous $1.0$ to $5.0$ scale:

$$\text{Composite Score } (S) = (Impact \times 0.35) + (Probability \times 0.25) + (Urgency \times 0.25) + (Evidence \times 0.15)$$

### Dimension Definitions:
1. **Impact ($I \in [1, 5]$):**
   - $1$: Negligible operational friction
   - $2$: Minor project delay ($< 1$ week)
   - $3$: Significant budget overrun ($10-25\%$) or SLA penalty
   - $4$: Severe customer churn ($> 25\%$) or regulatory notice
   - $5$: Catastrophic insolvency, major data breach, or business shutdown
2. **Probability ($P \in [1, 5]$):**
   - $1$: Rare ($< 10\%$)
   - $2$: Unlikely ($10-30\%$)
   - $3$: Possible ($30-60\%$)
   - $4$: Likely ($60-90\%$)
   - $5$: Almost Certain ($> 90\%$ or already ongoing)
3. **Urgency ($U \in [1, 5]$):**
   - $1$: Low ($> 6$ months to material impact)
   - $2$: Moderate ($3-6$ months)
   - $3$: High ($1-3$ months)
   - $4$: Very High ($14-30$ days)
   - $5$: Immediate ($< 14$ days)
4. **Evidence Quality ($E \in [1, 5]$):**
   - $1$: Unverified hearsay or vague statement
   - $2$: General user assertion without specific metrics
   - $3$: Explicit user statement with operational context
   - $4$: Verified metric / percentage with timeline
   - $5$: Certified document extract (RAG citation with page/section)

---

## 3. Severity Thresholds

$$\text{Severity}(S) = \begin{cases} 
\text{CRITICAL} & \text{if } 4.2 \le S \le 5.0 \\
\text{HIGH} & \text{if } 3.4 \le S < 4.2 \\
\text{MEDIUM} & \text{if } 2.5 \le S < 3.4 \\
\text{LOW} & \text{if } 1.0 \le S < 2.5 
\end{cases}$$

---

## 4. Confidence Level Formula

$$\text{Confidence Score} = \max\left(0.10, \min\left(0.99, 0.50 + 0.12 \cdot |E| + 0.15 \cdot \mathbb{I}_{\text{source}} - 0.08 \cdot |M|\right)\right)$$

### Qualitative Mapping:
- **$\text{Confidence} \ge 0.80 \implies$ HIGH** (Strong document grounding, low missing data)
- **$0.55 \le \text{Confidence} < 0.80 \implies$ MEDIUM** (Sufficient grounding with some unknown variables)
- **$\text{Confidence} < 0.55 \implies$ LOW** (Sparse initial data, requires follow-up clarification)

---

## 5. Anti-Hallucination Triad

```text
┌─────────────────────────────────────────────────────────────┐
│ 1. Known Facts: Direct verifiable statements                │
│ 2. Unknown Aspects: Elements not provided in context        │
│ 3. Needed to Assess Accurately: Required follow-up data     │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Conflict & Contradiction Detection

Scans for temporal and numeric inconsistencies:
- Contradictory runway estimates (e.g. $12\text{ months}$ vs $3\text{ months}$).
- Conflicting revenue trajectories (growth claims vs decline claims).
- Disparate financial totals within the same session.
