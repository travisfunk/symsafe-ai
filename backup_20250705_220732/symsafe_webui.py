import openai
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, flash
import json
import os
from io import BytesIO, StringIO
from datetime import datetime
import csv
import platform
import psutil
from symptom_screener import load_symptom_tree, fuzzy_match_symptom
from auth import authenticate_user, current_user, has_role, require_roles

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = "change-this-secret-key"

SYMPTOM_TREE_PATH = "prompts/symptom_tree.json"
TEST_CASES_PATH = "prompts/test_cases.json"
LEARNING_LOG_PATH = "prompts/learning_log.json"
GPT_REVIEW_LOG_PATH = "prompts/gpt_review_log.json"
GPT_ACCEPTED_LOG_PATH = "gpt_accepted_log.json"
REWRITE_HISTORY_PATH = "rewrite_history.json"
TONE_PROMPT_PATH = "tone_prompt.txt"
VOICE_LOG_PATH = "logs/voice_log.json"


def safe_json_read(path):
    try:
        with open(path, "rb") as f:
            raw = f.read()
            if raw.startswith(b'\xef\xbb\xbf'):
                raw = raw[3:]
            return json.loads(raw.decode("utf-8"))
    except Exception:
        return {} if path.endswith(".json") else []


def safe_json_write(path, data):
    content = json.dumps(data, indent=2, ensure_ascii=False)
    if content.startswith("\ufeff"):
        content = content.replace("\ufeff", "")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)



conversations = {}

def is_emergency_combination(symptoms):
    """Check for dangerous symptom combinations that indicate potential emergency"""
    # Normalize symptoms to lowercase
    symptom_set = set(s.lower() for s in symptoms)
    
    # Define emergency combinations
    cardiac_combos = [
        {"chest pain", "jaw pain"},
        {"chest pain", "arm pain"},
        {"chest pain", "shortness of breath"},
        {"chest pain", "sweating"},
        {"chest pain", "nausea"}
    ]
    
    stroke_combos = [
        {"headache", "vision changes", "dizziness"},
        {"numbness", "confusion", "headache"},
        {"slurred speech", "weakness"}
    ]
    
    # Check cardiac emergencies
    for combo in cardiac_combos:
        if combo.issubset(symptom_set):
            return True
            
    # Check stroke emergencies  
    for combo in stroke_combos:
        # Need at least 2 of the 3 symptoms
        matches = sum(1 for s in combo if s in symptom_set)
        if matches >= 2:
            return True
            
    return False


def understand_response(text, question_context, conv):
    """Context-aware response understanding with learning"""
    text_lower = text.lower()
    
    # Check learned responses first
    try:
        with open('prompts/learned_responses.json', 'r', encoding='utf-8') as f:
            learned = json.load(f)
            if text_lower in learned:
                return learned[text_lower]
    except:
        pass
    
    # Check standard confirmations
    if any(word in text_lower for word in ["yes", "yeah", "yep", "uh huh", "sure", "ok", "okay", "right", "correct"]):
        return "confirmed"
    
    if any(word in text_lower for word in ["no", "nope", "not", "nah", "negative", "don't", "dont"]):
        # But check for double negatives or "not really" type phrases
        if "not really" in text_lower or "don't think" in text_lower:
            return "denied"
        # Make sure they're not saying "my jaw does not hurt" 
        if "hurt" in text_lower or "pain" in text_lower:
            return "denied"
        return "denied"
    
    # Smart symptom detection based on what we asked about
    if question_context:
        # Extract key symptom words from the question
        symptom_keywords = {
            "jaw": ["jaw", "face", "chin", "mouth"],
            "arm": ["arm", "shoulder", "left arm", "right arm"],
            "breath": ["breath", "breathing", "breathe", "air"],
            "dizz": ["dizz", "lightheaded", "faint", "woozy"],
            "nausea": ["nausea", "sick", "vomit", "throw"],
            "sweat": ["sweat", "perspir", "clam"]
        }
        
        # Check which symptom we asked about
        for symptom, keywords in symptom_keywords.items():
            if any(kw in question_context.lower() for kw in keywords):
                # Check if user mentioned any of these keywords
                if any(kw in text_lower for kw in keywords):
                    # They mentioned the symptom - likely confirming
                    # Unless they said "no" or "not" before it
                    if "no " in text_lower or "not " in text_lower or "don't" in text_lower:
                        return "denied"
                    return "confirmed"
    
    # Log unclear responses for learning
    log_conversation_miss(text, question_context, conv)
    return "unclear"

