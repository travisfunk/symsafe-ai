# SymSafe AI

AI-powered triage assistant with a patient-facing web UI, clinician review dashboard, and a self-improving risk classifier that learns from clinician feedback.

## What It Does

SymSafe provides two interfaces to the same backend: a web UI for patients and a review dashboard for clinicians. Patients complete an optional intake form, then chat about their symptoms in a browser-based conversational interface. Behind the scenes, a dual-layer risk classifier (local keyword matching + GPT-4o) assesses urgency, routes patients to the appropriate level of care with Google Maps links to nearby facilities, and generates a printable Patient Preparation Document. Every session is persisted to a SQLite database where clinicians can review AI decisions, correct risk assessments, and approve new classifier rules — creating a feedback loop that makes the system more accurate over time. The original CLI is also fully functional. This is a portfolio prototype — it is not intended for real clinical use.

## Key Features

**Web-Based Patient Interface**
A Flask-powered single-page application with guided intake (chip-style selectable options, severity slider, optional zip code), real-time chat with safety banners, care guidance boxes with Google Maps links, typing indicators, and a session summary with downloadable HTML report.

**Clinician Review Dashboard**
Password-protected interface at /review where clinicians see a session queue sorted by risk level (HIGH first), click into any session to review each exchange, and accept, correct, or reject AI decisions. Supports clinical notes, session flagging, and bulk review workflows.

**Dual-Layer Risk Classification**
A local keyword classifier acts as a fast, deterministic safety net that catches high-risk phrases like "chest pain" or "suicidal" instantly. GPT-4o provides a second, contextual risk assessment. The system always takes the higher of the two — because in triage, false negatives are far more dangerous than false positives.

**Combination Rule Detection**
When clinicians correct the same multi-symptom pattern three or more times (e.g., "headache + vision changes" escalated to HIGH), the system automatically proposes a new combination rule. Seeded with six clinical combinations including chest pain + jaw pain and numbness + difficulty speaking.

**Synonym Proposal System**
When GPT catches a risk the local classifier misses, the system generates a synonym proposal (e.g., "add 'chest is burning' as synonym for 'chest pain'"). Clinicians approve or reject proposals from the review dashboard. Approved synonyms are written directly into the classifier source file.

**Self-Improving Risk Classifier**
Approved synonyms and combination rules are applied automatically — synonyms are written into risk_classifier.py on disk, combination rules are loaded from the database at startup. Each session makes the local classifier more comprehensive.

**5-Tier Care Routing with Location Awareness**
Patients are routed to a specific level of care: emergency (call 911), urgent care (walk-in clinic today), primary care (schedule this week), telehealth (virtual visit), or self-care (monitor at home). When a zip code is provided, care guidance includes a Google Maps link to nearby facilities.

**SQLite Session Persistence**
Every session, exchange, synonym proposal, and rule proposal is stored in a structured SQLite database. This enables clinician review, pattern detection across sessions, and data export for analysis.

**Guided Intake Questionnaire**
Seven structured questions — concern, location, onset, severity, trajectory, medications, and conditions — with chip-style selectable options in the web UI or step-by-step prompts in the CLI. Everything is optional. Answers are injected as system context for GPT.

**Structured GPT-4o Output**
GPT-4o returns structured JSON with a conversational reply, risk level, risk flags, follow-up questions, and a care level recommendation. This makes every response programmatically actionable.

**Repeat Escalation Detection**
If a patient is told to seek emergency care but continues chatting for three more messages without doing so, the system re-escalates with a direct reminder.

**Patient Preparation Document**
At session end, SymSafe generates a standalone HTML report the patient can print and bring to their doctor. It includes intake data, a symptom timeline, risk assessment, conversation summary, follow-up questions for the provider, and care guidance.

**Symptom Tree Matching**
A curated JSON mapping of common symptoms to vetted static responses anchors GPT's output. When a patient mentions "chest pain," the system injects the pre-written clinical reference so GPT's reply stays grounded.

**AI Self-Evaluation**
On clinically relevant messages, a secondary GPT-4o-mini call evaluates the assistant's response against a safety checklist. This evaluation is logged for practitioner review but never shown to the patient.

