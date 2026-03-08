# 🏉 Fan360 — Agentic Fan Engagement Platform

> **Real-time, AI-powered fan engagement system built on Microsoft Fabric, Azure AI Foundry, AutoGen A2A, and Semantic Kernel.**

---

## What is Fan360?

Fan360 is a **multi-agent AI system** that detects fan behaviour signals in real time and automatically delivers personalised, context-aware engagement actions — retention offers, birthday messages, sponsor activations, and re-engagement campaigns — without any human intervention.

When a fan's churn score drops, they scan a gate, abandon a cart, or have a birthday, Fan360:
1. **Detects** the event via Fabric Activator or HTTP webhook
2. **Reads** the fan's Gold-layer profile via MCP (Model Context Protocol)
3. **Routes** to the correct specialist AI agent via AutoGen A2A
4. **Generates** a personalised offer in natural language
5. **Writes back** the action to `gold_fact_engagement` in Microsoft Fabric OneLake

---

## Architecture

```
Azure AI Foundry Agent Service
        │
        ├── Microsoft Agent Framework (Semantic Kernel + AutoGen)
        │       │
        │       ├── Orchestrator Agent (parent)
        │       │       └── Connected Agents via AutoGen A2A protocol
        │       │               ├── Churn Agent              (retention offers)
        │       │               ├── Personalisation Agent    (engagement offers)
        │       │               ├── Recommendation Agent     (re-activation)
        │       │               ├── Segmentation Agent       (fan classification)
        │       │               └── Sponsor Matching Agent   (commercial offers)
        │       │
        │       └── MCP (Model Context Protocol)
        │               └── Data API Builder → Gold Delta tables in OneLake
        │
        └── Fabric Activator → HTTP webhook → Orchestrator entry point
```

### Data Flow

```
Fabric Activator (event detected)
        ↓
POST /webhook → webhook_server.py
        ↓
Orchestrator reads Gold tables via SK plugins (MCP/DAB)
  ├── get_fan_profile()     → gold_dim_fan
  ├── get_fan_segment()     → gold_fan_segments
  ├── get_churn_score()     → gold_churn_score
  └── get_last_contact()    → gold_fact_engagement
        ↓
LLM routing decision → target_child_agent
        ↓
AutoGen A2A dispatch → child agent
  (receives only minimal context — never touches Gold tables)
        ↓
Child agent generates offer JSON
        ↓
Result returns to Orchestrator
        ↓
log_action() SK plugin → write-back → gold_fact_engagement (OneLake)
```

### Multi-Agent Chain (Birthday / Complex Events)

```
BirthdayEvent trigger
        ↓
SegmentationAgent  → "VIP Diehard" (HIGH confidence)
        ↓
RecommendationAgent → "20% jersey offer hook"
        ↓
PersonalisationAgent → "Happy Birthday! [personalised message]"
        ↓
write-back + email sent
```

---

## Project Structure

