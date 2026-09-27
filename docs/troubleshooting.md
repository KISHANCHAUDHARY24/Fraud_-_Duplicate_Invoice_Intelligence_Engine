# Troubleshooting (Windows)

> **Status:** ✅ Contains the real problems met during development (Phases 1–16).

### `python` is not recognized
**Cause:** Python is not on PATH, or the Microsoft Store alias is intercepting the command.
**Fix:**
1. Try `py --version`. If that works, use `py -m venv venv`.
2. Reinstall from python.org and tick **"Add python.exe to PATH"**.
3. Settings → Apps → Advanced app settings → **App execution aliases** → turn off `python.exe` / `python3.exe`.
4. Reopen PowerShell.

### `pip.exe` blocked: "An Application Control policy has blocked this file"
**Cause:** Windows 11 Smart App Control / Application Control blocks the small `pip.exe` launcher (seen during Phase 1).
**Fix:** run pip through Python. It is the same tool, started a different way:
```powershell
python -m pip install -r requirements.txt
```
The same applies to other launcher `.exe` files in `venv\Scripts` (e.g. use `python -m uvicorn` / `python -m pytest` if `uvicorn.exe` / `pytest.exe` are blocked).

### `node` / `npm` is not recognized
Install Node LTS from nodejs.org, then **close and reopen** PowerShell (and VS Code). Check with `node --version`.

### Virtual environment will not activate
`...Activate.ps1 cannot be loaded because running scripts is disabled on this system`
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
Or use Command Prompt: `venv\Scripts\activate.bat`. Once it works, your prompt starts with `(venv)`.

