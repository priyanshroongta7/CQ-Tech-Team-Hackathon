# CQ Tech Team AI Agent — Autonomous Lead Sourcing & Verification Agent

An end-to-end autonomous AI agent built with **LangGraph** and **CrewAI** that turns an event brochure (PDF) or search prompt into verified, structured decision-maker leads saved directly into Google Sheets.

Designed to eliminate manual sponsor and college delegation digging, avoid hallucinated data, and navigate dead links autonomously.

---

## 🌟 Key Features

1. **Dual Input Support**: Accepts an uploaded event brochure (`.pdf`) or direct text search prompts (e.g., *"Find sponsors and college delegations for an AI Hackathon in Bangalore"*).
2. **Sponsor & College Delegation Sourcing**: Identifies corporate sponsors (marketing leads, CSR heads) and campus delegations (society presidents, convenors).
3. **Autonomous Deep Digging (CrewAI)**: Scours company websites, team pages, LinkedIn, social accounts, college portals, and press coverage with automatic retry on dead links.
4. **Anti-Hallucination & Verification Node**: Multi-tier email discovery and deliverability verification (Hunter.io / ZeroBounce / Authentic Profile URLs). Contacts failing verification are dropped.
5. **LangGraph StateGraph Orchestration**: Robust state machine with conditional routing, queue tracking, and rate-limit management.
6. **Strict 6-Field Google Sheets Schema**: Automatically initializes and appends clean rows adhering to the mandated schema.

---

## 📊 Mandatory 6-Field Schema

| Field | Description / Value |
|---|---|
| **Organization Name** | Company or college society name |
| **Category** | `Sponsor` or `College Delegation` |
| **Location** | City (e.g., `Pune`, `Bangalore`, `Mumbai`) |
| **Contact Person** | Name and exact role of the decision-maker (e.g., `Jane Doe - Marketing Lead`) |
| **Contact Channel** | Deliverable email address or authentic profile link |
| **Verification Status** | `Verified` or `Pattern-Derived` |

---

## 🏗️ Architecture

```
[Input: PDF or Search Prompt]
         │
         ▼
[LangGraph Node: parse_input] ──(Extracts Sponsors & College Delegations)
         │
         ▼
[LangGraph Node: research_lead] ◄──► [CrewAI Tool Agents (SerperDev & Web Scraper)]
         │                            (Company Sites, Team Pages, LinkedIn)
         ▼
[Conditional Edge: Contact Found?] ──(Not Found)──► [advance_queue]
         │ (Found)
         ▼
[LangGraph Node: verify_lead] ──(ZeroBounce Deliverability & Pattern Derivation)
         │
         ▼
[Conditional Edge: Verification Passed?] ──(Failed)──► [advance_queue] (Drops Fake Data)
         │ (Valid)
         ▼
[LangGraph Node: push_to_sheets] ──(Appends 6-Field Row via Google Sheets API)
         │
         ▼
[LangGraph Node: advance_queue] ──(More items?)──► [research_lead] OR [END]
```

---

## 🚀 Quick Setup Guide

### 1. Clone & Set Up Virtual Environment

```bash
cd ai_event_agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure API Keys

Set your API keys as environment variables or in the respective scripts:

```bash
export OPENAI_API_KEY="sk-..."          # Required (OpenAI gpt-4o-mini)
export SERPER_API_KEY="ea..."           # Required (Serper.dev Google Search)
export ZEROBOUNCE_API_KEY="e6..."       # Optional (ZeroBounce deliverability)
export HUNTER_API_KEY="your-key"        # Optional (Hunter.io email discovery)
```

### 3. Google Sheets Authentication

1. Place your Google Cloud Service Account JSON key as `credentials.json` in the root folder.
2. In `main_pipeline.py` and `phase4_output.py`, set:
   ```python
   GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit"
   ```
3. Share your Google Sheet with the `client_email` found in `credentials.json` with **Editor** access.

---

## 🧪 Testing & Execution

### Option A: Run with a PDF Brochure
```bash
python main_pipeline.py brochure.pdf
```

### Option B: Run with a Search Prompt
```bash
python main_pipeline.py "Find sponsors and college delegations for an AI and Cloud Hackathon in Bangalore"
```

### Option C: Isolated Phase Testing
```bash
python phase1_context.py "AI Hackathon Bangalore"   # Tests Context Generation
python phase2_orchestration.py                      # Tests CrewAI Autonomous Search
python phase3_verification.py                       # Tests Deliverability Verification
python phase4_output.py                             # Tests Google Sheets Schema & Push
```

---

## 📁 Project Structure

```
ai_event_agent/
├── brochure.pdf                  # Sample event brochure input
├── credentials.json              # Google Sheets service account key
├── phase1_context.py             # Phase 1: PDF/prompt parser & context generator
├── phase2_orchestration.py       # Phase 2: CrewAI autonomous web research agent
├── phase3_verification.py        # Phase 3: Deliverability verification & anti-hallucination
├── phase4_output.py              # Phase 4: Pydantic 6-field validation & Google Sheets push
├── main_pipeline.py              # Master LangGraph StateGraph orchestrator
├── requirements.txt              # Project dependencies
└── README.md                     # Documentation & setup guide
```
