# SymSafe AI Architecture

## File Structure

```
symsafe-ai/
├── symsafe/                          Application package
│   ├── __init__.py
│   ├── main.py                      CLI entrypoint and conversation loop
│   ├── agent.py                     Claude Sonnet structured JSON responses
│   ├── evaluator.py                 AI self-evaluation via Claude Haiku
│   ├── ai_analyzer.py              Session analysis engine for clinician review
│   ├── risk_classifier.py          Local keyword risk classifier + combination rules
│   ├── symptom_tree.py             Symptom-to-guidance JSON matcher
│   ├── care_router.py              5-tier care routing and risk-care merging
│   ├── intake.py                   Guided intake questionnaire (7 steps)
│   ├── logger.py                   Markdown session logging
│   ├── report.py                   HTML Patient Preparation Document generator
│   ├── config.py                   Configuration, API client, prompt loading
│   ├── store.py                    SQLite persistence layer
│   ├── feedback.py                 Gap detection, synonym/rule proposals
│   └── web/
│       ├── __init__.py
│       ├── app.py                  Flask app — patient UI + clinician dashboard
│       └── templates/
│           ├── index.html          Patient-facing single-page application
│           ├── review.html         Clinician 3-panel workstation
│           └── review_login.html   Clinician authentication
├── scripts/
│   ├── __init__.py
│   └── seed_demo_data.py           Demo data seeder for clinician dashboard
├── prompts/
│   ├── base_prompt.txt             Claude system prompt
│   └── symptom_tree.json           Symptom-to-guidance mapping
├── tests/                           22 test files, 305 tests
├── evaluations/
│   └── eval_template.md            Manual evaluation template
├── notes/
│   └── product_notes.md            Product development notes
├── data/                            SQLite database (gitignored)
├── logs/                            Session markdown logs (gitignored)
├── reports/                         Patient HTML reports (gitignored)
├── docs/
│   └── ARCHITECTURE.md             This file
├── run_web.py                       Flask dev server entrypoint
├── render.yaml                      Render deployment config
├── requirements.txt                 Python dependencies
├── .env.example                     Environment variable template
└── .gitignore
```

## Key Modules

**app.py** is the Flask web application with 24 routes covering patient intake, chat, session management, clinician authentication, session review, exchange review, synonym and rule proposal management, AI analysis, bulk synonym generation, response rewriting, classifier management, and impact analysis. It handles input sanitization, rate limiting, security headers, and the auto-seeding of demo data on first startup.

**agent.py** handles the primary Claude Sonnet API call for patient chat. It separates system messages from user/assistant messages per the Anthropic API format, appends a JSON instruction requiring structured output (response, risk_level, risk_flags, follow_up_questions, provider_questions, care_level), and includes fallback parsing for code-fenced or malformed responses.

**evaluator.py** runs a secondary Claude Haiku call on clinically relevant messages to evaluate the assistant's response against a safety checklist (safe, empathetic, avoided diagnosis, escalation offered, clear language). Results are logged for clinician review but never shown to patients.

**ai_analyzer.py** provides the AI analysis engine for the clinician review workstation. The analyze_session function makes one Claude Haiku call with the full session context and returns structured JSON with clinical summary, risk assessment, per-exchange quality scores, differential considerations, synonym suggestions with reasoning, response templates, intake observations, review priority, and pattern notes. Results are cached in SQLite.

**risk_classifier.py** provides instant, deterministic risk classification using curated keyword lists. HIGH_RISK_FLAGS covers cardiac, neurological, respiratory, vision, mental health, trauma, and allergic emergencies. MODERATE_RISK_FLAGS covers conditions needing medical attention but not immediately life-threatening. COMBINATION_RULES escalate risk when multiple symptoms appear together (e.g., headache + vision changes). Clinician-approved synonyms and rules are applied at runtime.

**store.py** manages the SQLite database with five tables: sessions, exchanges, synonym_proposals, rule_proposals, and session_analyses. Provides functions for creating, reading, and updating all records, plus aggregate queries for session stats, impact analysis, and bulk retrieval of proposals and analyses.

**care_router.py** maps the merged risk level and Claude's care recommendation to a final care level using a safety-first merge: HIGH risk forces at least urgent_care, emergency is never downgraded. Each care level has structured guidance (where to go, why, what to do right now).

**feedback.py** compares local vs Claude risk classifications to detect gaps — cases where Claude catches a risk the local classifier misses. When a gap is found, it generates a synonym proposal with the patient's exact phrasing. It also detects combination patterns across clinician-corrected exchanges and proposes new combination rules. The apply_approved_synonyms function writes approved phrases directly into risk_classifier.py on disk.

**report.py** generates standalone HTML Patient Preparation Documents with intake data, symptom timeline, risk assessment, conversation summary, provider questions with answer lines for handwriting, care guidance, and a medical disclaimer. Print-friendly CSS included.

