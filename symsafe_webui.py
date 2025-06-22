from flask import Flask, render_template, request, jsonify, redirect
import json
import os
import csv
import io

app = Flask(__name__)

SYMPTOM_TREE_PATH = "prompts/symptom_tree.json"

def load_symptom_tree():
    with open(SYMPTOM_TREE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_symptom_tree(tree):
    with open(SYMPTOM_TREE_PATH, "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2)

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
    return admin()

@app.route("/export")
def export():
    return render_template("export.html")

@app.route("/run-tests")
def run_tests():
    return render_template("run_tests.html")

@app.route("/voice-log")
def voice_log():
    return render_template("voice_log.html")

@app.route("/audit-summary")
def audit_summary():
    return render_template("audit_summary.html")

@app.route("/review-gpt", methods=["GET", "POST"])
def review_gpt():
    learning_log_path = "prompts/learning_log.json"
    review_log_path = "prompts/gpt_review_log.json"

    os.makedirs("prompts", exist_ok=True)
    for path in [learning_log_path, review_log_path]:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    try:
        with open(learning_log_path, "r", encoding="utf-8") as f:
            learning_log = json.load(f)
    except:
        learning_log = {}

    try:
        with open(review_log_path, "r", encoding="utf-8") as f:
            reviews = json.load(f)
    except:
        reviews = {}

    if request.method == "POST":
        entry_id = request.form.get("entry_id")
        if entry_id:
            reviews[entry_id] = {
                "empathy": request.form.get("empathy"),
                "escalation": request.form.get("escalation"),
                "diagnosis": request.form.get("diagnosis"),
                "clarity": request.form.get("clarity"),
                "comments": request.form.get("comments", ""),
                "flagged": request.form.get("flagged") == "true"
            }
            with open(review_log_path, "w", encoding="utf-8") as f:
                json.dump(reviews, f, indent=2)
        return redirect("/review-gpt")

    return render_template("review_gpt.html", learning_log=learning_log, reviews=reviews)

@app.route("/download-reviews")
def download_reviews():
    log_path = "prompts/gpt_review_log.json"
    input_path = "prompts/learning_log.json"

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            reviews = json.load(f)
        with open(input_path, "r", encoding="utf-8") as f:
            inputs = json.load(f)
    except:
        reviews = {}
        inputs = {}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["entry_id", "input", "gpt_response", "empathy", "escalation", "diagnosis", "clarity", "comments", "flagged"])

    for entry_id, review in reviews.items():
        input_text = inputs.get(entry_id, {}).get("input", "")
        gpt_response = inputs.get(entry_id, {}).get("gpt_response", "")
        writer.writerow([
            entry_id,
            input_text,
            gpt_response,
            review.get("empathy", ""),
            review.get("escalation", ""),
            review.get("diagnosis", ""),
            review.get("clarity", ""),
            review.get("comments", ""),
            review.get("flagged", False)
        ])

    output.seek(0)
    return app.response_class(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=gpt_review_log.csv"}
    )

@app.route("/login")
def login():
    return render_template("login.html")

if __name__ == "__main__":
    app.run(debug=True)
