# ClinIQ

ClinIQ is a Flask-based clinic queue and appointment management MVP. It helps small clinics reduce waiting-room confusion with online booking, receptionist approval, FIFO token generation, doctor workflow tools, queue tracking, clinic status updates, and simulated notification logs.

Built a full-stack healthcare operations MVP using Flask, SQLite, SQLAlchemy, Flask-Login, server-rendered HTML, and responsive CSS. Implemented role-based dashboards, appointment booking, FIFO queue tokens, consultation notes, clinic status management, and simulated notification logging with deployment-ready configuration.

## Features

- Patient booking with validation
- Public queue tracker by phone number
- Doctor and receptionist authentication
- Role-protected dashboards
- Receptionist appointment approval/rejection
- Walk-in patient support
- FIFO token generation with daily reset
- Doctor consultation flow with notes
- Clinic status: open, closed, emergency
- Simulated notification logs for MVP demos
- Responsive, accessible UI for patients and clinic staff
- Friendly 404 and 500 pages

## Tech Stack

- Flask
- Flask-Login
- Flask-SQLAlchemy
- SQLite
- HTML
- CSS
- Vanilla JavaScript ready structure
- Gunicorn for production serving

## Project Structure

```text
ClinIQ/
├── app/
│   ├── models/
│   ├── routes/
│   ├── services/
│   ├── static/css/
│   └── templates/
├── config.py
├── run.py
├── wsgi.py
├── seed.py
├── requirements.txt
├── Procfile
└── README.md
```

## Local Installation

1. Create and activate a virtual environment:

```powershell
python -m venv venv
venv\Scripts\activate
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Create your `.env` file:

```powershell
copy .env.example .env
```

4. Seed demo data:

```powershell
python seed.py
```

5. Run the app:

```powershell
python run.py
```

Run tests:

```powershell
pip install pytest
c:\Users\HP\Desktop\Cliniq\venv\Scripts\python.exe -m pytest -q
```

Open:

```text
http://127.0.0.1:5000
```

## Demo Credentials

Demo credentials have been removed from the public README. To seed demo users and appointments, run `python seed.py` — the demo credentials are included as comments in `seed.py` for local testing only.

## Render Deployment

Render's Flask quickstart uses `pip install -r requirements.txt` as the build command and Gunicorn as the production server start command.

Use these settings:

```text
Build Command:
pip install -r requirements.txt

Start Command:
gunicorn wsgi:app
```

Environment variables:

```text
SECRET_KEY=<long-random-secret>
DATABASE_URL=sqlite:///cliniq.db
FLASK_DEBUG=false
SESSION_COOKIE_SECURE=true
```

For a demo deployment, SQLite is acceptable. For production healthcare use, move to a managed database and follow healthcare privacy/compliance requirements.

## PostgreSQL and Migrations

To use PostgreSQL, set `DATABASE_URL` in your environment, then run:

```powershell
set DATABASE_URL=postgresql://user:password@host:5432/dbname
python run_migrations.py
```

This project also supports Alembic migrations via `run_migrations.py` and the Flask app config.

## Running tests

Install testing dependencies and run:

```powershell
pip install -r requirements.txt
c:\Users\HP\Desktop\Cliniq\venv\Scripts\python.exe -m pytest -q
```

## Screenshots

Add screenshots here:

- Home page
- Patient booking
- Queue tracker
- Receptionist dashboard
- Doctor dashboard

## Future Improvements

- Real SMS/WhatsApp notifications using Twilio or WhatsApp API
- Persistent production database such as PostgreSQL
- Multi-clinic support
- Patient self-cancellation/rescheduling
- Audit logs
- Exportable reports
- Deployment monitoring

## Important Note

ClinIQ is an MVP/demo project for learning, startup incubation discussions, and portfolio presentation. It is not a production medical record system.
