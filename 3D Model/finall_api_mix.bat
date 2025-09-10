@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul
title Full Pipeline Controller (LOCAL) — download -> generate -> assemble(to merge\<base>.fbx) -> upload -> clear (loop)

REM ====== 可調參數 ======
set "CONDA_ENV=hunyuan3d"
set "PROJECT_DIR=C:\Users\B310\Hunyuan3D-2"

REM 本機生成 API
set "GEN_PORT=8080"
set "MODEL_PATH=C:\Users\B310\.cache\hy3dgen\tencent\Hunyuan3D-2"
set "DIT_NAME=hunyuan3d-dit-v2-mini-turbo"
set "VAE_NAME=hunyuan3d-vae-v2-mini"
set "TEX_PATH=C:\Users\B310\.cache\hy3dgen\tencent\Hunyuan3D-2\hunyuan3d-paint-v2-0-turbo"

REM 目錄
set "IMAGES=%PROJECT_DIR%\demo\images"
set "OUTPUT=%PROJECT_DIR%\demo\output"
set "CLOUD=%PROJECT_DIR%\cloud_save"
set "MERGE=%CLOUD%\merge"

echo [STEP] 啟動/切換 Conda 環境：%CONDA_ENV%
call conda activate "%CONDA_ENV%" || (
  call "%UserProfile%\anaconda3\Scripts\activate.bat" "%CONDA_ENV%" || (
    echo [FATAL] 無法啟動 conda 環境。 & pause & exit /b 1
  )
)

echo [STEP] 切到專案：%PROJECT_DIR%
cd /d "%PROJECT_DIR%" || (echo [FATAL] 找不到專案資料夾 & pause & exit /b 1)

if not exist "%IMAGES%" mkdir "%IMAGES%"
if not exist "%OUTPUT%" mkdir "%OUTPUT%"
if not exist "%MERGE%"  mkdir "%MERGE%"

REM ====== 啟動生成 API（背景）並等待 /health=200（PowerShell 版本） ======
powershell -NoProfile -Command ^
  "$ok=$false; try{$r=Invoke-WebRequest -UseBasicParsing http://127.0.0.1:%GEN_PORT%/health -TimeoutSec 2; if($r.StatusCode -eq 200){$ok=$true}}catch{}; if(-not $ok){Start-Process -FilePath 'cmd.exe' -ArgumentList '/c','python','api_server.py','--host','0.0.0.0','--port','%GEN_PORT%','--model_path','%MODEL_PATH%','--dit_model_name','%DIT_NAME%','--vae_model_name','%VAE_NAME%','--enable_tex','--tex_model_path','%TEX_PATH%' -WorkingDirectory '%PROJECT_DIR%' -WindowStyle Hidden}"

echo [STEP] 等待 生成 API /health=200 ...
set /a __t=0
:wait_gen_ps
powershell -NoProfile -Command ^
  "try{$r=Invoke-WebRequest -UseBasicParsing http://127.0.0.1:%GEN_PORT%/health -TimeoutSec 2; if($r.StatusCode -eq 200){exit 0}else{exit 1}}catch{exit 1}"
if %errorlevel%==0 (
  echo [OK] 生成 API 就緒。
) else (
  set /a __t+=2
  if %__t% GEQ 120 (
    echo [ERROR] 等待本機服務逾時；請檢查模型路徑與環境。
    pause
    exit /b 1
  )
  timeout /t 2 >nul
  goto :wait_gen_ps
)

echo.
echo ==== 常駐開始（Ctrl+C 可中止） ====
:LOOP
REM ── 0) 從伺服器拉圖到 demo\images ───────────────────────────────
echo [STEP] download_images.py 下載遠端圖片到 %IMAGES%
pushd "%CLOUD%"
python download_images.py
popd

