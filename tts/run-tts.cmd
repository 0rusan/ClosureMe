@echo off
setlocal

cd /d %~dp0

rem 相對路徑，換哪個磁碟/資料夾都能跑
set "BASE=%~dp0"
set "PORT=5009"
set "OUT_WAV=%BASE%out\output.wav"
set "REF_WAV=%BASE%voices\huei_aunt.aac"
set "AUDIO_URL_BASE=http://122.100.76.28:80/audio"  rem ← 對外可連的網址（請修改）
set "WARMUP_ENABLE=1"
set "WARMUP_TEXT=嗨"

rem 可攜版 ffmpeg（如果夾帶了 ffmpeg\bin）
set "PATH=%BASE%ffmpeg\bin;%PATH%"

if not exist "%BASE%out" mkdir "%BASE%out"

call "%BASE%venv\Scripts\activate.bat"

waitress-serve --host=0.0.0.0 --port=%PORT% tts_server:app
pause