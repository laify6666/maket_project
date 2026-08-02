@echo off
set "PYTHONPATH=%~dp0.deps"
set "PYTHONDONTWRITEBYTECODE=1"
"%~dp0runtime\python.exe" "%~dp0manage.py" %*
