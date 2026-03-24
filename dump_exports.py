import requests

BASE = "http://127.0.0.1:5000"

def check_csv(path):
    print(f"\n🔍 Checking {path}")
    try:
        r = requests.get(BASE + path)
        print(f"Status Code: {r.status_code}")
        print(f"Content Length: {len(r.content)} bytes")
        content = r.content.decode("utf-8").strip()
        print("---- CSV Content ----")
        print(content if content else "(empty)")
    except Exception as e:
        print(f"❌ Error fetching {path}: {e}")

check_csv("/download-tests")
check_csv("/download-reviews")
