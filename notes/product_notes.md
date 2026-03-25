# SymSafe AI — Product Development Notes

## Vision

SymSafe demonstrates that healthcare AI can be built responsibly without sacrificing usability. The project shows how to combine the conversational flexibility of large language models with deterministic safety guardrails, structured clinical output, a self-improving feedback loop, and a web-based patient interface — all in a system that puts the patient's experience first while giving clinicians the tools to review and improve AI decisions over time.

This is not a product; it is a proof of concept for the design patterns and engineering decisions that responsible healthcare AI requires.

## Design Principles

1. **Safety over helpfulness.** When there is a conflict between being helpful and being safe, safety wins. A false alarm is always preferable to a missed emergency. This is why the dual-layer risk classifier takes the higher of two assessments, and why emergency care levels are never downgraded.

2. **Deterministic safety with generative empathy.** Risk classification and care routing use local, deterministic logic that does not depend on an LLM behaving correctly. The LLM handles the part it is good at — empathetic, conversational replies — while hard safety decisions are anchored by keyword matching, combination rules, and rule-based merging.

3. **Auditable by default.** Every interaction is logged to both a timestamped markdown file and a SQLite database with full detail. There is no mode where the system operates without a paper trail. Clinicians can review every exchange after the fact.

4. **Patient-first language.** The system uses plain language at an 8th-grade reading level. It never shows internal QA data (evaluations) to the patient. Risk badges and clinical terminology appear in logs, the database, and the clinician dashboard, not in the patient-facing interface.

5. **Clinician-ready output.** The Patient Preparation Document is designed for a real clinical workflow. The clinician review dashboard is designed for efficient queue-based review. The system produces structured data a clinician can actually use.

6. **Continuous improvement.** The system does not just capture feedback — it acts on it. Approved synonyms are written into the classifier source. Approved combination rules are loaded at startup. Each clinician review makes the next session more accurate.

## Key Decisions

### Why dual-layer risk classification?

LLMs are unreliable safety classifiers — they can be swayed by phrasing, context, or instruction-following failures. A local keyword check catches "chest pain" and "suicidal" instantly and deterministically, regardless of what GPT decides. The two layers are complementary: local catches known red flags fast, GPT catches nuanced clinical judgment that keywords miss.

### Why combination rules?

Individual symptom keywords can underweight multi-symptom presentations. "Headache" alone is low risk. "Headache with vision changes" can indicate a neurological emergency. Combination rules enable the system to escalate when it sees patterns that no single keyword would catch. The seed set covers known medical emergencies; the feedback loop discovers new patterns from clinician corrections.

### Why a feedback loop with synonym proposals and rule proposals?

A static keyword list will always miss new phrasing. Patients say "my chest is on fire" instead of "chest pain." Rather than maintaining the keyword list manually, the system detects gaps in real time (GPT caught it, local missed it), generates structured proposals, and lets clinicians approve them. This turns every session into training data for the local classifier.

### Why structured JSON output?

Free-text GPT responses are hard to act on programmatically. By requiring JSON with explicit fields for risk level, care level, and follow-up questions, the system can merge risk assessments, route care, and track follow-ups without parsing natural language. The fallback (treating unparseable responses as low-risk plain text) ensures the system degrades gracefully.

### Why care routing with Google Maps?

"You should see a doctor" is not actionable. Patients need to know whether to call 911, drive to urgent care, schedule an appointment, or monitor at home. Adding a Google Maps link with their zip code removes one more barrier between the recommendation and the action.

### Why a separate clinician dashboard?

The patient interface and clinician interface have fundamentally different goals. Patients need calm, clear guidance. Clinicians need data density, review controls, and the ability to correct and improve the system. A dark header (#2c3e50 vs. the patient's teal #1a6b52) makes it immediately obvious which side you are on.

### Why SQLite?

For a prototype, SQLite provides structured persistence without infrastructure. The database lives in a single file, requires no server, and supports the full query surface needed for the clinician dashboard, pattern detection, and proposal workflows. It ships with Python's standard library.

### Why password-based clinician auth?

Full authentication (OAuth, SSO) would be over-engineering for a prototype. A simple environment-variable-based password gates the review dashboard from accidental patient access while keeping the implementation focused on the triage and feedback functionality that matters.

## Architecture Decisions

- **Flask for web** — lightweight, well-understood, sufficient for a single-server deployment. The patient UI and clinician dashboard are routes in the same app.
- **Server-side session state** — Flask cookie sessions have size limits, so conversation state lives in an in-memory dict keyed by session ID. The cookie only stores the session ID.
- **OpenAI GPT-4o for conversation, GPT-4o-mini for evaluation** — balances quality (patient-facing) with cost (internal QA).
- **Pathlib for all file paths** — ensures the application works regardless of working directory.
- **Module-per-concern structure** — each module has a single responsibility, no circular imports, only main.py does CLI user I/O, only web/app.py does HTTP I/O.
- **All tests mock API calls** — the full test suite runs without an API key, making CI/CD straightforward.
- **Conversation history trimming** — keeps only the last 10 message pairs to manage token costs while maintaining context.
- **Security headers and input sanitization** — defense-in-depth for a web application handling sensitive health data, even in a prototype.

## Roadmap

See the Project Status section in README.md for potential future enhancements.
