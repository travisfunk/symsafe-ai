"""
intake.py — Guided intake questionnaire for structured patient data collection.

Walks patients through seven structured questions (concern, location, onset,
severity, trajectory, medications, chronic conditions) before the open
conversation begins. This ensures GPT has meaningful clinical context from
the start, especially for patients who struggle to articulate symptoms.
"""

# Defines the seven intake steps in order. Each step specifies:
# id (for answer storage), prompt (displayed to patient), options (numbered
# choices or None for free text), allow_freetext (whether to accept typed
# input when options exist), and help_text (clarification shown to patient).
INTAKE_STEPS = [
    {
        "id": "concern",
        "prompt": "What's your main concern today?",
        "options": ["Pain", "Breathing issues", "Digestive issues", "Skin issue", "Mental health", "Injury", "Other"],
        "allow_freetext": True,
        "help_text": "You can pick one or type your own description."
    },
    {
        "id": "location",
        "prompt": "Where is the problem located?",
        "options": ["Head", "Chest", "Abdomen/Stomach", "Back", "Arms/Hands", "Legs/Feet", "Skin", "All over", "Not applicable"],
        "allow_freetext": True,
        "help_text": "Pick the closest match or type your own."
    },
    {
        "id": "onset",
        "prompt": "When did this start?",
        "options": ["Just now", "Today", "Yesterday", "A few days ago", "About a week", "More than a week"],
        "allow_freetext": False,
        "help_text": None
    },
    {
        "id": "severity",
        "prompt": "On a scale of 1-10, how severe is it? (1 = barely noticeable, 10 = worst ever)",
        "options": None,
        "allow_freetext": True,
        "help_text": "Just type a number from 1 to 10."
    },
    {
        "id": "trajectory",
        "prompt": "Is it getting better, worse, or staying the same?",
        "options": ["Getting better", "Getting worse", "Staying the same", "Comes and goes"],
        "allow_freetext": False,
        "help_text": None
    },
    {
        "id": "medications",
        "prompt": "Are you currently taking any medications? (type them or 'none')",
        "options": None,
        "allow_freetext": True,
        "help_text": "List any medications, or type 'none'."
    },
    {
        "id": "conditions",
        "prompt": "Do you have any chronic conditions?",
        "options": ["Diabetes", "Heart disease", "Asthma/COPD", "High blood pressure", "None", "Other"],
        "allow_freetext": True,
        "help_text": "Pick one or more, or type your own. Type 'none' if none."
    }
]

# Maps step IDs to human-readable labels for display and logging.
LABEL_MAP = {
    "concern": "Main concern",
    "location": "Location",
    "onset": "Onset",
    "severity": "Severity",
    "trajectory": "Trajectory",
    "medications": "Medications",
    "conditions": "Chronic conditions",
}


def run_intake():
    """Run the guided intake questionnaire interactively.

    Presents each step in sequence, collecting answers via numbered
    options or free text. Patients can type 'skip' to jump to the
    conversation with partial answers, or 'exit'/'quit' to end.

    Returns:
        A dict of answers keyed by step ID (may be partial if skipped),
        or None if the user chose to exit.
    """
    print("\nLet's start by gathering some basic information about what brought you here today.")
    print("You can type 'skip' at any point to jump to the conversation.\n")

    answers = {}

    for step in INTAKE_STEPS:
        print(f"  {step['prompt']}")
        if step["options"]:
            for i, opt in enumerate(step["options"], 1):
                print(f"    {i}. {opt}")
        if step["help_text"]:
            print(f"    ({step['help_text']})")

        while True:
            response = input("  → ").strip()

            if response.lower() == "skip":
                return answers
            if response.lower() in ("exit", "quit"):
                return None
            if not response:
                print("    Please enter a response.")
                continue

            # Severity requires numeric validation (1-10)
            if step["id"] == "severity":
                try:
                    val = int(response)
                    if 1 <= val <= 10:
                        answers["severity"] = str(val)
                        break
                    else:
                        print("    Please enter a number between 1 and 10.")
                        continue
                except ValueError:
                    print("    Please enter a number between 1 and 10.")
                    continue

            # Option-based steps: accept number selection or freetext if allowed
            if step["options"]:
                try:
                    idx = int(response)
                    if 1 <= idx <= len(step["options"]):
                        answers[step["id"]] = step["options"][idx - 1]
                        break
                    else:
                        print(f"    Please enter a number between 1 and {len(step['options'])}.")
                        if step["allow_freetext"]:
                            print("    Or type your own response.")
                        continue
                except ValueError:
                    if step["allow_freetext"]:
                        answers[step["id"]] = response
                        break
                    else:
                        print(f"    Please enter a number between 1 and {len(step['options'])}.")
                        continue
            else:
                answers[step["id"]] = response
                break

    return answers


def format_intake_context(answers):
    """Convert intake answers into a context string for the GPT system message.

    Builds a readable summary from the answers dict, mapping step IDs
    to human-readable labels. Severity is formatted as "N/10".

    Args:
        answers: A dict of intake answers keyed by step ID.

    Returns:
        A context string like "Patient intake information: Main concern: Pain, ...".
        Returns an empty string if answers is empty.
    """
    if not answers:
        return ""

    parts = []
    for step_id, label in LABEL_MAP.items():
        if step_id in answers:
            value = answers[step_id]
            if step_id == "severity":
                parts.append(f"{label}: {value}/10")
            else:
                parts.append(f"{label}: {value}")

    if not parts:
        return ""

    return "Patient intake information: " + ", ".join(parts)
