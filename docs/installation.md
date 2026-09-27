# Installation Guide (Windows)

> **Status:** ✅ Verified (Windows 11, Python 3.11.9, Node.js 24, PostgreSQL 17.10). Sections 1–4 in Phase 1, 5–6 in Phases 5 and 10, §8 in Phase 14. To start everything at once afterwards: `scripts\start_all.ps1` (deployment.md §2).

Everything runs natively on Windows 10/11. **No Docker, WSL or Linux is needed.** All commands are for **PowerShell**.

## 1. Prerequisites

| Tool | Version | Check command | Download |
|---|---|---|---|
| Python | 3.11+ | `python --version` | https://www.python.org/downloads/ (tick **"Add python.exe to PATH"**) |
| Node.js + npm | 20+ | `node --version`, `npm --version` | https://nodejs.org/ (LTS) |
| PostgreSQL | 15+ | `psql --version` | https://www.postgresql.org/download/windows/ |
| Git | any | `git --version` | https://git-scm.com/download/win |

### Put `psql` on your PATH (one-time)
The PostgreSQL installer does not add `psql` to PATH. Add it for your user (PostgreSQL 17 shown):

```powershell
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\Program Files\PostgreSQL\17\bin", "User")
```
Close and reopen PowerShell, then run `psql --version`.

### Allow PowerShell to activate virtual environments (one-time)
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

## 2. Get the code
```powershell
git clone <your-repo-url> corporate-expense-intelligence
cd corporate-expense-intelligence
```

## 3. Create the backend `.env` and the PostgreSQL database
The database name, user and password live in `backend\.env`. A setup script reads them and creates the database for you.

**3.1 Create `backend\.env`**
```powershell
Copy-Item backend\.env.example backend\.env
```
Fill in every empty value. Generate each secret with:
```powershell
python -c "import secrets; print(secrets.token_urlsafe(50))"
```
`DATABASE_PASSWORD` is the password for the *application* user `expense_app`, which the script creates. It is **not** your `postgres` superuser password.

**3.2 Create the database user and database**
From the project root:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_database.ps1
```
psql asks for the password of the `postgres` superuser (chosen when PostgreSQL was installed). Expected output ends with `Database setup complete.`

What the script does ([scripts/setup_database.sql](../scripts/setup_database.sql)):
- creates login role `expense_app` (not a superuser; `CREATEDB` lets Django create its test database)
- creates database `expense_intelligence` owned by `expense_app`, UTF-8 encoded
- is safe to run again. It re-syncs the password from `.env`

Manual alternative in `psql -U postgres`:
```sql
CREATE ROLE expense_app LOGIN CREATEDB PASSWORD 'same-as-DATABASE_PASSWORD';
CREATE DATABASE expense_intelligence OWNER expense_app ENCODING 'UTF8' TEMPLATE template0;
```

## 4. Django backend
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py check              # "System check identified no issues"
python manage.py migrate            # from Phase 2 onwards (see note)
python manage.py createsuperuser    # from Phase 2 onwards
python manage.py seed_data          # optional demo data: start the ML service first (see §8)
python manage.py runserver 8000
```
Expected: `Starting development server at http://127.0.0.1:8000/`. Then http://127.0.0.1:8000/api/health/ returns `{"status":"ok","database":"ok"}`.

> **Note on `migrate`:** Do not run `migrate` before Phase 2 is in place. Django's custom User model must exist before the first migration. Migrating earlier creates the default `auth_user` table, and switching later requires recreating the database.

Using Command Prompt instead of PowerShell? Activate with `venv\Scripts\activate.bat`.

## 5. FastAPI ML service
Open a **new** PowerShell window:
```powershell
cd ml-service
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env        # set INTERNAL_API_KEY = ML_SERVICE_API_KEY from backend\.env
python -m pytest                   # all tests should pass
python -m uvicorn main:app --reload --port 8001
```
From Phase 7 the model is also trained once, before starting the service:
```powershell
python ..\scripts\generate_dataset.py   # creates data/raw/synthetic_invoices.csv
python ..\scripts\train_model.py        # creates ml-service/models/*.pkl
```
Expected: `Uvicorn running on http://127.0.0.1:8001`. Open http://127.0.0.1:8001/docs to see Swagger.

## 6. React frontend
Open a **third** PowerShell window:
```powershell
cd frontend
npm install
Copy-Item .env.example .env        # VITE_API_BASE_URL=http://127.0.0.1:8000/api
npm run dev
```
Expected: `Local: http://localhost:5173/`. Open it and sign in with an account created in Django (e.g. your superuser).