```
fan360Code/
│
├── README.md                          ← this file
│
├── fan360-mcp/                        ← MCP Server (Data API Builder)
│   ├── dab-config.json                ← DAB config exposing Gold tables
│   └── .env                           ← DB connection string
│
├── fan360-orchestrator/               ← Orchestrator Agent (parent)
│   ├── orchestrator.py                ← main orchestrator logic
│   ├── autogen_agents.py              ← AutoGen A2A dispatch layer
│   ├── sk_plugins.py                  ← Semantic Kernel plugin wrappers
│   ├── webhook_server.py              ← FastAPI HTTP webhook + SSE stream
│   ├── birthday_scheduler.py          ← daily birthday trigger cron script
│   ├── test_orchestrator.py           ← E2E test (multi-fan scenarios)
│   ├── test_chain.py                  ← multi-agent chain test
│   ├── test_sk_plugins.py             ← SK plugin unit tests
│   ├── update_agent_instructions.py   ← push updated prompts to Foundry
│   ├── agent_actions_log.jsonl        ← local write-back log (fallback)
│   ├── .env                           ← all secrets (see env setup below)
│   └── venv/                          ← shared Python virtualenv
│
├── churn-agent/                       ← Churn Agent (child)
│   ├── churn_agent.py                 ← agent logic + INSTRUCTIONS
│   ├── create_churn_agent.py          ← one-time Azure AI agent creation
│   ├── test_churn_agent.py            ← isolation test
│   └── .env                           ← AZURE_AI_AGENT_ID
│
├── personalisation-agent/             ← Personalisation Agent (child)
│   ├── personalisation_agent.py
│   ├── create_personalisation_agent.py
│   ├── test_personalisation_agent.py
│   └── .env                           ← AZURE_AI_PERSONALISATION_AGENT_ID
│
├── recommendation-agent/              ← Recommendation Agent (child)
│   ├── recommendation_agent.py
│   ├── create_recommendation_agent.py
│   ├── test_recommendation_agent.py
│   └── .env
│
├── segmentation-agent/                ← Segmentation Agent (child)
│   ├── segmentation_agent.py
│   ├── create_segmentation_agent.py
│   ├── test_segmentation_agent.py
│   └── .env
│
├── sponsor-matching-agent/            ← Sponsor Matching Agent (child)
│   ├── sponsor_matching_agent.py
│   ├── create_sponsor_matching_agent.py
│   ├── test_sponsor_matching_agent.py
│   └── .env
│
├── fan360-control-room/               ← React Control Room UI
│   ├── src/
│   │   ├── App.js                     ← full UI (robotic dark theme)
│   │   └── index.css
│   └── package.json
│
└── sponsor-roi-dashboard/             ← React Sponsor ROI Dashboard
    ├── src/
    │   ├── App.js                     ← sponsor ROI charts
    │   └── index.css
    └── package.json
```

---

## Gold Tables (Microsoft Fabric OneLake)

| Table | Purpose |
|---|---|
| `gold_dim_fan` | Fan profile — preferences, opt-ins, segment, favourite player/team |
| `gold_fan_segments` | KMeans cluster labels — VIP Diehard, Casual Fan, At Risk etc. |
| `gold_churn_score` | Daily churn risk score (0–1) per season ticket holder |
| `gold_fact_engagement` | Every interaction ever — reads + agent write-backs |
| `gold_sponsor_audiences` | GDPR-safe aggregated segments handed to sponsors |

---

## Agent Registry

| Agent | Azure AI ID | Trigger Condition |
|---|---|---|
| Orchestrator | `asst_orchestrator...` | All events — parent router |
| ChurnAgent | `asst_utXk0Otf...` | churn_score > 0.75 or null |
| PersonalisationAgent | `asst_Z9pULIVM...` | churn ≤ 0.75, active fan |
| RecommendationAgent | `asst_hMdrNnfV...` | inactive / lapsed fan |
| SegmentationAgent | `asst_uVIxbrr4...` | segment unknown/null |
| SponsorMatchingAgent | `asst_vpzPeUmJ...` | VIP/Loyal + sponsor signal |

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- Azure CLI (`brew install azure-cli`)
- Microsoft Fabric workspace with Gold Delta tables
- Azure AI Foundry project
- ngrok (optional, for Fabric Activator webhook)

---

## 🚀 How to Run

### 1 — Clone & Setup

```bash
git clone https://github.com/<your-username>/fan360.git
cd fan360/fan360Code
```

### 2 — Python Environment

```bash
cd fan360-orchestrator
python3 -m venv venv
source venv/bin/activate
pip install azure-ai-projects azure-identity semantic-kernel \
            pyautogen fastapi uvicorn python-dotenv requests
```

### 3 — Environment Variables

Create `fan360-orchestrator/.env`:

```bash
# Azure AI Foundry
AZURE_AI_FOUNDRY_ENDPOINT=https://<your-project>.openai.azure.com/
AZURE_AI_FOUNDRY_API_KEY=<your-api-key>
AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME=gpt-4o

# Orchestrator Agent ID
AZURE_AI_AGENT_ID=asst_<orchestrator-id>

# Child Agent IDs
AZURE_AI_AGENT_ID=asst_utXk0Otf...
AZURE_AI_PERSONALISATION_AGENT_ID=asst_Z9pULIVM...
AZURE_AI_RECOMMENDATION_AGENT_ID=asst_hMdrNnfV...
AZURE_AI_SEGMENTATION_AGENT_ID=asst_uVIxbrr4...
AZURE_AI_SPONSOR_MATCHING_AGENT_ID=asst_vpzPeUmJ...

# Microsoft Fabric
FABRIC_BEARER_TOKEN=<az account get-access-token output>
FABRIC_WORKSPACE_ID=c5ce5ad3-a854-4249-b980-f4da942c3871
FABRIC_LAKEHOUSE_ID=80da8dc3-294e-406e-b545-bdcd1a9bd348

# DAB (MCP Server)
DAB_BASE_URL=http://localhost:5000

# Email (optional — birthday flow)
GMAIL_SENDER=<your-gmail>
GMAIL_APP_PASSWORD=<16-char app password>
```

