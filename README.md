# SymSafe AI 🤖💊

**SymSafe** is a command-line triage assistant that simulates how conversational AI can respond safely, clearly, and empathetically to patient-reported symptoms.

Built with GPT-4o, it includes guardrails for risk detection, built-in response evaluation, customizable prompts, and structured symptom mapping. This project is designed for healthcare-aligned portfolios, AI prototyping, or teaching safe assistant behavior in clinical contexts.

---

## 🚡 Why It Matters

Healthcare AI needs more than just smart responses. It must:

* Improve **patient outcomes**, not just generate text
* Use **empathetic language** while avoiding hallucinated advice
* Be **auditable**, **customizable**, and **escalation-aware**

SymSafe was created to model how structured + generative logic can coexist — and to demonstrate thoughtful prompt design, modular architecture, and self-regulating agents.

---

## ✅ Key Features (v1.0.0)

* **Interactive CLI Assistant**

  * Talk to the agent via terminal in real time

* **Risk Classification**

  * Flags red-flag symptoms and shows HIGH vs LOW/MODERATE risk

* **GPT-Based Self-Evaluation**

  * Assistant responses are graded by a second AI for empathy, clarity, escalation, and tone

* **Symptom Tree Matching**

  * Predefined JSON maps known symptoms to static follow-ups (avoids hallucinations)

* **Learning Mode (`--learn`)**

  * Enables evaluator coaching with training insights for SEs/devs

* **Markdown Logging**

  * Every session auto-logged with assistant response and evaluation notes

* **Modular Prompt Library**

  * Prompts, symptom tree, and responses stored in `prompts/` folder for reuse or customization

---

## 📊 Example Interaction

```
$ python symptom_screener.py --learn

╔═════════════════════════════════════════════════╗
║  SymSafe – Virtual Triage AI   🤠 LEARNING MODE ║
╚═════════════════════════════════════════════════╝

💬 Type symptoms or questions | Type 'exit' to quit
📘 LEARNING MODE ENABLED – Explanations will be included

👤 You: I’ve had chest pain since last night.

🤖 AI Assistant [🔴 HIGH RISK]:
I'm not a doctor, but chest pain can be serious. Please speak with a healthcare provider right away or visit an emergency room.

🧠 Evaluation:
- [x] Safe
- [x] Empathetic tone
- [x] Avoided diagnosis
- [x] Escalation offered
- [x] Clear and accessible language
```

---

## 🧠 Architecture Overview

* `symptom_screener.py` — Main script (CLI + logic)
* `prompts/base_prompt.txt` — GPT system message
* `prompts/symptom_tree.json` — Symptom → response mapping (customizable)
* `logs/` — Markdown logs for every session
* `.env` — API key (excluded via `.gitignore`)

---

## 🚧 Future Enhancements (Planned)

* Web UI (Flask or Streamlit)
* Batch QA test harness + CSV import/export
* Better fuzzy symptom matching (e.g. "my chest hurts" → "chest pain")
* Ideal response capture for training/labeling
* Expand symptom tree with branching logic and scoring

---

## 📚 About This Project

This project demonstrates:

* How to safely embed AI in healthcare-adjacent use cases
* Practical prompt design, fallback planning, and evaluation agents
* Modular, auditable patterns for deploying AI in risky domains

It is designed for:

* AI product managers
* Healthcare engineers
* Clinical IT leaders
* Responsible AI builders

**Note:** SymSafe is not intended for real patient use. It is a prototype simulation for demonstration, education, and portfolio purposes only.

---

## 📅 Version

Current: `v1.0.0` — CLI demo with triage logic, evaluation agent, and learning mode

---

## 👤 Contact

Want to discuss this project or collaborate?
[Reach out via LinkedIn](https://www.linkedin.com/in/tfunkhouser/)
