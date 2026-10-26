@echo off
chcp 65001 >nul
REM 把 20 件臺灣民間藝術（nmth-*、tcmb-*）複製到小組 repo 的 kb\，不碰小組原本的 3 幅名畫
set SRC=%~dp0data
set DST=C:\dev\art-rag\kb
set LOG=%~dp0logs\copy_to_group_repo.txt
if not exist "%~dp0logs" mkdir "%~dp0logs"

if not exist "%DST%\artworks" (
  echo ✘ 找不到 %DST%\artworks，小組 repo 的位置不對，請告訴教練
  > "%LOG%" echo ERROR: %DST%\artworks not found
  pause
  exit /b 1
)

echo 【1】複製 JSON（只複製 nmth-* 和 tcmb-*）
copy /Y "%SRC%\artworks\nmth-*.json" "%DST%\artworks\" >nul
copy /Y "%SRC%\artworks\tcmb-*.json" "%DST%\artworks\" >nul
echo 【2】複製圖片
copy /Y "%SRC%\images\nmth-*.jpg" "%DST%\images\" >nul
copy /Y "%SRC%\images\tcmb-*.jpg" "%DST%\images\" >nul

for /f %%c in ('dir /b "%DST%\artworks\nmth-*.json" "%DST%\artworks\tcmb-*.json" ^| find /c /v ""') do set J=%%c
for /f %%c in ('dir /b "%DST%\images\nmth-*.jpg" "%DST%\images\tcmb-*.jpg" ^| find /c /v ""') do set I=%%c

echo.
echo 結果：JSON %J% 個、圖片 %I% 張（應該都是 20）
> "%LOG%" echo JSON=%J%
>> "%LOG%" echo images=%I%
>> "%LOG%" echo time=%date% %time%
echo 結果已存到 logs\copy_to_group_repo.txt，跟教練說一聲就好
pause