**Security Hardening**
Input sanitization on all routes, HTML tag stripping, XSS protection, rate limiting (30 messages per session), session cookie security, clinician authentication, security headers (X-Frame-Options, CSP, etc.), and API key protection.

**Full Session Logging**
Every interaction is logged to both a timestamped markdown file and the SQLite database: user input, risk level, care routing, symptom tree matches, assistant response, follow-up questions, and evaluation results.

## Example Session

### Web UI Flow

A patient visits the SymSafe web interface and clicks "Guided assessment." They select "Pain" for concern, "Chest" for location, "Today" for onset, drag the severity slider to 7, select "Worse" for trajectory, type "aspirin" for medications, and select "Heart disease" for conditions. They enter their zip code "46038" and click "Start conversation."

In the chat, they type "I've had chest pain since last night and I'm feeling short of breath." A red safety banner appears: "Based on what you've described, please seek immediate medical attention or call 911." Below the AI's response, a care guidance box shows "Where to go: Emergency room" with a clickable link to "Find emergency room near you" that opens Google Maps searching for emergency rooms near 46038.

When they click "End session," they see a summary card with a red HIGH risk badge, 1 message exchanged, "emergency" care level, and symptom tags for "chest pain" and "shortness of breath." They can view or download the HTML report.

### CLI Flow

```bash
python -m symsafe.main --intake
```

The same patient answers the same seven questions at the command line, then types their symptoms. They see the same risk assessment, care routing, and session summary, with a saved HTML report and markdown log.

### Clinician Review Flow

A clinician navigates to /review, logs in, and sees the session in the "High risk — review first" section. They click into it, review the exchange, click "Accept" to confirm the AI's classification, add a note "Appropriate escalation for cardiac symptoms with history," and click "Mark as reviewed."

## Architecture

```
symsafe/
├── main.py              — CLI entrypoint, argument parsing, main conversation loop
├── agent.py             — GPT-4o API calls with structured JSON response parsing
├── evaluator.py         — AI self-evaluation of responses via GPT-4o-mini
├── risk_classifier.py   — Local keyword risk classification with combination rules
├── symptom_tree.py      — Symptom-to-guidance JSON matching
├── care_router.py       — 5-tier care routing and risk-care level merging
├── intake.py            — Guided intake questionnaire (7 steps)
├── logger.py            — Markdown session logging and intake/summary logging
├── report.py            — HTML Patient Preparation Document generation
├── config.py            — Base directory resolution, API client init, prompt loading
├── store.py             — SQLite data persistence (sessions, exchanges, proposals)
├── feedback.py          — Gap detection, synonym proposals, combination pattern detection
└── web/
    ├── app.py           — Flask application (patient UI + clinician dashboard)
    └── templates/
        ├── index.html          — Patient-facing single-page UI
        ├── review.html         — Clinician session queue dashboard
        ├── review_session.html — Session detail with feedback controls
        └── review_login.html   — Clinician authentication
```

## Quick Start

### Web UI (recommended)

```bash
git clone https://github.com/your-username/symsafe-ai.git
cd symsafe-ai
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your OpenAI API key
python run_web.py
```

Open http://localhost:5000 for the patient UI and http://localhost:5000/review for the clinician dashboard (default password: `symsafe-review`).

### CLI

```bash
python -m symsafe.main
```

**CLI flags:**
- `--intake` — Start with the guided intake questionnaire
- `--learn` — Enable learning mode with developer coaching notes

```bash
python -m symsafe.main --intake --learn
```

### Deploy to Render

```bash
# Set these environment variables in the Render dashboard:
# OPENAI_API_KEY=sk-...
# FLASK_SECRET_KEY=<generate-a-random-string>
# REVIEW_PASSWORD=<choose-a-secure-password>
```

See `render.yaml` for the deployment configuration. The free tier works for demonstration purposes.

## How It Works

