@echo off
REM Clique duas vezes neste arquivo para ligar o coletor no Windows.
cd /d "%~dp0"
if not exist node_modules call npm install
if not exist .env (
  copy .env.example .env >nul
  echo Preencha o arquivo .env que abriu no Bloco de Notas, salve e rode de novo.
  notepad .env
  pause
  exit /b
)
npm start
pause
