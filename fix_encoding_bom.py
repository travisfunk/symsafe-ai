# fix_encoding_bom.py
files = [
    "prompts/test_cases.json",
    "prompts/learning_log.json",
    "prompts/gpt_review_log.json",
    "prompts/symptom_tree.json"
]

for path in files:
    with open(path, "r", encoding="utf-8-sig") as f:
        content = f.read()
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Cleaned BOM from {path}")
