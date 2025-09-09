@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ====== 路徑與參數 ======
set "PROJECT_ROOT=D:\chatbot"
set "INPUT_DIR=D:\chatbot\notanalysis"
set "SHARED_DIR=D:\chatbot\shared_memories"
set "SCRIPT=%PROJECT_ROOT%\shared_memory_generator.py"
set "CHAT_URL=http://127.0.0.1:5000/chat"
set "MODEL_NAME=gpt-4.1-nano"
set "INDEX_FILE=D:\chatbot\rightnow-name\index.txt"

REM ====== 啟動 venv ======
if not exist "%PROJECT_ROOT%\venv\Scripts\activate.bat" exit /b 1
call "%PROJECT_ROOT%\venv\Scripts\activate.bat" || exit /b 1

REM ====== 基本檢查 ======
if not exist "%SCRIPT%" exit /b 3
if not exist "%INDEX_FILE%" exit /b 8

REM ====== 從 index.txt 取得第一個非空白人名（自動 Trim） ======
set "ROLE_NAME="
for /f "delims=" %%A in ('powershell -NoProfile -ExecutionPolicy Bypass -Command " $p='D:\chatbot\rightnow-name\index.txt'; $line = Get-Content -LiteralPath $p -Encoding UTF8 | Where-Object { $_ -and $_.Trim().Length -gt 0 } | Select-Object -First 1; if ($null -ne $line) { $line.Trim() } "') do set "ROLE_NAME=%%A"
if not defined ROLE_NAME exit /b 9

REM ====== 以人名作為基底 ======
set "BASENAME=%ROLE_NAME%"

REM ---- 先檢查 shared_memories 是否已有任何匹配檔；有就直接 /use ----
for /f "delims=" %%g in ('dir /b /a-d "%SHARED_DIR%\*%BASENAME%*.txt" 2^>nul') do (
  goto :switch
)

REM ====== 準備來源與臨時檔 ======
set "SRC_FILE=%INPUT_DIR%\%BASENAME%.txt"
set "TMP_IN=%PROJECT_ROOT%\%BASENAME%.txt"

REM ====== 檢查來源是否存在（只有在沒現成 shared 才需要） ======
if not exist "%SRC_FILE%" exit /b 10

REM ====== 複製到專案根目錄（若不同檔） ======
if /I not "%SRC_FILE%"=="%TMP_IN%" (
  copy /y "%SRC_FILE%" "%TMP_IN%" >nul
  if errorlevel 1 powershell -NoProfile -ExecutionPolicy Bypass -Command "Copy-Item -LiteralPath '%SRC_FILE%' -Destination '%TMP_IN%' -Force" 2>nul
  if not exist "%TMP_IN%" exit /b 7
)

REM ====== 執行 Python 分析 ======
set "PYTHONUNBUFFERED=1"
python -u "%SCRIPT%" --input "%TMP_IN%" --model %MODEL_NAME%
set "PYERR=%ERRORLEVEL%"

REM ====== 清除臨時檔 ======
if /I not "%SRC_FILE%"=="%TMP_IN%" del /q "%TMP_IN%" >nul 2>&1

if not "%PYERR%"=="0" exit /b %PYERR%

:switch
REM ====== 送出 /use {人名} ======
set "TMPJSON=%TEMP%\use_role_%RANDOM%.json"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$obj = @{ message = '/use %BASENAME%' } | ConvertTo-Json -Compress; Set-Content -LiteralPath '%TMPJSON%' -Value $obj -Encoding UTF8"
curl -s -X POST %CHAT_URL% -H "Content-Type: application/json" --data-binary "@%TMPJSON%"
del /q "%TMPJSON%" >nul 2>&1

exit /b 0

