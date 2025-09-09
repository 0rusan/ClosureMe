@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM %1 = DEST_BASE  (file name prefix, e.g. kd)
REM %2 = DEST_DIR   (dest folder, e.g. C:\Users\B310\Hunyuan3D-2\cloud_save\merge)
set "DEST_BASE=%~1"
set "DEST_DIR=%~2"

REM ===== 基本路徑 =====
set "BLENDER=C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
set "SCRIPT=C:\Users\B310\Hunyuan3D-2\jobs\assemble_worker.py"
set "OUTPUT_BASE=C:\Users\B310\Hunyuan3D-2\demo\output"

REM ===== 檢查檔案 =====
if not exist "%BLENDER%"      ( echo [錯誤] 找不到 Blender：%BLENDER% & exit /b 1 )
if not exist "%SCRIPT%"       ( echo [錯誤] 找不到腳本：%SCRIPT%  & exit /b 1 )
if not exist "%OUTPUT_BASE%"  ( echo [錯誤] 找不到 output 資料夾：%OUTPUT_BASE% & exit /b 1 )

REM ===== 執行 Blender 組裝（--auto_base 自動挑最新資料夾）=====
set "LOG=%TEMP%\assemble_%RANDOM%.log"
echo ---------------------------------------
echo 正在執行 Blender 自動組裝...
echo 日誌：%LOG%
echo ---------------------------------------
"%BLENDER%" -b -P "%SCRIPT%" -- --auto_base "%OUTPUT_BASE%" --export_assembled --print_json > "%LOG%" 2>&1

REM ===== 顯示 LOG 尾段（最近 40 行）=====
echo.
echo ---- Blender Log 尾段 (最近 40 行) ----
powershell -NoProfile -Command "Get-Content -Tail 40 -Path '%LOG%'" || echo [WARN] 顯示 log 失敗
echo ---------------------------------------

REM ===== 從 LOG 擷取 JSON；若有帶參數則複製為 DEST_DIR\DEST_BASE.fbx =====
powershell -NoProfile -Command ^
  "$t = Get-Content -Raw '%LOG%';" ^
  "$re = New-Object System.Text.RegularExpressions.Regex('===ASSEMBLE_JSON_BEGIN===(.*)===ASSEMBLE_JSON_END===',[System.Text.RegularExpressions.RegexOptions]::Singleline);" ^
  "$m = $re.Match($t);" ^
  "if(-not $m.Success){ Write-Host '[失敗] 未捕捉到 ASSEMBLE_JSON（可能 Blender 先報錯）'; exit 2 }" ^
  "$json = $m.Groups[1].Value | ConvertFrom-Json;" ^
  "if(-not $json.mixamo_path){ Write-Host '[失敗] 組裝腳本沒有回傳 mixamo_path'; exit 3 }" ^
  "Write-Host ('[完成] 已輸出 FBX 檔案：' + $json.mixamo_path);" ^
  "$destBase = $env:DEST_BASE; $destDir = $env:DEST_DIR;" ^
  "if([string]::IsNullOrWhiteSpace($destBase) -or [string]::IsNullOrWhiteSpace($destDir)){ exit 0 }" ^
  "if(-not (Test-Path $destDir)){ New-Item -ItemType Directory -Force -Path $destDir | Out-Null }" ^
  "$dest = Join-Path $destDir ($destBase + '.fbx');" ^
  "Copy-Item -LiteralPath $json.mixamo_path -Destination $dest -Force;" ^
  "Write-Host ('[COPY] 已複製到：' + $dest);" ^
  "exit 0"

endlocal
