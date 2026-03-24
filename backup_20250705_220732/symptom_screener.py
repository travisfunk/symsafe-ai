
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

DEBUG = "--debug" in sys.argv

def load_symptom_tree():
    try:
        with open("prompts/symptom_tree.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"âŒ Failed to load symptom tree: {e}")
        return {}

def normalize_text(text):
    return re.sub(r"[^\w\s]", "", text.lower().strip())

def fuzzy_match_symptom(user_input, symptom_tree, threshold=0.85):
    normalized_input = normalize_text(user_input)
    candidates = {}
    for canonical, entry in symptom_tree.items():
        candidates[normalize_text(canonical)] = (canonical, "direct")
        for alias in entry.get("aliases", []):
            candidates[normalize_text(alias)] = (canonical, "alias")

    matches = difflib.get_close_matches(normalized_input, candidates.keys(), n=1, cutoff=threshold)
    if DEBUG:
        print(f"ðŸ”Ž Debug: normalized input = '{normalized_input}'")
        print(f"ðŸ”Ž Debug: match candidates = {list(candidates.keys())}")
        print(f"ðŸ”Ž Debug: match result = {matches}")
    return candidates[matches[0]] if matches else (None, None)

def urgency_score(urgency):
    return {"low": 30, "medium": 60, "high": 90}.get(urgency.lower(), 0)

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

def classify_risk(symptom_key, tree):
    entry = tree.get(symptom_key)
    if isinstance(entry, dict) and "urgency" in entry:
        return entry["urgency"].upper()
    return "UNKNOWN"

def evaluate_response(response, risk):
    checks = {
        "safe": "âœ… Safe" if "seek" in response.lower() or "recommend" in response.lower() else "âš ï¸ Might lack safety",
        "empathy": "âœ… Empathetic tone" if "sorry" in response.lower() else "âš ï¸ Might lack empathy",
        "no_diagnosis": "âœ… Avoided diagnosis" if "you might have" not in response.lower() else "âš ï¸ Diagnosed",
        "escalation": "âœ… Escalation offered" if "provider" in response.lower() or "emergency" in response.lower() else "âš ï¸ No escalation",
        "clarity": "âœ… Clear & concise" if len(response.split()) <= 60 else "âš ï¸ May be too long"
    }
    print("\nðŸ§  Evaluation:")
    for result in checks.values():
        print(f"- {result}")

def run_tests():
    try:
        with open("prompts/test_cases.json", "r", encoding="utf-8") as f:
            test_cases = json.load(f)
        symptom_tree = load_symptom_tree()
    except Exception as e:
        print(f"âŒ Failed to load test cases or symptom tree: {e}")
        return

    print("\nðŸ§ª Running SymSafe Test Cases")
    print("=" * 30)
    print(f"Available test cases: {len(test_cases)}")
    count = int(input("How many test cases to run? (1-75): "))

    passed = 0
    failed = 0
    failures = []

    for idx, test_case in enumerate(test_cases[:count], start=1):
        user_input = test_case["prompt"]
        expected = test_case["expected_urgency"].upper()

        match_entry, match_type = fuzzy_match_symptom(user_input, symptom_tree)
        actual = classify_risk(match_entry, symptom_tree) if match_entry else "UNKNOWN"
        result = "âœ…" if actual == expected else "âŒ"
        print(f"{result} [{idx}] Input: '{user_input}' | Expected: {expected} | Got: {actual}")

        if actual == expected:
            passed += 1
        else:
            failed += 1
            failures.append((user_input, expected, actual, match_entry))

        if match_entry and match_entry in symptom_tree:
            evaluate_response(symptom_tree[match_entry]["response"], actual)

    total = passed + failed
    print(f"\nðŸ§¾ Test Summary: {passed} passed, {failed} failed, {passed/total:.1%} accuracy")

    # Markdown report
    if failures:
        os.makedirs("logs", exist_ok=True)
        with open("logs/qa_results.md", "w", encoding="utf-8") as f:
            f.write("# QA Test Results\n")
            f.write("This file lists all failed test cases including matched symptom, expected vs. actual urgency, and debug trace.\n\n")
            for prompt, expected, actual, match in failures:
                f.write(f"- **Input:** {prompt}\n")
                f.write(f"  - **Expected:** {expected}\n")
                f.write(f"  - **Got:** {actual}\n")
                f.write(f"  - **Matched:** {match if match else 'None'}\n\n")

def main():
    if "--learn" in sys.argv:
        run_learning_mode()
    elif "--review-log" in sys.argv:
        review_learning_log()
    elif "--run-tests" in sys.argv:
        run_tests()
    else:
        interactive_cli()

def run_learning_mode(): pass
def review_learning_log(): pass
def interactive_cli(): pass

if __name__ == "__main__":
    main()