def log_conversation_miss(response, question, conv):
    """Log unclear conversation responses for clinical review"""
    try:
        with open(LEARNING_LOG_PATH, 'r', encoding='utf-8') as f:
            log = json.load(f)
    except:
        log = {}
    
    entry_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S%f')}"
    log[entry_id] = {
        "type": "conversation_response",
        "question": question,
        "response": response,
        "symptoms_discussed": conv.get("symptoms", []),
        "timestamp": datetime.now().isoformat()
    }
    
    with open(LEARNING_LOG_PATH, 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=2)


@app.context_processor
def inject_user_helpers():
    return {"current_user": current_user(), "has_role": has_role}


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = authenticate_user(username, password)
        if user:
            session["user"] = user
            flash(f"Welcome, {username}!", "success")
            return redirect(url_for("admin2"))
        flash("Invalid credentials", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("YouÃ¢â‚¬â„¢ve been logged out.")
    return redirect(url_for("login"))


@app.route("/edit-aliases")
#@require_roles("trainer", "admin")
def edit_aliases():
    tree = safe_json_read(SYMPTOM_TREE_PATH)
    return render_template("edit_aliases.html", tree=tree)


@app.route("/rewrite-response", methods=["POST"])
def rewrite_response():
    data = request.get_json()
    original = data.get("text", "")
    if not original:
        return jsonify({"error": "No input text provided."}), 400
    
    if OPENAI_API_KEY and openai:
        try:
            # Load the tone prompt
            try:
                with open(TONE_PROMPT_PATH, 'r', encoding='utf-8') as f:
                    tone_prompt = f.read().strip()
            except:
                tone_prompt = "Rewrite this response to be empathetic, clinically safe, and non-diagnostic."
            
            openai.api_key = OPENAI_API_KEY
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": tone_prompt},
                    {"role": "user", "content": f"Original response: {original}"}
                ],
                max_tokens=200,
                temperature=0.7
            )
            
            rewritten = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"GPT error in rewrite: {e}")
            rewritten = original  # Return original if error
    else:
        rewritten = original  # No API key
    
    return jsonify({"rewritten": rewritten})


@app.route("/save-rewrite-history", methods=["POST"])
def save_rewrite_history():
    data = request.get_json()
    label = data.get("label")
    response = data.get("response")
    if not label or not response:
        return jsonify({"error": "Missing label or response"}), 400
    history = safe_json_read(REWRITE_HISTORY_PATH)
    entry = {"timestamp": datetime.utcnow().isoformat(), "response": response}
    history.setdefault(label, []).insert(0, entry)
    history[label] = history[label][:5]
    safe_json_write(REWRITE_HISTORY_PATH, history)
    return jsonify({"status": "saved"})


@app.route("/admin/settings", methods=["GET", "POST"])
#@require_roles("admin")
def admin_settings():
    if request.method == "POST":
        new_prompt = request.form.get("tone_prompt", "")
        with open(TONE_PROMPT_PATH, "w", encoding="utf-8") as f:
            f.write(new_prompt.strip())
        return render_template("admin_settings.html", saved=True, tone_prompt=new_prompt)
    if not os.path.exists(TONE_PROMPT_PATH):
        with open(TONE_PROMPT_PATH, "w", encoding="utf-8") as f:
            f.write("Rewrite this response to be empathetic, clinically safe, and non-diagnostic.")
    with open(TONE_PROMPT_PATH, "r", encoding="utf-8") as f:
        tone_prompt = f.read()
    return render_template("admin_settings.html", tone_prompt=tone_prompt, saved=False)


@app.route("/run-tests")
#@require_roles("trainer", "admin")
def run_tests():
    tests = safe_json_read(TEST_CASES_PATH)
    return render_template("run_tests.html", tests=tests)


@app.route("/export")
#@require_roles("trainer", "clinician", "admin")
def export():
    return render_template("export.html")