**intake.py** defines the 7-step intake questionnaire (concern, location, onset, severity, trajectory, medications, conditions) with structured options for each step. The format_intake_context function converts answers into a system prompt injection for Claude.

**config.py** resolves the project root directory, loads .env, initializes the Anthropic client, and provides the load_base_prompt function.

**main.py** is the CLI entrypoint that orchestrates the full triage session: argument parsing, intake, conversation loop, dual-layer risk assessment, care routing, escalation tracking, evaluation, logging, and report generation.

**logger.py** writes timestamped markdown log files with exchange details, risk levels, flags, evaluations, and session summaries.

**symptom_tree.py** loads and matches patient input against a curated JSON mapping of symptoms to clinical guidance. Matches are injected as system context for Claude.

**seed_demo_data.py** populates the database with 5 realistic patient sessions (chest pain emergency, headache with vision changes, stomach upset, cold with asthma, mental health crisis), 8 exchanges, 5 synonym proposals, 2 rule proposals, and 5 pre-computed AI analyses. Idempotent with a --clear flag. Auto-runs on first app startup if the database is empty.

## Data Flow

A patient message flows through the system in this order. First, the patient completes an optional intake form and their answers are injected as system context for Claude. When the patient sends a chat message, the local keyword classifier scans it against HIGH_RISK_FLAGS and MODERATE_RISK_FLAGS, then checks COMBINATION_RULES for multi-symptom patterns. Simultaneously, the symptom tree matches known symptoms and injects clinical guidance as a system hint.

The message (with intake context and symptom hints) is sent to Claude Sonnet, which returns structured JSON with a conversational reply, risk level, risk flags, follow-up questions, provider questions, and a care level recommendation. The system merges the local and Claude risk levels — always taking the higher — and maps the result to a final care level using care_router's safety-first logic.

The patient sees the reply with a proportionate banner (decoupled from the internal risk level to avoid alarming patients unnecessarily) and care guidance with Google Maps links if a zip code was provided. The exchange is immediately saved to SQLite with all classification data. The session record is updated with current message count, highest risk, and symptoms after every exchange.

On clinically relevant messages, a secondary Claude Haiku call evaluates the response quality. If the local classifier missed a risk that Claude caught, a synonym proposal is generated. When the session ends, the session summary is logged, a Patient Preparation Document is generated, and the session is marked ready for clinician review.

When a clinician opens a session in the Review Queue, an analysis request is made to Claude Haiku (cached after first call). The analysis populates the clinical summary, risk assessment, per-exchange quality scores, and synonym suggestions in the 3-panel interface. Clinician actions (approve synonym, correct risk, accept exchange) feed back into the classifier and the database, improving future sessions.

## API Routes

### Patient-Facing

| Route | Method | Description |
|---|---|---|
| `/` | GET | Patient chat interface (index.html) |
| `/api/intake` | POST | Submit intake questionnaire answers |
| `/api/chat` | POST | Send a chat message, receive AI response |
| `/api/end-session` | POST | End session, generate report |
| `/reports/<filename>` | GET | Serve generated patient reports |

### Clinician Authentication

| Route | Method | Description |
|---|---|---|
| `/review/login` | GET/POST | Clinician login form |
| `/review/logout` | GET | Log out of clinician dashboard |

### Clinician Dashboard

| Route | Method | Description |
|---|---|---|
| `/review` | GET | Main clinician workstation (3-tab interface) |

### Clinician API — Session Review

| Route | Method | Description |
|---|---|---|
| `/api/review/session-data/<session_id>` | GET | Full session JSON for center panel |
| `/api/review/exchange/<exchange_id>` | POST | Update exchange review status |
| `/api/review/session/<session_id>` | POST | Update session status and notes |
| `/api/review/save-correction` | POST | Save clinician's corrected response |
| `/api/review/rewrite` | POST | Generate AI-suggested response rewrite |

### Clinician API — AI Analysis

| Route | Method | Description |
|---|---|---|
| `/api/review/analyze/<session_id>` | GET | Get/generate AI session analysis (cached) |
| `/api/review/bulk-synonyms` | POST | Generate bulk synonym suggestions |
| `/api/review/impact/<phrase>` | GET | Count past exchanges containing a phrase |

### Clinician API — Classifier Management

| Route | Method | Description |
|---|---|---|
| `/api/review/classifier-data` | GET | Current flag lists and combination rules |
| `/api/review/add-synonym` | POST | Directly add a synonym to the classifier |
| `/api/review/add-rule` | POST | Directly add a combination rule |
| `/api/review/remove-flag` | POST | Remove a flag from in-memory lists |
| `/api/review/remove-rule` | POST | Remove a combination rule by index |

### Clinician API — Proposals

| Route | Method | Description |
|---|---|---|
| `/api/review/proposals` | GET | All pending synonym and rule proposals |
| `/api/review/synonym/<proposal_id>` | POST | Approve or reject a synonym proposal |
| `/api/review/rule/<proposal_id>` | POST | Approve or reject a rule proposal |
