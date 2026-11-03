@echo off
setlocal
echo === AI Smart Interview Simulator: setup ===
where python >nul 2>nul || (echo Python 3.11 is required. Install from python.org and tick "Add to PATH". & exit /b 1)
where node >nul 2>nul || (echo Node.js 18+ is required. Install from nodejs.org. & exit /b 1)
cd /d "%~dp0backend"
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt || (echo Backend dependency install failed. & exit /b 1)
if not exist .env (copy .env.example .env >nul & echo Created backend\.env : OPEN IT and add your GEMINI_API_KEY and a JWT_SECRET.)
python init_db.py
cd /d "%~dp0frontend"
call npm install || (echo npm install failed. & exit /b 1)
echo.
echo Setup complete. Next: edit backend\.env, then run start-backend.bat and start-frontend.bat (two windows).
endlocal
