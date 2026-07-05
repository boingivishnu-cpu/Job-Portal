# JobPortal

A simple Flask-based job portal application with user registration, login, job posting, job searching, alerts, and admin management.

## Features

- User registration and login
- Role-based access: Job Seeker, Employer, Admin
- Post, edit, and delete job listings
- Search jobs by keyword, category, and location
- Job seeker alerts for matching job postings
- Apply to jobs with email or external application links
- Admin dashboard for managing users, jobs, and applications

## Requirements

- Python 3.11+ (recommended)
- Dependencies listed in `requirements.txt`

## Setup

1. Clone or copy the project to your local machine.
2. Create and activate a virtual environment:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
pip install -r requirements.txt
```

4. (Optional) Set environment variables or create a `.env` file in the project root:

```powershell
$env:SECRET_KEY = "your-secret-key"
$env:JOBPORTAL_DATABASE = "C:\path\to\jobs.db"
```

Or create `.env` with:

```dotenv
SECRET_KEY=your-secret-key
JOBPORTAL_DATABASE=C:\path\to\jobs.db
```

If not set, the app uses a default secret key and creates `jobs.db` in the project root.

## Run the app

```powershell
python app.py
```

Then open http://127.0.0.1:5000 in your browser.

## Testing

This project includes a simple pytest test in `tests/test_job_alerts.py`.

Run tests with:

```powershell
pytest
```

## Project Structure

- `app.py` - Flask application and routing logic
- `templates/` - Jinja2 HTML templates
- `static/` - CSS, JS, and image assets
- `tests/` - pytest tests
- `requirements.txt` - Python dependencies

## Notes

- The app uses SQLite and initializes the database automatically on first run.
- Admin users can view and manage all users, jobs, and applications.
- Job seeker users can save alerts and see matching job listings immediately.

## License

This project does not include a license file. Add one if you want to define reuse terms.
