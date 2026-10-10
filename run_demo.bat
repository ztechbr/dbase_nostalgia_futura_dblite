@echo off
cd /d "%~dp0"
python examples\setup.py --cwd demo_data
if errorlevel 1 goto fim
python main.py --cwd demo_data --cmd negocios.prg --plain
:fim
pause
