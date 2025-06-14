# SymSafe AI

---

## 🔄 What's New in v1.1.0 (In Progress)

### ✅ Alias Matching + Match Trace Debugging

SymSafe now supports `aliases` in the symptom tree, enabling more natural language inputs to be correctly matched to structured triage categories. For example:

- "trouble breathing" → matched to "shortness of breath" (via alias)
- "woozy" → matched to "dizziness" (via alias)

Match logic now supports both:
- **Direct matches** (exact key in the tree)
- **Alias matches** (from a curated list of alternate expressions)

🧠 **Match Trace Debugging:**  
The CLI prints detailed trace output for every input:
- Normalized user input
- All candidate match phrases (including aliases)
- Whether a match was found (and how)

---

## 📖 Why This Matters

This version proves the system can handle real-world phrasing, even when users don’t say the “textbook” symptom names. It also introduces transparent debug tooling — showing exactly how the match was made — which is essential in real-world AI systems.

By combining fuzzy matching, structured symptom modeling, and traceable scoring, this update moves SymSafe from “cool demo” to “product-grade prototype.” It’s the kind of detail-aware engineering that hiring managers and product leads expect from a senior AI engineer or architect.

---