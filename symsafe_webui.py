from flask import Flask, render_template, request, jsonify
import json
import os

app = Flask(__name__)

# Load symptom tree
SYMPTOM_TREE_PATH = "prompts/symptom_tree.json"

def load_symptom_tree():
    with open(SYMPTOM_TREE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_symptom_tree(tree):
    with open(SYMPTOM_TREE_PATH, "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2)

# --- Dev Plan for v1.1 Web UI Build (added 2025-06-16) ---
# 1. /test         → Primary UI for entering symptoms via text/voice and getting responses
# 2. /edit-aliases → Trainer/admin page to manage aliases, responses, and escalation flags
# 3. /train        → Shows unmatched inputs and lets practitioner map them
# 4. /edit-tests   → Edit and expand test_cases.json visually
# 5. /admin        → Upload/download configs (optional)
# 6. /review-tests → View last QA run + flag failures (optional polish)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/test", methods=["GET", "POST"])
def test():
    if request.method == "POST":
        user_input = request.json.get("input", "").strip()
        if not user_input:
            return jsonify({"error": "No input provided."}), 400

        try:
            from symptom_screener import fuzzy_match_symptom, classify_risk, generate_response, evaluate_response, load_symptom_tree as load_tree
        except ImportError:
            return jsonify({"error": "Matching logic not found."}), 500

        tree = load_tree()
        match, match_type = fuzzy_match_symptom(user_input, tree, threshold=0.5)
        if not match:
            try:
                with open("prompts/learning_log.json", "r", encoding="utf-8") as f:
                    learning = json.load(f)
            except:
                learning = []
            if user_input not in [e.get("input") for e in learning]:
                learning.append({"input": user_input})
                with open("prompts/learning_log.json", "w", encoding="utf-8") as f:
                    json.dump(learning, f, indent=2)
            return jsonify({
                "matched_symptom": "None",
                "response": "Sorry, I couldn't confidently match that to a known symptom. Please try rephrasing.",
                "evaluation": {}
            })

        matched_entry = tree[match]
        response = matched_entry.get("response") or generate_response(match)
        urgency = matched_entry.get("urgency", "UNKNOWN")

        # Safety scoring
        checks = {
            "safe": any(word in response.lower() for word in ["seek", "contact", "urgent"]),
            "empathy": any(word in response.lower() for word in ["sorry", "difficult", "uncomfortable", "tough"]),
            "diagnosis": not any(word in response.lower() for word in ["you might have", "it could be"]),
            "escalation": "provider" in response.lower() or "emergency" in response.lower() or "urgent" in response.lower()
        }

        return jsonify({
            "matched_symptom": match,
            "response": response,
            "evaluation": checks
        })

    return render_template("test.html")

@app.route("/edit-aliases")
def edit_aliases():
    tree = load_symptom_tree()
    return render_template("edit_aliases.html", tree=tree)

@app.route("/save-aliases", methods=["POST"])
def save_aliases():
    tree = request.json
    save_symptom_tree(tree)
    return jsonify({"status": "saved"})

@app.route("/train")
def train():
    try:
        with open("prompts/learning_log.json", "r", encoding="utf-8") as f:
            entries = json.load(f)
    except:
        entries = []

    tree = load_symptom_tree()
    return render_template("train.html", entries=entries, symptoms=list(tree.keys()))

@app.route("/edit-tests")
def edit_tests():
    return render_template("edit_tests.html")

@app.route("/get-tests")
def get_tests():
    try:
        with open("prompts/test_cases.json", "r", encoding="utf-8") as f:
            tests = json.load(f)
    except:
        tests = []
    return jsonify(tests)

@app.route("/save-tests", methods=["POST"])
def save_tests():
    data = request.get_json()
    with open("prompts/test_cases.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return jsonify({"status": "saved"})

@app.route("/save-mapping", methods=["POST"])
def save_mapping():
    data = request.get_json()
    input_text = data.get("input", "").strip()
    target = data.get("map_to", "").strip()

    if not input_text or not target:
        return jsonify({"error": "Invalid mapping data."}), 400

    try:
        with open("prompts/symptom_tree.json", "r", encoding="utf-8") as f:
            tree = json.load(f)
    except:
        tree = {}

    if target in tree:
        aliases = set(tree[target].get("aliases", []))
        aliases.add(input_text)
        tree[target]["aliases"] = list(aliases)
    else:
        tree[target] = {
            "response": "[placeholder response]",
            "urgency": "LOW",
            "aliases": [input_text],
            "requires_escalation": False
        }

    with open("prompts/symptom_tree.json", "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2)

    # Remove from learning log
    try:
        with open("prompts/learning_log.json", "r", encoding="utf-8") as f:
            learning = json.load(f)
        learning = [e for e in learning if e.get("input") != input_text]
        with open("prompts/learning_log.json", "w", encoding="utf-8") as f:
            json.dump(learning, f, indent=2)
    except:
        pass

    return jsonify({"status": "saved"})

@app.route("/review-tests")
def review_tests():
    try:
        with open("logs/qa_results.md", "r", encoding="utf-8") as f:
            markdown = f.read()
    except:
        markdown = "No QA results found."
    return render_template("review_tests.html", markdown=markdown)

@app.route("/admin")
def admin():
    files = {}
    paths = {
        "symptom_tree.json": "prompts/symptom_tree.json",
        "test_cases.json": "prompts/test_cases.json",
        "learning_log.json": "prompts/learning_log.json"
    }

    for name, path in paths.items():
        try:
            with open(path, "r", encoding="utf-8") as f:
                files[name] = f.read()
        except Exception as e:
            files[name] = f"⚠️ Error loading {name}: {str(e)}"

    return render_template("admin.html", files=files)

@app.route("/admin2")
def admin2():
    files = {}
    paths = {
        "symptom_tree.json": "prompts/symptom_tree.json",
        "test_cases.json": "prompts/test_cases.json",
        "learning_log.json": "prompts/learning_log.json"
    }

    for name, path in paths.items():
        try:
            with open(path, "r", encoding="utf-8") as f:
                files[name] = f.read()
        except Exception as e:
            files[name] = f"⚠️ Error loading {name}: {str(e)}"

    return render_template("admin2.html", files=files)

if __name__ == "__main__":
    app.run(debug=True)