REM 檢查是否有圖片
set "HAS_IMG="
for %%F in ("%IMAGES%\*.png" "%IMAGES%\*.jpg" "%IMAGES%\*.jpeg" "%IMAGES%\*.webp" "%IMAGES%\*.bmp") do (
  if exist "%%~F" set HAS_IMG=1
)
if not defined HAS_IMG (
  echo [INFO] 沒有待處理圖片，10 秒後再檢查...
  timeout /t 10 >nul
  goto :LOOP
)

REM ── 0.1) 從檔名抓 base（_head/_body 去尾；否則取第一個底線前的前綴） ───────
set "BASE="

REM 先處理有 _head / _body 的情況
for %%F in ("%IMAGES%\*_head.*") do (
  set "BASE=%%~nF"
  set "BASE=!BASE:_head=!"
  goto :GOTBASE
)
for %%F in ("%IMAGES%\*_body.*") do (
  set "BASE=%%~nF"
  set "BASE=!BASE:_body=!"
  goto :GOTBASE
)

REM 一般情況：取第一個 "_" 之前的部分；若無 "_" 則用整個檔名
for %%F in ("%IMAGES%\*.*") do (
  set "BASE=%%~nF"
  for /f "tokens=1 delims=_" %%A in ("!BASE!") do set "BASE=%%A"
  goto :GOTBASE
)

:GOTBASE
if not defined BASE set "BASE=case"
echo [INFO] 本輪 base = %BASE%

REM ── 1) 產生 OBJ + 材質 ──────────────────────────────────────────
echo [STEP] 執行 api_run_text.py 產生 OBJ+材質...
python api_run_text.py
set RET=%ERRORLEVEL%
if not "%RET%"=="0" echo [WARN] api_run_text.py 回傳碼=%RET%（可能仍有部分輸出）

REM ── 2) 在 demo\output 找出「最新且同時含 001/002.obj」的資料夾 ──────────
set "SCENE_DIR="
for /f "delims=" %%D in ('dir "%OUTPUT%" /b /ad ^| findstr /r "^[0-9][0-9]*$" ^| sort /R') do (
  if exist "%OUTPUT%\%%D\001.obj" if exist "%OUTPUT%\%%D\002.obj" ( set "SCENE_DIR=%OUTPUT%\%%D" & goto :found_scene )
)
for /f "delims=" %%D in ('dir "%OUTPUT%" /b /ad /o:-d') do (
  if exist "%OUTPUT%\%%D\001.obj" if exist "%OUTPUT%\%%D\002.obj" ( set "SCENE_DIR=%OUTPUT%\%%D" & goto :found_scene )
)
:found_scene
if not defined SCENE_DIR (
  echo [FATAL] 找不到 001/002.obj；請確認 demo\images 至少有兩張圖。 
  goto :CLEAN_AND_WAIT
)
echo [INFO] 最新場景：%SCENE_DIR%
echo        HEAD=%SCENE_DIR%\001.obj
echo        BODY=%SCENE_DIR%\002.obj

REM ── 3) 呼叫你的組裝腳本（會自動複製到 merge\<base>.fbx） ───────────────
echo [STEP] run_assemble_latest.bat "%BASE%" "%MERGE%"
pushd "%PROJECT_DIR%\jobs"
call run_assemble_latest.bat "%BASE%" "%MERGE%"
popd

REM ── 4) 上傳到伺服器（切到 cloud_save 再執行，確保讀對 config.json） ───────
echo [STEP] upload_fbx_temp.py 上傳 %BASE%.fbx
pushd "%CLOUD%"
python upload_fbx_temp.py
set RET=%ERRORLEVEL%
popd
if not "%RET%"=="0" (
  echo [ERROR] 上傳腳本回傳非 0，請檢查上面日誌。
  pause
)

REM ── 5) 清空 images（單人模式，避免混檔） ──────────────────────────
:CLEAN_AND_WAIT
echo [STEP] 清空 %IMAGES%
del /q "%IMAGES%\*" 2>nul
for /d %%D in ("%IMAGES%\*") do rd /s /q "%%D" 2>nul

echo [INFO] 本輪完成；10 秒後重新檢查是否有新圖片...
timeout /t 10 >nul
goto :LOOP