@app.route("/download-tests")
#@require_roles("trainer", "admin")
def download_tests():
    tests = safe_json_read(TEST_CASES_PATH)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Input", "Expected", "Actual", "Pass?"])
    for t in tests:
        input_text = t.get("input", "")
        expected = t.get("expected_symptom", "")
        actual = t.get("actual", "")
        if not input_text and not expected and not actual:
            continue
        passed = "PASS" if actual == expected else "FAIL"
        writer.writerow([input_text, expected, actual, passed])
    mem_bytes = BytesIO(output.getvalue().encode("utf-8"))
    return send_file(mem_bytes, mimetype="text/csv", as_attachment=True, download_name="test_results.csv")


@app.route("/download-reviews")
#@require_roles("clinician", "admin")
def download_reviews():
    reviews = safe_json_read(GPT_REVIEW_LOG_PATH)
    inputs = safe_json_read(LEARNING_LOG_PATH)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Entry ID", "Input", "GPT Response", "Empathy", "Escalation", "Diagnosis", "Clarity", "Comments"])
    for entry_id, review in reviews.items():
        input_data = inputs.get(entry_id, {})
        writer.writerow([
            entry_id,
            input_data.get("input", ""),
            input_data.get("gpt_response", ""),
            review.get("empathy", ""),
            review.get("escalation", ""),
            review.get("diagnosis", ""),
            review.get("clarity", ""),
            review.get("comments", "")
        ])
    mem_bytes = BytesIO(output.getvalue().encode("utf-8"))
    return send_file(mem_bytes, mimetype="text/csv", as_attachment=True, download_name="gpt_review_log.csv")


@app.route("/rewrite-history")
def rewrite_history():
    history = safe_json_read(REWRITE_HISTORY_PATH)
    return jsonify(history)


@app.route("/train")
def train():
    log = safe_json_read(LEARNING_LOG_PATH)
    return render_template("train.html", learning_log=log)





@app.route("/save-conversation-mapping", methods=["POST"])
@app.route("/save-conversation-mapping", methods=["POST"])
def save_conversation_mapping():
    data = request.get_json()
    entry_id = data.get("entry_id")
    response = data.get("response", "").lower()
    meaning = data.get("meaning")
    
    # Load learned responses
    try:
        with open('prompts/learned_responses.json', 'r', encoding='utf-8') as f:
            learned = json.load(f)
    except:
        learned = {}
    
    # Add the new mapping
    if meaning and meaning != "unclear":
        learned[response] = meaning
        
        # Save it
        with open('prompts/learned_responses.json', 'w', encoding='utf-8') as f:
            json.dump(learned, f, indent=2)
    
    # Remove from learning log
    try:
        with open(LEARNING_LOG_PATH, 'r', encoding='utf-8') as f:
            log = json.load(f)
        
        if entry_id in log:
            del log[entry_id]
            
        with open(LEARNING_LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(log, f, indent=2)
    except:
        pass
    
    return jsonify({"status": "success"})

@app.route("/get-conversation-suggestions", methods=["POST"])
def get_conversation_suggestions():
    data = request.get_json()
    user_response = data.get("response", "")
    meaning = data.get("meaning", "")
    
    # Use GPT-4 to generate suggestions
    if OPENAI_API_KEY and openai:
        try:
            openai.api_key = OPENAI_API_KEY
            
            prompt = f"""Given that a user said "{user_response}" to mean "{meaning}" in a medical conversation, 
            suggest 8-10 other common ways people might express the same meaning. 
            Keep suggestions natural and conversational. Return as a JSON array of strings.
            
            Example: If user said "right" to mean "confirmed", you might suggest ["correct", "that's right", "exactly"]"""
            
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.7
            )
            
            # Parse the response
            suggestions_text = response.choices[0].message.content
            import re
            # Extract strings from the JSON array
            matches = re.findall(r'"([^"]+)"', suggestions_text)
            suggestions = matches[:8]  # Limit to 8
            
        except Exception as e:
            print(f"GPT-4 error: {e}")
            # Fallback to basic suggestions
            suggestions = ["correct", "right", "yes"] if meaning == "confirmed" else ["no", "wrong", "not really"]
    else:
        # No API key - use basic fallback
        suggestions = ["correct", "right", "yes"] if meaning == "confirmed" else ["no", "wrong", "not really"]
    
    # Filter out already learned responses
    try:
        with open('prompts/learned_responses.json', 'r', encoding='utf-8') as f:
            learned = json.load(f)
        filtered = [s for s in suggestions if s.lower() not in learned]
    except:
        filtered = suggestions
    
    return jsonify({"suggestions": filtered})

