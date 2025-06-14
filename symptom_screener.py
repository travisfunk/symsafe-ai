import os
import datetime
import json
import difflib
import re
import sys
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Load symptom tree
def load_symptom_tree():
    try:
        with open("prompts/symptom_tree.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Failed to load symptom tree: {e}")
        return {}

# Normalize input
def normalize_text(text):
    return re.sub(r"[^\w\s]", "", text.lower().strip())

# Alias-aware fuzzy matching
def fuzzy_match_symptom(user_input, symptom_tree, threshold=0.6):
    normalized_input = normalize_text(user_input)
    candidates = {}

    for canonical, entry in symptom_tree.items():
        candidates[normalize_text(canonical)] = (canonical, "direct")
        for alias in entry.get("aliases", []):
            candidates[normalize_text(alias)] = (canonical, "alias")

    matches = difflib.get_close_matches(normalized_input, candidates.keys(), n=1, cutoff=threshold)
    print(f"🔎 Debug: normalized input = '{normalized_input}'")
    print(f"🔎 Debug: match candidates = {list(candidates.keys())}")
    print(f"🔎 Debug: match result = {matches}")
    return candidates[matches[0]] if matches else (None, None)

# Generate GPT fallback
def generate_response(symptom):
    prompt = (
        f"The user reported: {symptom}\n"
        "You are an AI assistant trained to give safe, empathetic triage advice. "
        "Do not diagnose. If the symptom is serious, recommend seeing a healthcare provider. "
        "Keep your response under 60 words. Begin your response now:"
    )

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150
    )
    return response.choices[0].message.content.strip()

# Classify urgency
def classify_risk(symptom_key, tree):
    entry = tree.get(symptom_key)
    if isinstance(entry, dict) and "urgency" in entry:
        return entry["urgency"].upper()
    return "UNKNOWN"

# Evaluate response
def evaluate_response(response, risk):
    checks = {
        "safe": "✅ Safe" if "seek" in response.lower() or "recommend" in response.lower() else "⚠️ Might lack safety",
        "empathy": "✅ Empathetic tone" if "sorry" in response.lower() else "⚠️ Might lack empathy",
        "no_diagnosis": "✅ Avoided diagnosis" if "you might have" not in response.lower() else "⚠️ Diagnosed",
        "escalation": "✅ Escalation offered" if "provider" in response.lower() or "emergency" in response.lower() else "⚠️ No escalation",
        "clarity": "✅ Clear & concise" if len(response.split()) <= 60 else "⚠️ May be too long"
    }

    print("\n🧠 Evaluation:")
    for result in checks.values():
        print(f"- {result}")

# Log to Markdown
def log_to_markdown(user_input, response, risk_level, match_type):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("logs", exist_ok=True)
    log_path = f"logs/convo_{timestamp}.md"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"# SymSafe Triage Log ({timestamp})\n")
        f.write(f"**User input:** {user_input}\n")
        f.write(f"**Match type:** {match_type}\n")
        f.write(f"**Risk level:** {risk_level}\n\n")
        f.write(f"**Response:**\n{response}\n")

# Learning mode
def run_learning_mode():
    tree = load_symptom_tree()
    while True:
        user_input = input("🧠 Enter symptom (or 'exit'): ")
        if user_input.lower() == "exit":
            break

        corrected_response = input("🔧 Enter corrected response: ")
        if not corrected_response.strip():
            continue

        with open("logs/learning_log.json", "a", encoding="utf-8") as f:
            f.write(json.dumps({"input": user_input, "correction": corrected_response}) + "\n")
        print("✅ Saved to learning log.\n")

# Review corrections
def review_learning_log():
    try:
        with open("logs/learning_log.json", "r", encoding="utf-8") as f:
            for line in f:
                item = json.loads(line)
                print(f"\n📝 Prompt: {item['input']}\n✅ Correction: {item['correction']}")
    except FileNotFoundError:
        print("No learning log found.")

# CLI banner
def print_banner():
    print("\n╔════════════════════════════════════╗")
    print("║     SymSafe – Virtual Triage AI    ║")
    print("╚════════════════════════════════════╝")
    print("💬 Type symptoms or questions | Type 'exit' to quit")

# CLI loop
def interactive_cli():
    tree = load_symptom_tree()
    print_banner()

    while True:
        user_input = input("\n🧑 You: ")
        if user_input.lower() == "exit":
            break

        match_key, match_type = fuzzy_match_symptom(user_input, tree)
        if match_key:
            print(f"🧠 Matched '{user_input}' to '{match_key}' (via {match_type})")
            response = tree[match_key]["response"]
            urgency = tree[match_key]["urgency"]
        else:
            print(f"⚠️ No match found. Using GPT fallback.")
            response = generate_response(user_input)
            urgency = "LOW/MODERATE"
            match_type = "GPT fallback"

        label = "🔴 HIGH RISK" if urgency.lower() == "high" else "🟢 Low/Moderate Risk"
        print(f"\n🤖 Assistant [{label}]:\n{response}")
        evaluate_response(response, urgency)
        log_to_markdown(user_input, response, urgency, match_type)

# Entry point
def main():
    if "--learn" in sys.argv:
        run_learning_mode()
    elif "--review-log" in sys.argv:
        review_learning_log()
    else:
        interactive_cli()

if __name__ == "__main__":
    main()