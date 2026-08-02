@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "SEVENZIP=C:\Program Files\NVIDIA Corporation\NVIDIA App\7z.exe"
if not exist "%SEVENZIP%" set "SEVENZIP=C:\Program Files\7-Zip\7z.exe"
if not exist "%SEVENZIP%" (
  echo 未找到 7z.exe，请先安装 7-Zip。
  pause
  exit /b 1
)

echo 正在打包，请稍候...
"%SEVENZIP%" a -tzip -mx3 "%~dp0portable-shop.zip" "%~dp0*" ^
  -xr!db.sqlite3 ^
  -xr!db.sqlite3.legacy ^
  -xr!media ^
  -xr!server.log ^
  -xr!server.err.log ^
  -xr!__pycache__ ^
  -xr!*.pyc ^
  -xr!portable-shop.zip ^
  -xr!.git

echo.
echo 打包完成：portable-shop.zip
pause
