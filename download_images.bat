@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
if not exist ".venv\Scripts\python.exe" (
  echo 還沒安裝環境：請先雙擊 setup.bat
  pause
  exit /b 1
)
title art-mcp 下載作品圖片
echo 下載作品圖片中（20 張，大約 1～3 分鐘）...
".venv\Scripts\python.exe" download_images.py
echo.
echo 這次的結果也存在 logs\download_images.txt
pause
