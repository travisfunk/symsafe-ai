# SymSafe AI — v1.1 Project Tracker

This file serves as a living document for tracking SymSafe AI development. Paste this into a future chat to resume work or verify status.

---

## ✅ Current Branch
`v1.1-dev` (local development only, not public)

---

## 🧭 Project Goal
Refactor and polish all SymSafe AI routes for v1.1 release, making the app fully trainer-usable in the browser with modern UI and audit tools.

---

## ✅ Completed Routes

### `/review-gpt` (tag: `v1.1-dev-review-gpt`)
- [x] Collapsible reviewed entries
- [x] Edit mode with prefilled values
- [x] 🚩 Flag support + red border
- [x] “Show Reviewed” + “Show Flagged” filters
- [x] CSV export
- [x] Sticky header with progress bar
- [x] Save confirmation toast
- [x] Full layout polish

✅ **This page is complete and stable.**

---

## 🔧 Pages Still To Complete

### `/edit-aliases`
- [ ] Flag editing (e.g. requires escalation)
- [ ] Improved UI layout
- [ ] Inline guidance and response examples

### `/train`
- [ ] Confirm JSON mappings update correctly
- [ ] Trainer UI for mapping unmatched input
- [ ] Create new entries directly from UI

### `/edit-tests`
- [ ] Load + edit `test_cases.json`
- [ ] Validate input structure
- [ ] Add visual schema help

### `/review-tests`
- [ ] Display last QA run markdown
- [ ] Highlight failures
- [ ] Filter: failed only

### `/voice-log`
- [ ] Show voice transcripts
- [ ] Add filter + download
- [ ] Show flagged or retried input

### `/audit-summary`
- [ ] Stats: matched vs GPT fallback
- [ ] Filter by date or escalation
- [ ] Graphs or sparklines for UI polish

---

## 📌 Git Strategy

- Work locally in `v1.1-dev` branch
- After completing each route, run:
  ```
  git add .
  git commit -m "Finish /ROUTE for v1.1"
  git tag v1.1-dev-ROUTE
  ```
- When all pages are complete and verified, tag `v1.1.0` and prepare release notes

---

## 🔒 Tags Used So Far

| Tag | Description |
|-----|-------------|
| `v1.1-dev-review-gpt` | Finalized `/review-gpt` with all v1.1 polish |

---

## 🧠 How to Use This File

- ✅ Paste this into any future ChatGPT session
- ✅ I’ll use it to pick up right where we left off
- ✅ Update it each time we finalize another page

---

Last updated: {{REPLACE_ME_ON_NEXT_EDIT}}
