@echo off
chcp 65001 >nul 2>&1
title Acik Analiz - Motor (bu pencereyi KAPATMAYIN)
setlocal
set "DIR=%USERPROFILE%\.acikanaliz"
if not exist "%DIR%" mkdir "%DIR%"
if not exist "%DIR%\server" mkdir "%DIR%\server"
set "BASE=https://raw.githubusercontent.com/seoncu/acik-analiz/main"
set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"

echo Hazirlaniyor... Ilk acilis birkac dakika surebilir. Bu pencereyi kapatmayin.

:: 1) uv (yoksa kur)
where uv >nul 2>&1
if %errorlevel% neq 0 (
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
)
where uv >nul 2>&1
if %errorlevel% neq 0 (
  powershell -NoProfile -c "Add-Type -AssemblyName System.Windows.Forms;[void][System.Windows.Forms.MessageBox]::Show('Kurulum araci (uv) yuklenemedi. Internet baglantinizi kontrol edin.','Acik Analiz')"
  exit /b 1
)

:: 2) En guncel dosyalari cek
echo Guncel surum indiriliyor...
powershell -NoProfile -c "$b='%BASE%';$d='%DIR%';foreach($f in 'server/engine.py','server/api-bridge.js','server/requirements.txt','index.html'){$n=Split-Path $f -Leaf; try{Invoke-WebRequest -UseBasicParsing \"$b/$f\" -OutFile \"$d\$n\"}catch{}}; Copy-Item \"$d\api-bridge.js\" \"$d\server\api-bridge.js\" -Force -ErrorAction SilentlyContinue"
if not exist "%DIR%\engine.py" (
  powershell -NoProfile -c "Add-Type -AssemblyName System.Windows.Forms;[void][System.Windows.Forms.MessageBox]::Show('Motor dosyasi indirilemedi. Internet baglantinizi kontrol edin.','Acik Analiz')"
  exit /b 1
)

:: 3) Tarayiciyi gecikmeli ac + motoru baslat
cd /d "%DIR%"
start "" /b powershell -NoProfile -c "Start-Sleep 9; Start-Process 'http://127.0.0.1:8765'"
echo Motor baslatiliyor (port 8765)...
uv run --python 3.12 --with-requirements "%DIR%\requirements.txt" "%DIR%\engine.py"
echo.
echo Motor durdu. Bu pencereyi kapatabilirsiniz.
pause >nul
