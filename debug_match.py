import json
import difflib
import re

SYMPTOM_TREE_PATH = "prompts/symptom_tree.json"

def load_symptom_tree():
    with open(SYMPTOM_TREE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def normalize_text(text):
    return re.sub(r"[^\w\s]", "", text.lower().strip())

def fuzzy_match_symptom(user_input, symptom_tree, threshold=0.6):
    normalized_input = normalize_text(user_input)
    candidates = {}
    for canonical, entry in symptom_tree.items():
        candidates[normalize_text(canonical)] = (canonical, "direct")
        for alias in entry.get("aliases", []):
            candidates[normalize_text(alias)] = (canonical, "alias")

    matches = difflib.get_close_matches(normalized_input, candidates.keys(), n=1, cutoff=threshold)
    return candidates[matches[0]] if matches else (None, None), normalized_input, matches, list(candidates.keys())

# --- RUN TEST ---
symptom_tree = load_symptom_tree()
test_input = "I keep throwing up"

(match, match_type), norm_input, matches, candidate_keys = fuzzy_match_symptom(test_input, symptom_tree)

print("\n🧪 DEBUG MATCH RESULTS")
print(f"Input: {test_input}")
print(f"Normalized: {norm_input}")
print(f"Matched Symptom: {match} (type: {match_type})")
print(f"Match Candidates: {matches}")
print(f"Total Indexed Phrases: {len(candidate_keys)}")
