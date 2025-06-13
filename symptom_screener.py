import os
import datetime
import json
import difflib
import re
import sys
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")

# Load symptom tree
def load_symptom_tree():
    try:
        with open("prompts/symptom_tree.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Failed to load symptom tree: {e}")
        return {}

# Match user input to known symptoms
def normalize_text(text):
    return re.sub(r"[^\w\s]", "", text.lower().strip())

def fuzzy_match_symptom(user_input, symptom_tree, threshold=0.6):
    normalized_input = normalize_text(user_input)
    normalized_to_key = {}

    for key, entry in symptom_tree.items():
        normalized_to_key[normalize_text(key)] = key
        if isinstance(entry, dict) and "aliases" in entry:
            for alias in entry["aliases"]:
                normalized_to_key[normalize_text(alias)] = key

    matches = difflib.get_close_matches(normalized_input, normalized_to_key.keys(), n=1, cutoff=threshold)
    return normalized_to_key[matches[0]] if matches else None

# Generate GPT response
def generate_response(symptom):
    prompt = (
        f"The user reported: {symptom}\n"
        "You are an AI assistant trained to give safe, empathetic triage advice. "
        "Do not diagnose. If the symptom is serious, recommend seeing a healthcare provider. "
        "Keep your response under 60 words. Begin your response now:"
    )

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150
    )
    return response.choices[0].message.content.strip()

# Classify risk from tree
def classify_risk(symptom_key, tree):
    entry = tree.get(symptom_key)
    if isinstance(entry, dict) and "urgency" in entry:
        return entry["urgency"].upper()
    return "UNKNOWN"

# Evaluate AI response
def evaluate_response(response, risk):
    checkmarks = {
        "safe": "✅ Safe" if "seek" in response.lower() or "recommend" in response.lower() else "⚠️ Might lack safety",
        "empathy": "✅ Empathetic tone" if "sorry" in response.lower() else "⚠️ Might lack empathy",
        "no_diagnosis": "✅ Avoided diagnosis" if "you might have" not in response.lower() else "⚠️ Diagnosed",
        "escalation": "✅ Escalation offered when appropriate" if "provider" in response.lower() or "emergency" in response.lower() else "⚠️ No escalation",
        "clarity": "✅ Clear and accessible language" if len(response.split()) <= 60 else "⚠️ May be too long"
    }

    print("\n🧠 Evaluation:")
    print("The assistant's response was:")
    for key, result in checkmarks.items():
        print(f"- {result}")

# Logging
def log_to_markdown(user_input, response, risk_level):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("logs", exist_ok=True)
    log_path = f"logs/convo_{timestamp}.md"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"# SymSafe Triage Log ({timestamp})\n")
        f.write(f"**User input:** {user_input}\n\n")
        f.write(f"**Risk level:** {risk_level}\n\n")
        f.write(f"**Assistant response:**\n{response}\n")

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

# Review learning log
def review_learning_log():
    try:
        with open("logs/learning_log.json", "r", encoding="utf-8") as f:
            for line in f:
                item = json.loads(line)
                print(f"\n📝 Prompt: {item['input']}\n✅ Correction: {item['correction']}")
    except FileNotFoundError:
        print("No learning log found.")

# Banner
def print_banner():
    print("\n╔════════════════════════════════════╗")
    print("║     SymSafe – Virtual Triage AI    ║")
    print("╚════════════════════════════════════╝")
    print("💬 Type symptoms or questions | Type 'exit' to quit")

# CLI mode
def interactive_cli():
    tree = load_symptom_tree()
    print_banner()

    while True:
        user_input = input("\n🧑 You: ")
        if user_input.lower() == "exit":
            break

        match = fuzzy_match_symptom(user_input, tree)
        if match:
            response = tree[match]["response"]
            urgency = tree[match]["urgency"]
        else:
            response = generate_response(user_input)
            urgency = "LOW/MODERATE"

        urgency_label = "🔴 HIGH RISK" if urgency == "high" else "🟢 Low/Moderate Risk"
        print(f"\n🤖 AI Assistant [{urgency_label}]:\n{response}")

        evaluate_response(response, urgency)
        log_to_markdown(user_input, response, urgency)

# CLI entry point
def main():
    if "--learn" in sys.argv:
        run_learning_mode()
    elif "--review-log" in sys.argv:
        review_learning_log()
    else:
        interactive_cli()

if __name__ == "__main__":
    main()
