import webbrowser
import time
import os
import sys

print("🔍 SymSafe Voice Input Checker\n")

# 1. Check if running on localhost
print("1️⃣ Checking URL...")
if len(sys.argv) > 1 and "127.0.0.1" in sys.argv[1]:
    print("❌ You're using 127.0.0.1 - Voice input won't work!")
    print("✅ FIX: Use http://localhost:5000 instead\n")
else:
    print("✅ Good - Use http://localhost:5000\n")

# 2. Create a test page (without emojis to avoid encoding issues)
test_html = """<!DOCTYPE html>
<html>
<head>
    <title>Voice Test</title>
    <style>
        body { font-family: Arial; padding: 50px; text-align: center; }
        button { font-size: 20px; padding: 15px 30px; margin: 10px; cursor: pointer; }
        #status { font-size: 18px; margin: 20px; padding: 20px; background: #f0f0f0; }
        .success { color: green; font-weight: bold; }
        .error { color: red; font-weight: bold; }
    </style>
</head>
<body>
    <h1>SymSafe Voice Test</h1>
    <button onclick="testVoice()">Click to Test Microphone</button>
    <button onclick="checkBrowser()">Check Browser Support</button>
    <div id="status">Status will appear here...</div>
    
    <script>
    function checkBrowser() {
        let msg = "";
        if ('webkitSpeechRecognition' in window) {
            msg = "SUCCESS: Your browser supports voice input!";
        } else if ('SpeechRecognition' in window) {
            msg = "SUCCESS: Your browser supports voice input!";
        } else {
            msg = "ERROR: Your browser doesn't support voice input. Use Chrome or Edge.";
        }
        document.getElementById('status').innerHTML = msg;
    }
    
    function testVoice() {
        const status = document.getElementById('status');
        
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            status.innerHTML = '<span class="error">ERROR: Speech recognition not supported in this browser!</span>';
            return;
        }
        
        const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        
        recognition.onstart = () => {
            status.innerHTML = 'LISTENING... Say something!';
        };
        
        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            status.innerHTML = '<span class="success">SUCCESS! You said: "' + transcript + '"</span>';
        };
        
        recognition.onerror = (event) => {
            let errorMsg = '<span class="error">ERROR: ';
            switch(event.error) {
                case 'not-allowed':
                    errorMsg += 'Microphone permission denied. Please allow microphone access and reload the page.</span>';
                    break;
                case 'no-speech':
                    errorMsg += 'No speech detected. Try again!</span>';
                    break;
                default:
                    errorMsg += event.error + '</span>';
            }
            status.innerHTML = errorMsg;
        };
        
        try {
            recognition.start();
        } catch(e) {
            status.innerHTML = '<span class="error">ERROR: Failed to start: ' + e.message + '</span>';
        }
    }
    </script>
</body>
</html>"""

# Save test file with UTF-8 encoding
with open("voice_test.html", "w", encoding="utf-8") as f:
    f.write(test_html)

print("2️⃣ Created voice_test.html")

# 3. Open in browser
print("3️⃣ Opening test page in your browser...")
webbrowser.open(f"file:///{os.path.abspath('voice_test.html')}")

print("\n📋 INSTRUCTIONS:")
print("1. Click 'Check Browser Support' first")
print("2. Then click 'Click to Test Microphone'")
print("3. Allow microphone access if prompted")
print("4. Say something clearly")
print("\n🔧 COMMON FIXES:")
print("- Use Chrome or Edge browser")
print("- Make sure you're on http://localhost:5000 (not 127.0.0.1)")
print("- Allow microphone permissions when prompted")
print("\n✅ If the test works, your voice input should work in SymSafe too!")