### `psql` is not recognized
```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres     # folder may be named sql-17 etc.
```
To fix it permanently, see [installation.md](installation.md#put-psql-on-your-path-one-time).

### PostgreSQL connection error
`connection to server at "127.0.0.1", port 5432 failed: Connection refused`
```powershell
Get-Service postgresql*
Start-Service postgresql-x64-17      # may need an Administrator PowerShell
```
Check that `DATABASE_HOST`/`DATABASE_PORT` in `backend\.env` match.

### Database authentication error
`password authentication failed for user "expense_app"` (for example, `runserver` exits immediately with a long traceback)
- **Most common cause:** the database setup script has not been run yet, so the user does not exist. Run `powershell -ExecutionPolicy Bypass -File scripts\setup_database.ps1`.
- You changed `DATABASE_PASSWORD` in `.env`: run the setup script again. It re-syncs the password.
- Check `DATABASE_USER` / `DATABASE_PASSWORD` in `.env` (no quotes, no trailing spaces).

### `psql.exe` not found at `C:\Program Files\PostgreSQL\17\bin`
Some installations use a different folder name (e.g. `C:\Program Files\PostgreSQL\sql-17`). Find it with:
```powershell
Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\psql.exe"
```
`scripts\setup_database.ps1` searches automatically, or pass `-PgBin "<folder>\bin"`.

### `permission denied for schema public` during migrate
PostgreSQL 15+ no longer lets every user create tables in `public`. Make the app user the owner:
```sql
ALTER DATABASE expense_intelligence OWNER TO expense_app;
\c expense_intelligence
ALTER SCHEMA public OWNER TO expense_app;
```

### Port already in use
`Error: That port is already in use` / `[WinError 10048]`
```powershell
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```
Or run on another port and update `FASTAPI_URL` / `VITE_API_BASE_URL` to match.

### `'…\node_modules\.bin\' is not recognized` when running `npm run dev`
**Cause:** the project folder path contains `&` (e.g. `Fraud_&_Duplicate_…`). npm runs scripts through `cmd.exe` using `.cmd` launchers, and `cmd.exe` treats `&` as "run another command", so the path is cut in half.
**Fix used in this project:** `frontend/package.json` scripts call Node directly (`node node_modules/vite/bin/vite.js`), which works with any folder name. If you add a new script, use the same pattern, or keep project folders free of `&`.

### npm install fails
```powershell
npm cache clean --force
Remove-Item -Recurse -Force node_modules, package-lock.json
npm install
```
If a path-length error occurs, keep the project near the drive root (e.g. `C:\projects\...`). Antivirus locking files: retry, or exclude the folder.

### Django migration problems
- `No changes detected` → is the app in `INSTALLED_APPS`?
- `InconsistentMigrationHistory` involving `accounts.User` → the custom user model was added after the first migrate. During development only: drop and recreate the DB, then `python manage.py migrate`.
- Never delete migration files that have already been applied to a shared DB.

### FastAPI connection problem (from Django)
`ML_SERVICE_UNAVAILABLE` / invoices stuck with `ANALYSIS_FAILED`
- Is Uvicorn running? Open http://127.0.0.1:8001/health
- Does `FASTAPI_URL` in `backend\.env` match the port?
- Does `ML_SERVICE_API_KEY` (Django) equal `INTERNAL_API_KEY` (FastAPI)? A mismatch gives 401.
- Re-run analysis from the invoice page ("Re-analyse") after fixing.

### `model_loaded: false`
Run `python scripts\train_model.py` from the project root (with the ml-service venv active), then restart Uvicorn.

### CORS error in the browser console
`blocked by CORS policy: No 'Access-Control-Allow-Origin' header`
- `CORS_ALLOWED_ORIGINS` in `backend\.env` must be exactly `http://localhost:5173` (no trailing slash).
- Use `localhost` consistently: `127.0.0.1:5173` and `localhost:5173` are different origins.
- Restart Django after changing `.env`.

### JWT authentication error
- `401 TOKEN_INVALID` right after login → the system clock is wrong, or `JWT_SIGNING_KEY` changed. Log in again.
- Logged out every 30 min → expected if the refresh token also expired. Check `JWT_REFRESH_DAYS`.
- Clear old tokens: browser DevTools → Application → Local Storage → delete the keys.

### `No time zone found with key Asia/Kolkata` (ML service)
**Cause:** Python's `zoneinfo` reads timezone rules from the operating system. Linux and macOS include them, **Windows does not**.
**Fix:** install the `tzdata` package (it is in `ml-service/requirements.txt`):
```powershell
python -m pip install tzdata
```
The Django venv already has it (Django depends on it).

### `UnicodeEncodeError: 'charmap' codec can't encode character` when printing
Only affects printing to the Windows console. Messages contain `σ`, `→` and `–`. API responses are UTF-8 JSON and are fine. For scripts:
```powershell
$env:PYTHONIOENCODING = "utf-8"
```

### The first `import pandas` / `import sklearn` takes minutes
Seen in Phase 7: the very first imports after installing numpy, pandas and scikit-learn took 115–134 s. Afterwards they took about 1 s. **Cause:** Windows Defender scans every newly installed library file (`.pyd`/`.dll`) the first time it is loaded. **Fix:** nothing. Wait once and it stays fast. If it keeps happening, exclude the project's `venv` folders from real-time scanning (only if your organisation allows it).

### `.env` changes are ignored
Restart the server. Django and Uvicorn read `.env` only at startup. Vite needs a restart for `VITE_*` changes.

### Report times are a few minutes off from the clock on the PC
Reports, working-hours checks and analytics use the **business timezone setting** (Settings → Working time → Timezone, default `Asia/Kolkata`, UTC+5:30), not the PC's clock. A PC set to Nepal time (UTC+5:45) therefore shows times 15 minutes later. If the business runs on another timezone, change the setting (e.g. `Asia/Kathmandu`).

### A PDF report shows empty boxes instead of some characters
The PDF uses the standard Helvetica font, which has no glyphs for characters such as ₹ or non-Latin scripts in vendor names. Amounts are printed as numbers with a separate currency code, so figures are never affected. Use the CSV export (UTF-8) when names contain such characters.
