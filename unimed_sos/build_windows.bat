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

echo [1/4] Criando ambiente...
%PY% -m venv .venv >> %LOG% 2>&1 || goto erro
call .venv\Scripts\activate.bat
echo [2/4] Instalando bibliotecas (precisa de internet)...
python -m pip install --upgrade pip >> %LOG% 2>&1
python -m pip install -r requirements_app.txt >> %LOG% 2>&1 || goto erro
echo [3/4] Baixando biblioteca de graficos para uso offline...
python -c "import urllib.request as u; u.urlretrieve('https://cdn.plot.ly/plotly-2.35.2.min.js','static/plotly.min.js')" >> %LOG% 2>&1 || goto erro
echo [4/4] Gerando o programa (pode levar alguns minutos)...
pyinstaller --noconfirm --clean --windowed --icon "icone.ico" --name "Controle de Treinamentos SOS" --add-data "static;static" --add-data "seed.json;." --collect-submodules uvicorn app.py >> %LOG% 2>&1 || goto erro
echo Gerando o pacote .zip para enviar aos colegas...
powershell -NoProfile -Command "Compress-Archive -Force -Path 'dist\Controle de Treinamentos SOS' -DestinationPath 'Controle de Treinamentos SOS.zip'" >> %LOG% 2>&1 || goto erro
echo.
echo PRONTO!
echo Programa: dist\Controle de Treinamentos SOS
echo Pacote para enviar: Controle de Treinamentos SOS.zip
goto fim

:semPython
echo.
echo PYTHON NAO ENCONTRADO.
echo Instale o Python 3.12 em python.org e marque a opcao "Add python.exe to PATH".
echo Depois de instalar, feche esta janela e rode o arquivo novamente.
goto fim

:erro
echo.
echo ERRO. Os detalhes foram gravados no arquivo build_log.txt, nesta mesma pasta.
echo Me envie o conteudo desse arquivo.

:fim
echo.
pause
