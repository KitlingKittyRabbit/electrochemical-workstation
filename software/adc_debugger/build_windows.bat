@echo off
setlocal

cd /d "%~dp0"
py -3 -m pip install -r requirements.txt -r build-requirements.txt
py -3 -m PyInstaller --clean --noconfirm ADC-Debugger.spec
echo Built: %CD%\dist\ADC-Debugger\ADC-Debugger.exe
pause
