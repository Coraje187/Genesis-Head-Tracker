@echo off
cd /d "%~dp0"
uv run python headtrack.py %*
pause