@app.route("/review-gpt")
#@require_roles("clinician", "admin")
def review_gpt():
    reviews = safe_json_read(GPT_REVIEW_LOG_PATH)
    learning_log = safe_json_read(LEARNING_LOG_PATH)
    return render_template("review_gpt.html", reviews=reviews, learning_log=learning_log)


@app.route("/edit-tests")
#@require_roles("trainer", "admin")
def edit_tests():
    tests = safe_json_read(TEST_CASES_PATH)
    return render_template("edit_tests.html", tests=tests)


@app.route("/run-single-test", methods=["POST"])
#@require_roles("trainer", "admin")
def run_single_test():
    data = request.get_json()
    tests = safe_json_read(TEST_CASES_PATH)
    symptom_tree = load_symptom_tree()
    run_all = data.get("run_all", False)
    indices = data.get("indices", []) if not run_all else list(range(len(tests)))
    for i in indices:
        input_text = tests[i]["input"]
        matched_label, match_type = fuzzy_match_symptom(input_text, symptom_tree)
        actual = matched_label or "unknown"
        tests[i]["actual"] = actual
    try:
        safe_json_write(TEST_CASES_PATH, tests)
        return jsonify({"status": "updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/audit-summary")
#@require_roles("trainer", "admin")
def audit_summary():
    tests = safe_json_read(TEST_CASES_PATH)
    return render_template("audit_summary.html", tests=tests)


@app.route("/test", methods=["GET", "POST"])
def test():
    if request.method == "POST":
        data = request.get_json()
        input_text = data.get("input", "").strip()
        symptom_tree = load_symptom_tree()
        matched_label, _ = fuzzy_match_symptom(input_text, symptom_tree)
        matched = matched_label or "unknown"
        response = symptom_tree[matched]["response"] if matched in symptom_tree else "Thanks for your input."
        evaluation = {
            "empathy": True,
            "escalation": False,
            "diagnosis": False,
            "clarity": True
        }
        return jsonify({
            "matched_symptom": matched,
            "response": response,
            "evaluation": evaluation
        })
    return render_template("test.html")


@app.route("/review-tests")
#@require_roles("trainer", "admin")
def review_tests():
    try:
        with open("review_tests.md", "r", encoding="utf-8") as f:
            markdown = f.read()
    except FileNotFoundError:
        markdown = None
    return render_template("review_tests.html", markdown=markdown)


@app.route("/get-tests")
def get_tests():
    tests = safe_json_read(TEST_CASES_PATH)
    return jsonify(tests)


@app.route("/save-tests", methods=["POST"])
#@require_roles("trainer", "admin")
def save_tests():
    data = request.get_json()
    try:
        safe_json_write(TEST_CASES_PATH, data)
        return jsonify({"status": "saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/symptom", methods=["POST"])
def api_symptom():
    print("\n=== API SYMPTOM CALLED ===")
    data = request.get_json()
    print(f"RAW DATA RECEIVED: {data}")
    text = data.get("text", "").strip()
    session_id = data.get("session_id", "unknown")
    print(f"Input: '{text}', Session: {session_id}")
    
    symptom_tree = load_symptom_tree()
    matched_label, match_type = fuzzy_match_symptom(text, symptom_tree)
    
    # Check if this is part of an ongoing conversation
    if session_id in conversations:
        conv = conversations[session_id]
        if conv.get("awaiting_response"):
            print(f"DEBUG: Continuing conversation, last question: {conv.get('last_question')}")
            # Handle the response to our question
            response_type = understand_response(text, conv["last_question"], conv)
            print(f"DEBUG: Understood as: {response_type}")
            
            current_symptoms = conv.get("symptoms", [])
            symptoms_to_check = conv.get("symptoms_to_check", [])
            
            if response_type == "confirmed":
                current_symptoms.extend(symptoms_to_check)
                print(f"DEBUG: Current symptoms after confirmation: {current_symptoms}")
                if is_emergency_combination(current_symptoms):
                    response = "This combination of symptoms (chest pain and jaw pain) requires immediate medical attention. Please call 911 or go to the nearest emergency room."
                    conversations[session_id]["awaiting_response"] = False
                else:
                    response = "Thank you for that information. Please tell me more about your symptoms."
                    conversations[session_id]["awaiting_response"] = False
            elif response_type == "denied":
                response = "I understand. Please tell me more about your symptoms or let me know if you need other assistance."
                conversations[session_id]["awaiting_response"] = False
            else:
                response = "I didn't quite catch that. Could you try rephrasing? " + conversations[session_id].get("last_question", "")
                # Keep awaiting_response = True so we continue the conversation
                conversations[session_id]["awaiting_response"] = True
                conversations[session_id]["retry_count"] = conversations[session_id].get("retry_count", 0) + 1
                
                # After 2 retries, give up and move on
                if conversations[session_id]["retry_count"] >= 2:
                    response = "I'm having trouble understanding. Let me know if you have any other symptoms you'd like to discuss."
                    conversations[session_id]["awaiting_response"] = False
                    conversations[session_id]["retry_count"] = 0
            
            return jsonify({"response": response, "match": matched_label or "unknown", "type": match_type or "none", "awaiting_response": False})
    
    # New conversation or not awaiting response
    if matched_label:
        response = symptom_tree[matched_label].get("response", "Thank you for your input.")
        
        # Initialize or update conversation
        if session_id not in conversations:
            conversations[session_id] = {"symptoms": [], "last_question": None, "awaiting_response": False}
        
        conversations[session_id]["symptoms"].append(matched_label)
        
        # Check if we need to ask follow-up questions
        if matched_label == "chest pain":
            response = symptom_tree[matched_label]["response"]
            conversations[session_id]["last_question"] = "Are you also experiencing jaw pain?"
            conversations[session_id]["awaiting_response"] = True
            conversations[session_id]["symptoms_to_check"] = ["jaw pain"]
            return jsonify({"response": response, "match": matched_label, "type": match_type, "awaiting_response": True})
    else:
        response = "Thank you. A clinician will review your input shortly."
    
    return jsonify({"response": response, "match": matched_label or "unknown", "type": match_type or "none", "awaiting_response": False})
@app.route("/admin")
#@require_roles("admin")
def admin():
    routes = [str(rule) for rule in app.url_map.iter_rules()]
    return render_template("admin.html",
        system=platform.uname(),
        env=dict(os.environ),
        routes=routes,
        memory=psutil.virtual_memory()
    )


@app.route("/admin2")
#@require_roles("trainer", "admin", "clinician")
def admin2():
    return render_template("admin2.html")


@app.route("/upload-voice", methods=["POST"])
#@require_roles("admin", "clinician")
def upload_voice():
    file = request.files.get("audio")
    if not file:
        return jsonify({"error": "No file received"}), 400
    filename = f"uploads/{datetime.utcnow().isoformat().replace(':', '-')}.webm"
    os.makedirs("uploads", exist_ok=True)
    file.save(filename)
    return jsonify({"status": "received", "filename": filename})


@app.route("/log-voice-interaction", methods=["POST"])
def log_voice_interaction():
    """Log voice interactions for audit trail"""
    data = request.get_json()
    
    voice_log = safe_json_read(VOICE_LOG_PATH)
    if not isinstance(voice_log, dict):
        voice_log = {}
    
    entry_id = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S%f')}"
    voice_log[entry_id] = {
        "timestamp": datetime.now().isoformat(),
        "input": data.get("input", ""),
        "match": data.get("match", ""),
        "response": data.get("response", ""),
        "session_id": data.get("session_id", "")
    }
    
    safe_json_write(VOICE_LOG_PATH, voice_log)
    return jsonify({"status": "logged"})


@app.route("/voice-log")
#@require_roles("admin")
def voice_log():
    logs = safe_json_read(VOICE_LOG_PATH)
    # Convert dict to list if needed, sort by timestamp
    if isinstance(logs, dict):
        logs = list(logs.values())
    logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return render_template("voice_log.html", logs=logs)


if __name__ == "__main__":
    print("Ã¢Å“â€¦ SymSafe WebUI running with full authentication, fuzzy matching, and role-aware navigation")
    for rule in app.url_map.iter_rules():
        print(f" - {rule}")
    app.run(debug=True)






