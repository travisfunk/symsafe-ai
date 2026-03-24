import requests
import json
import os
import shutil
import time
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "http://127.0.0.1:5000"

TEST_LABEL = "test_label_validation"
REWRITE_HISTORY_PATH = "rewrite_history.json"
TEST_CASES_PATH = "prompts/test_cases.json"
DOWNLOAD_PATHS = ["/download-tests", "/download-reviews"]

PASS = []
FAIL = []

def log_pass(msg): PASS.append(msg); print(f"✅ {msg}")
def log_fail(msg): FAIL.append(msg); print(f"❌ {msg}")

def check_get(path, expect_text=None, max_time=1.0):
    try:
        start = time.time()
        r = requests.get(BASE_URL + path)
        elapsed = time.time() - start
        if r.status_code != 200:
            log_fail(f"GET {path} failed (status {r.status_code})")
            return None
        if elapsed > max_time:
            log_fail(f"GET {path} slow ({elapsed:.2f}s)")
        if expect_text and expect_text not in r.text:
            log_fail(f"GET {path} missing expected content")
        else:
            log_pass(f"GET {path}")
        return r.text
    except Exception as e:
        log_fail(f"GET {path} error: {e}")
        return None

def check_post(path, payload):
    try:
        r = requests.post(BASE_URL + path, json=payload)
        if r.status_code == 200:
            log_pass(f"POST {path}")
            return r.json()
        else:
            log_fail(f"POST {path} failed (status {r.status_code})")
            return None
    except Exception as e:
        log_fail(f"POST {path} error: {e}")
        return None

def backup_file(path):
    if os.path.exists(path):
        shutil.copy(path, path + ".bak")

def restore_file(path):
    if os.path.exists(path + ".bak"):
        shutil.move(path + ".bak", path)

def validate_rewrite_history():
    try:
        with open(REWRITE_HISTORY_PATH, "r", encoding="utf-8") as f:
            history = json.load(f)
        if TEST_LABEL in history and isinstance(history[TEST_LABEL], list):
            log_pass("Rewrite history saved and retrievable")
        else:
            log_fail("Rewrite history entry missing")
    except Exception as e:
        log_fail(f"Rewrite history check failed: {e}")

def validate_test_case_persistence():
    try:
        with open(TEST_CASES_PATH, "r", encoding="utf-8") as f:
            tests = json.load(f)
        if any(t["input"] == "validation test input" for t in tests):
            log_pass("Test case saved successfully")
        else:
            log_fail("Test case did not persist correctly")
    except Exception as e:
        log_fail(f"Test case readback failed: {e}")

def validate_downloads():
    for path in DOWNLOAD_PATHS:
        try:
            r = requests.get(BASE_URL + path)
            if r.status_code == 200 and len(r.content) > 50:
                log_pass(f"{path} downloaded")
            else:
                log_fail(f"{path} download too small or failed")
        except Exception as e:
            log_fail(f"{path} download error: {e}")

def scan_html_for_errors(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text().lower()
    if any(x in text for x in ["exception", "traceback", "error loading"]):
        log_fail("HTML contains error text")
    else:
        log_pass("HTML clean of visible error text")

def main():
    print("🔍 Running SymSafe AI Full Validator...\n")

    # --- Route & HTML content checks ---
    pages = {
        "/": "SymSafe AI",
        "/edit-aliases": "Edit Aliases",
        "/train": "Review Unknown Inputs",
        "/review-gpt": "Review GPT",
        "/edit-tests": "Edit Test Cases",
        "/run-tests": "Run Test Cases",
        "/audit-summary": "Audit",
        "/export": "Export",
        "/review-tests": "QA Test Results",
        "/test": "SymSafe AI – Triage Tester",
        "/login": "Admin Login",
        "/admin": "System Info",
        "/admin2": "Admin Tool Hub"
    }
    for path, text in pages.items():
        html = check_get(path, expect_text=text)
        if html:
            scan_html_for_errors(html)

    # --- API tests ---
    check_post("/api/symptom", {"text": "I have a headache"})
    check_post("/rewrite-response", {"text": "Test rewrite please"})
    check_post("/save-rewrite-history", {
        "label": TEST_LABEL,
        "response": f"Rewritten at {datetime.utcnow().isoformat()}"
    })

    # --- Test case save + read ---
    backup_file(TEST_CASES_PATH)
    test_payload = [{"input": "validation test input", "expected_symptom": "test", "actual": ""}]
    check_post("/save-tests", test_payload)
    r = requests.get(BASE_URL + "/get-tests")
    if r.status_code == 200 and isinstance(r.json(), list):
        log_pass("/get-tests returned list")
    else:
        log_fail("/get-tests failed or returned wrong format")

    validate_test_case_persistence()

    # --- Run single test ---
    check_post("/run-single-test", {"run_all": True})

    # --- Rewrite history check ---
    validate_rewrite_history()

    # --- Export download check ---
    validate_downloads()

    # --- Cleanup ---
    restore_file(TEST_CASES_PATH)

    print("\n📋 Summary:")
    for msg in PASS: print(f"✅ {msg}")
    for msg in FAIL: print(f"❌ {msg}")

    print(f"\n✅ Passed: {len(PASS)}")
    print(f"❌ Failed: {len(FAIL)}")

    if FAIL:
        exit(1)
    else:
        print("\n🎉 All systems green. SymSafe is fully operational.")

if __name__ == "__main__":
    main()