1. **Intake** (optional): Patient answers 7 structured questions. Answers are injected as system context.
2. **User input**: Patient describes symptoms in natural language (web chat or CLI).
3. **Local risk check**: Keyword classifier scans for high-risk and moderate-risk phrases. Combination rules check for multi-symptom patterns.
4. **Symptom tree match**: Known symptoms are matched against curated static guidance.
5. **GPT structured output**: GPT-4o returns JSON with a reply, risk level, flags, follow-ups, and care level.
6. **Risk merging**: The system takes the higher of the local and GPT risk assessments.
7. **Care routing**: Care level is merged with risk level — HIGH risk forces at least urgent care, emergency is never downgraded. Google Maps link generated if zip code provided.
8. **Response display**: Patient sees the reply with appropriate safety banners and care guidance.
9. **Evaluation** (clinical messages only): GPT-4o-mini evaluates the response against safety criteria. Logged but not shown to patient.
10. **Persistence**: Exchange is saved to SQLite. Classifier gaps are detected and synonym proposals generated.
11. **Escalation tracking**: If patient keeps chatting after an emergency recommendation, the system re-escalates after 3 messages.
12. **Session end**: Summary displayed, markdown log completed, HTML report saved, session persisted to database.
13. **Clinician review**: Clinician reviews session, accepts/corrects/rejects exchanges, approves synonym and rule proposals.
14. **Classifier improvement**: Approved synonyms are written into risk_classifier.py. Approved combination rules are loaded at next startup.

## Testing

```bash
pytest tests/ -v
```

The test suite includes 248 tests across 20 test files covering all modules. All tests run without a valid OpenAI API key — API calls are mocked. Coverage spans risk classification, combination rules, symptom tree matching, care routing, structured output parsing, session summary, intake questionnaire, HTML report generation, evaluator behavior, SQLite persistence, gap detection, synonym proposals, pattern detection, Flask routes (patient and clinician), input sanitization, authentication, rate limiting, security headers, and integration checks.

## Project Structure

```
symsafe-ai/
├── symsafe/                       — Main application package
│   ├── __init__.py
│   ├── main.py                   — CLI entrypoint and conversation loop
│   ├── agent.py                  — GPT-4o structured response handler
│   ├── evaluator.py              — AI self-evaluation via GPT-4o-mini
│   ├── risk_classifier.py        — Local keyword risk classifier + combination rules
│   ├── symptom_tree.py           — Symptom JSON matcher
│   ├── care_router.py            — Care level routing and merging
│   ├── intake.py                 — Guided intake questionnaire
│   ├── logger.py                 — Markdown session logger
│   ├── report.py                 — HTML report generator
│   ├── config.py                 — Configuration and API client
│   ├── store.py                  — SQLite data persistence layer
│   ├── feedback.py               — Gap detection and proposal generation
│   └── web/                      — Flask web application
│       ├── __init__.py
│       ├── app.py                — Routes, session management, security
│       └── templates/            — Jinja2 HTML templates
├── prompts/                       — Prompt templates and clinical data
│   ├── base_prompt.txt           — GPT system prompt
│   └── symptom_tree.json         — Symptom-to-guidance mapping
├── tests/                         — Test suite (248 tests, all mocked)
├── data/                          — SQLite database (gitignored)
├── evaluations/                   — Manual evaluation templates
├── notes/                         — Product development notes
├── logs/                          — Session logs (gitignored)
├── reports/                       — Patient reports (gitignored)
├── run_web.py                     — Flask development server entrypoint
├── render.yaml                    — Render deployment configuration
├── .env                           — API key and secrets (gitignored)
├── .env.example                   — Environment variable template
├── .gitignore
├── requirements.txt
└── README.md
```

## Project Status

**Current version: v3.0.0**

v3.0.0 delivers the complete system: patient-facing web UI, clinician review dashboard with feedback controls, self-improving risk classifier with synonym and combination rule proposals, SQLite persistence, location-aware care routing, security hardening, and deployment configuration.

Potential future enhancements:
- Multilingual support for non-English-speaking patients
- FHIR integration for EHR interoperability
- Analytics dashboard for aggregate triage pattern analysis
- Multi-clinician support with role-based access control

## Disclaimer

SymSafe is a prototype for demonstration and portfolio purposes only. It is NOT intended for real patient use, real clinical decision-making, or deployment in any healthcare setting. Always consult a qualified healthcare provider for medical advice.

## Contact

Built by Travis — [LinkedIn](https://www.linkedin.com/in/travisj-ai)
