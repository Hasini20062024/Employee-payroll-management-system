# Haven ? Employee Payroll Management System

A responsive website built with plain HTML, CSS, and JavaScript, served by Django with a REST API backed by PostgreSQL, based on the supplied EPMS SRS. The app includes role-aware authentication, people records, attendance punches, leave and WFH workflows, salary structures, monthly payroll drafts and finalization, PDF payslips, CSV export, announcements, holidays, notifications, documents, audit records, and an employee-scoped assistant.

## Requirements

- Python 3.11+ (3.14 also works with current dependencies)
- PostgreSQL 14+ for the intended database setup

## Run locally

### 1. Create the PostgreSQL database in pgAdmin 4

1. Install/start PostgreSQL and open pgAdmin 4. Connect to your local server (usually `localhost:5432`).
2. In **Login/Group Roles**, create a login role named `epms_user`; set a strong password and enable **Can login**. Do not grant superuser.
3. Under **Databases ? Create ? Database**, set database name `epms` and owner `epms_user`. Save. The database owner needs schema/table creation rights; ownership grants this on the new database.
4. In `backend/.env`, set `DB_NAME=epms`, `DB_USER=epms_user`, `DB_PASSWORD` to the same password, `DB_HOST=localhost`, and `DB_PORT=5432`. Confirm PostgreSQL is running and the port matches the server properties in pgAdmin.
5. Optional connection check in pgAdmin: select `epms`, open **Query Tool**, run `SELECT current_database(), current_user;`. Expected: `epms` and `epms_user`.

### 2. Start the website and Django API

PowerShell:

```powershell
cd C:\Users\ACER\OneDrive\Desktop\epms\backend
if (!(Test-Path .venv\Scripts\python.exe)) { python -m venv .venv }
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
# Copy .env.example to .env if .env does not exist, then enter your DB password
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

At the createsuperuser prompts, enter an email and username. After creation, set the user's role to `ADMIN` in Django admin at `http://localhost:8000/admin/` (the first user can instead be created as admin in the shell: `python manage.py shell`, then `from payroll.models import User; User.objects.filter(is_superuser=True).update(role='ADMIN')`). Create a Department, at least one Employee, a Salary Structure, and (optionally) a Shift in admin before running payroll. The admin dashboard can also create employees, salary structures, shifts, and assignments. Employees can register through the employee sign-up link and sign in with their work email. Administrator accounts are created by an administrator.

Django serves the plain HTML, CSS, and JavaScript website and its API on the same address. After the server starts, open `http://localhost:8000/`. The API is available at `http://localhost:8000/api/`.

## Database setup alternatives

For a quick UI-only preview without PostgreSQL, set `DB_ENGINE=django.db.backends.sqlite3` in `backend/.env`; this is only for local development and is not the SRS production database. To inspect PostgreSQL tables in pgAdmin, refresh **Databases ? epms ? Schemas ? public ? Tables** after `migrate`. Django migrations create and evolve the schema; do not manually create the application tables in Query Tool.

## Included workflows

The backend provides APIs for employee and department management, attendance, leave and WFH, shifts, overtime, payroll, payslips, holidays, announcements, documents, notifications, audit records, reports, password reset, and employee-scoped assistant features. The current plain JavaScript page implements the employee/admin sign-in and employee sign-up flow; remaining feature screens are planned as later implementation steps.

For automatic absence classification, run `python manage.py mark_absent` after the latest scheduled shift ends. On Windows, configure this command in Task Scheduler daily after working hours; on Linux, schedule it with cron.

## Notes

- Never commit `.env`; use a long random `DJANGO_SECRET_KEY`, `DEBUG=false`, HTTPS, and secure deployment settings in production.
- JWT access tokens last 20 minutes; refresh tokens rotate and are blacklisted on rotation. The frontend redirects to sign-in when an access token expires.
- Add `GEMINI_API_KEY` to `.env` to enable open-ended assistant answers. Common leave, attendance, and salary explanations work without the external service.
- Employees can create their own employee account through the sign-up link. Administrator accounts should be created through Django admin.
- PDF payslips are only available after an administrator finalizes a payroll.
- Automated database backups and production SMTP delivery require deployment-specific configuration. Password-reset email uses the console backend by default in development; configure SMTP variables in `.env` to send messages.