### 4 — Start MCP Server (Data API Builder)

```bash
cd fan360-mcp
dab start
# → Gold tables available at http://localhost:5000
```

### 5 — Start Webhook Server (Orchestrator entry point)

```bash
cd fan360-orchestrator
source venv/bin/activate
python webhook_server.py
# → Running on http://localhost:8000
```

### 6 — Start Control Room UI

```bash
cd fan360-control-room
npm install
npm start
# → http://localhost:3000
```

### 7 — Start Sponsor ROI Dashboard

```bash
cd sponsor-roi-dashboard
npm install
npm start -- --port 3001
# → http://localhost:3001
```

### 8 — Test End-to-End

```bash
# Churn event
curl -X POST http://localhost:8000/webhook/test \
     -H "Content-Type: application/json" \
     -d '{"fan_id": "FAN-d65867e0", "event_type": "ChurnDrop"}'

# Birthday event (multi-agent chain)
curl -X POST http://localhost:8000/webhook/test \
     -H "Content-Type: application/json" \
     -d '{"fan_id": "FAN-d65867e0", "event_type": "BirthdayEvent"}'

# Full 5-scenario test
cd fan360-orchestrator
python test_orchestrator.py
```

---

## 🔁 Refresh Fabric Bearer Token (expires ~1hr)

```bash
az account get-access-token \
  --resource https://api.fabric.microsoft.com \
  --query accessToken -o tsv
# → paste into .env FABRIC_BEARER_TOKEN
```

---

## 🧪 Individual Agent Tests

```bash
source fan360-orchestrator/venv/bin/activate

python churn-agent/test_churn_agent.py
python personalisation-agent/test_personalisation_agent.py
python recommendation-agent/test_recommendation_agent.py
python segmentation-agent/test_segmentation_agent.py
python sponsor-matching-agent/test_sponsor_matching_agent.py
python fan360-orchestrator/test_sk_plugins.py
python fan360-orchestrator/test_chain.py
```

---

## 🌐 Expose Webhook for Fabric Activator (ngrok)

```bash
brew install ngrok
ngrok http 8000
# Copy https://xxxx.ngrok.io → paste into Fabric Activator webhook URL
```

---

## 📐 Key Design Principles

| Principle | Implementation |
|---|---|
| **Child agents never read Gold tables** | Only Orchestrator has MCP access |
| **Child agents never write back** | Only Orchestrator calls `log_action()` |
| **Minimal context per child** | Orchestrator slices only what each agent needs |
| **Child agents are stateless** | One fan, one decision, return JSON, done |
| **No duplicate actions** | `get_last_contact()` checked before every dispatch |
| **GDPR compliant** | Sponsors receive aggregated segments only, never raw fan PII |

---

## 🏆 Tech Stack

| Layer | Technology |
|---|---|
| AI Agent Framework | Azure AI Foundry Agent Service |
| Agent Orchestration | Semantic Kernel (SK) |
| Agent Communication | AutoGen A2A protocol |
| Tool/Data Access | MCP (Model Context Protocol) via Data API Builder |
| Data Platform | Microsoft Fabric (OneLake, Delta tables, Activator) |
| LLM | GPT-4o via Azure OpenAI |
| Write-back | Fabric Lakehouse REST API |
| Webhook Server | FastAPI + Uvicorn |
| Control Room UI | React + Recharts + SSE |
| Email Delivery | Gmail SMTP (dev) / Azure Logic Apps (prod) |

---

## 👤 Author

MSc Artificial Intelligence — National College of Ireland

---
