@echo off
echo 🔪 Killing any existing symsafe_webui.py processes...
for /f "tokens=2 delims=," %%a in ('tasklist /fi "imagename eq python.exe" /v /fo csv ^| findstr /i "symsafe_webui.py"') do taskkill /PID %%a /F >nul 2>&1

echo 🚀 Starting symsafe_webui.py...
python symsafe_webui.py
pause
