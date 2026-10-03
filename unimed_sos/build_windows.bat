@echo off
setlocal
cd /d "%~dp0"
set LOG=build_log.txt

echo Inicio: %date% %time% > %LOG%
set PY=
where py >nul 2>&1 && set PY=py -3
if not defined PY where python >nul 2>&1 && set PY=python
if not defined PY goto semPython
%PY% --version >nul 2>&1 || goto semPython

echo Python encontrado:
%PY% --version
%PY% --version >> %LOG% 2>&1

echo [1/3] Criando ambiente...
%PY% -m venv .venv >> %LOG% 2>&1 || goto erro
call .venv\Scripts\activate.bat
echo [2/3] Instalando bibliotecas...
python -m pip install --upgrade pip >> %LOG% 2>&1
python -m pip install -r requirements_app.txt >> %LOG% 2>&1 || goto erro
echo [3/3] Gerando o executavel unico (uma unica instancia/arquivo)...
pyinstaller --noconfirm --clean --windowed --onefile --icon "icone.ico" --name "ControleTreinamentosSOS" --add-data "static;static" --add-data "seed.json;." --collect-submodules uvicorn app.py >> %LOG% 2>&1 || goto erro

echo.
echo PRONTO!
echo Executavel unico: dist\ControleTreinamentosSOS.exe
goto fim

:semPython
echo.
echo PYTHON NAO ENCONTRADO.
echo Instale o Python 3.12+ e marque a opcao "Add python.exe to PATH".
goto fim

:erro
echo.
echo ERRO. Os detalhes foram gravados em build_log.txt nesta pasta.

:fim
echo.
pause
