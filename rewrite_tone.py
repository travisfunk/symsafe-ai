import os
import json
from dotenv import load_dotenv
from openai import OpenAI

# Load API key
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = (
    "You are an assistant trained to rewrite medical triage messages. "
    "Add a warm, empathetic sentence at the beginning, but do not diagnose. "
    "Keep the whole message under 60 words and safe for patient communication."
)

def rewrite_response_tone(original):
    try:
        result = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Original response: {original}"}
            ],
            temperature=0.7,
            max_tokens=150
        )
        return result.choices[0].message.content.strip()
    except Exception as e:
        return f"[ERROR] {e}"

# Load existing symptom tree
with open("prompts/symptom_tree.json", "r", encoding="utf-8") as f:
    tree = json.load(f)

# Rewrite each response
for symptom, entry in tree.items():
    old = entry["response"]
    new = rewrite_response_tone(old)
    print(f"\n📝 {symptom}\n→ {new}")
    entry["response"] = new

# Save to new file
with open("prompts/symptom_tree_tone_rewritten.json", "w", encoding="utf-8") as f:
    json.dump(tree, f, indent=2)

print("\n✅ Rewritten responses saved to prompts/symptom_tree_tone_rewritten.json")
