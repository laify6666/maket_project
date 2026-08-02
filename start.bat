@echo off
call "%~dp0manage.bat" migrate
call "%~dp0manage.bat" seed_demo
call "%~dp0manage.bat" runserver 127.0.0.1:8000
