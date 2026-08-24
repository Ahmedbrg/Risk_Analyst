# AI Risk Analyst — Technical Architecture Blueprint

## System Overview
The **AI Risk Analyst** is an enterprise AI decision-support platform designed for Team Leaders, Risk Managers, and Business Analysts to evaluate business situations, detect cross-vector risks, extract evidence, and automate PDF report delivery.

```
                         User
                           │
                 ┌─────────▼─────────┐
                 │   React / Next.js │
                 │  Chat + Workspace │
                 └─────────┬─────────┘
                           │
                           ▼
                      FastAPI API
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
          PostgreSQL      RAG        AI Agents
              │            │            │
              │         Qdrant       CrewAI
              │            │            │
              └────────────┼────────────┘
                           │
                           ▼
                     Risk Analysis
                           │
                  ┌────────┴────────┐
                  │                 │
                  ▼                 ▼
               Report            n8n
                                    │
                            ┌───────┴───────┐
                            ▼               ▼
                         PDF Report       Email
```

## Key Components

### 1. FastAPI REST Backend
- Async execution model built with Python 3.11+ and Pydantic v2.
- Implements `/chat` with sliding-window conversation memory.
- Exposes structured risk analysis (`/analyze`), document indexing (`/documents/upload`), vector context querying (`/documents/query`), PDF report compilation (`/reports/pdf`), and n8n webhook automation triggers (`/reports/n8n-trigger`).

### 2. Grounded Risk Engine & Product Principle
- Strictly distinguishes between **Known Facts** (explicit user input), **Inferences** (logical deductions), and **Missing Information**.
- Prevents unsupported or hallucinated claims of insolvency or breach.

### 3. Quantitative Risk Severity Methodology
- Multi-Factor composite score:
  $$S = (Impact \times 0.40) + (Urgency \times 0.30) + (Probability \times 0.20) + (Evidence \times 0.10)$$
- Severity mapped to `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
- Confidence calculated dynamically based on evidence count vs missing data ratio.

### 4. Vector DB & RAG Pipeline (Qdrant)
- Semantic chunking (500 chars / 100 overlap).
- Metadata-aware indexing storing `document_id`, `filename`, `page_number`, `chunk_id`, and `source_location`.

### 5. CrewAI 5-Agent System
- **Risk Analyst**: Taxonomy classification.
- **Evidence Analyst**: Forensic quote extraction.
- **Cross-Information Analyst**: Contradiction detection.
- **Recommendation Analyst**: Action planning.
- **Report Writer**: Final grounded synthesis.

### 6. n8n Automation Engine
- Webhook trigger handles email formatting and report attachment dispatch without cluttering core AI code.