Other commands: `npm test` (166 tests), `npm run coverage`, `npm run build` (production build to `dist/`), `npm run lint`.
Use **http://localhost:5173**, not `127.0.0.1:5173`: Django's CORS setting allows exactly `http://localhost:5173`.

## Environment variables

### `backend/.env`
| Variable | Example | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | *(long random string)* | Django cryptographic signing. Generate with `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DEBUG` | `True` | `False` outside development |
| `HTTPS` | `False` | `True` only when served over HTTPS: secure cookies, HTTPS redirect, HSTS (`HSTS_SECONDS`, default 3600). `BEHIND_PROXY=True` when a reverse proxy terminates TLS |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost` | Hosts Django will serve |
| `DATABASE_NAME` | `expense_intelligence` | |
| `DATABASE_USER` | `expense_app` | |
| `DATABASE_PASSWORD` | *(secret)* | |
| `DATABASE_HOST` | `127.0.0.1` | |
| `DATABASE_PORT` | `5432` | |
| `JWT_SIGNING_KEY` | *(long random string)* | Signs JWTs (separate from the Django key) |
| `JWT_ACCESS_MINUTES` | `30` | Access-token lifetime |
| `JWT_REFRESH_DAYS` | `1` | Refresh-token lifetime |
| `FASTAPI_URL` | `http://127.0.0.1:8001` | ML service base URL |
| `ML_SERVICE_API_KEY` | *(shared secret)* | Must match FastAPI's `INTERNAL_API_KEY` |
| `ML_SERVICE_TIMEOUT` | `10` | Seconds |
| `BANK_HASH_KEY` | *(long random string)* | HMAC key for hashing bank account numbers |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Frontend origin |

### `ml-service/.env`
| Variable | Example |
|---|---|
| `INTERNAL_API_KEY` | same value as `ML_SERVICE_API_KEY` |
| `MODEL_DIR` | `models` |
| `LOG_LEVEL` | `INFO` |

### `frontend/.env`
| Variable | Example |
|---|---|
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000/api` |

> Only variables prefixed `VITE_` are visible to React, and they are **public** (bundled into the browser). Never put secrets in the frontend `.env`.

## 7. Verify everything
| Check | URL / command | Expected |
|---|---|---|
| Django | http://127.0.0.1:8000/api/health/ | `{"status":"ok","database":"ok"}` |
| Django admin | http://127.0.0.1:8000/admin/ | Login page |
| FastAPI | http://127.0.0.1:8001/health | `{"status":"ok","model_loaded":true}` |
| Swagger | http://127.0.0.1:8001/docs | Interactive docs |
| React | http://localhost:5173 | Login page |

Problems? See [troubleshooting.md](troubleshooting.md).

## 8. Demo data (`seed_data`)
Loads four demo accounts, 8 fictional vendors, a year of normal invoice history and the five demo scenarios. **Development only**: it refuses to run unless `DEBUG=True`.

```powershell
# window 1: the ML service must be running so the scenarios are analysed by the real model
cd ml-service; .\venv\Scripts\Activate.ps1; python -m uvicorn main:app --port 8001
# window 2
cd backend; .\venv\Scripts\Activate.ps1
python manage.py seed_data
```
Expected (about 3 seconds):
```text
Accounts: 4 | vendors: 8 | history invoices added: 192

Demo scenarios
  OK    1. Normal invoice       EV-2001   0 LOW Paid (simulated)
  OK    2. Duplicate invoice    INV1001   60 HIGH Under review -> Auditor review
  OK    3. Unusual invoice      AC-2003   40 MEDIUM Under review -> Manager review
  OK    4. Split purchase       BP-3003   70 HIGH Under review -> Auditor review
  OK    5. Bank account change  FL-2005   60 HIGH Under review -> Auditor review
```
| Option | Effect |
|---|---|
| `--password P` | Password for the demo accounts (or set `DEMO_PASSWORD`). Default: the documented demo password |
| `--no-scenarios` | Only accounts, vendors and history |
| `--reset` | First deletes **demo** invoices and vendors (asks for confirmation; `--noinput` skips the question). Your own data is never touched |

- **Safe to run again:** it only adds what is missing. If the ML service was down, the scenario invoices stay as drafts; start the service and run the command again to analyse them.
- **Demo records are marked:** users have an `@demo.local` e-mail, vendors a `DEMO-` registration number. A real account that already uses a demo username (e.g. `admin`) stops the command instead of being changed.
- Exact scores can differ slightly after retraining the model or changing Settings; the command prints `CHECK` with the expected result when a scenario does not match.
