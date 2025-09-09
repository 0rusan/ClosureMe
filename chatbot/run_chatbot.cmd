@echo off
setlocal
cd /d %~dp0

echo ================================
echo   啟動 Chat API Server ...
echo ================================

:: 啟用虛擬環境 (假設你已經有 venv)
if exist venv (
  call venv\Scripts\activate
) else (
  echo [INFO] 找不到 venv，請先建立虛擬環境並安裝需求套件
  pause
  exit /b
)

:: 安裝缺少的套件
pip install --quiet flask openai faiss-cpu

:: 啟動 chatbot_API_server.py
python chatbot_API_server.py

pause
