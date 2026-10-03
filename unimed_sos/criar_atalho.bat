@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0criar_atalho.ps1"
if errorlevel 1 goto erro
echo.
echo Atalho criado na area de trabalho e nesta pasta.
goto fim
:erro
echo.
echo Nao foi possivel criar o atalho. Leia a mensagem acima.
:fim
echo.
pause
