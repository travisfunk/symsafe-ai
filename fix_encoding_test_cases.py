import json

file_path = "prompts/test_cases.json"

with open(file_path, "r", encoding="utf-8-sig") as f:
    data = json.load(f)

with open(file_path, "w", encoding="utf-8-sig") as f:
    json.dump(data, f, indent=2)

print("✅ test_cases.json re-encoded cleanly with utf-8-sig")
