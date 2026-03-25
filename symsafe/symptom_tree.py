"""
symptom_tree.py — Symptom-to-guidance matching using curated clinical references.

Loads a JSON mapping of common symptoms to vetted static responses and
matches them against patient input. When a match is found, the static
guidance is injected into the GPT conversation to anchor its reply to
clinically reviewed content rather than relying solely on generation.
"""

import json
from symsafe.config import BASE_DIR


def load_symptom_tree():
    """Load the symptom tree JSON from prompts/symptom_tree.json.

    Returns:
        dict: A mapping of symptom keywords to static guidance strings.
              Returns an empty dict if the file is missing or invalid.
    """
    tree_path = BASE_DIR / "prompts" / "symptom_tree.json"
    try:
        with open(tree_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load symptom_tree.json: {e}")
        return {}


def match_symptom_tree(user_input, symptom_tree):
    """Find all symptom tree entries that match the patient's input.

    Performs case-insensitive substring matching of each symptom tree
    key against the user's message.

    Args:
        user_input: The patient's message text.
        symptom_tree: A dict mapping symptom keywords to guidance strings.

    Returns:
        A list of (matched_key, guidance_response) tuples.
        Empty list if no matches found.
    """
    user_lower = user_input.lower()
    matches = []
    for key, response in symptom_tree.items():
        if key.lower() in user_lower:
            matches.append((key, response))
    return matches
