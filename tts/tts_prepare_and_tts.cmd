@echo off
setlocal
chcp 65001 >nul

rem ===== 固定參數 =====
set "TTS_BASE=http://127.0.0.1:5009"
set "REF_WAV=D:\tts\voices\default.wav"
set "PREP_JSON=%TEMP%\prepare_out.json"

if not exist "%REF_WAV%" (
  echo [ERR] 參考音不存在：%REF_WAV%
  exit /b 1
)

echo [PREP] POST /prepare ...
curl -s -X POST "%TTS_BASE%/prepare" ^
  -F "wav=@%REF_WAV%" > "%PREP_JSON%"

type "%PREP_JSON%"
echo.

rem === 用 PowerShell 直接以退出碼回報結果（避免亂碼與字串解析） ===
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$j = Get-Content '%PREP_JSON%' -Raw | ConvertFrom-Json; if ($j.ok) { exit 0 } else { exit 1 }"

if errorlevel 1 (
  echo [PREP] FAIL
  exit /b 1
) else (
  echo [PREP] OK
  exit /b 0
)
