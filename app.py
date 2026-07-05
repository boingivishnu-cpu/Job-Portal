import os
import sqlite3
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
app.config["DATABASE"] = os.environ.get("JOBPORTAL_DATABASE", os.path.join(app.root_path, "jobs.db"))


def get_db():
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            salary TEXT,
            category TEXT,
            application_link TEXT,
            application_email TEXT,
            posted_by INTEGER NOT NULL,
            posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(posted_by) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(job_id) REFERENCES jobs(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            keyword TEXT,
            location TEXT,
            email TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.commit()
    conn.close()


init_db()


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user


def get_matching_jobs(keyword="", location="", conn=None):
    created_conn = False
    if conn is None:
        conn = get_db()
        created_conn = True
    sql = "SELECT * FROM jobs WHERE 1=1"
    params = []

    if keyword:
        like_query = f"%{keyword}%"
        sql += " AND (title LIKE ? OR company LIKE ? OR description LIKE ?)"
        params.extend([like_query, like_query, like_query])
    if location:
        sql += " AND location LIKE ?"
        params.append(f"%{location}%")

    sql += " ORDER BY posted_at DESC"
    jobs = conn.execute(sql, params).fetchall()
    if created_conn:
        conn.close()
    return jobs


@app.context_processor
def inject_user():
    return {"current_user": get_current_user()}


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not get_current_user():
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user or user["role"] != "Admin":
            flash("Access denied. Admin only.", "danger")
            return redirect(url_for("dashboard"))
        return view_func(*args, **kwargs)

    return wrapped


@app.route("/")
def home():
    conn = get_db()
    jobs = conn.execute("SELECT * FROM jobs ORDER BY posted_at DESC LIMIT 6").fetchall()
    conn.close()
    return render_template("index.html", jobs=jobs)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role = request.form.get("role", "").strip()

        if not all([name, email, password, confirm_password, role]):
            flash("Please fill in all fields.", "danger")
        elif password != confirm_password:
            flash("Passwords do not match.", "danger")
        else:
            conn = get_db()
            existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                flash("An account with that email already exists.", "warning")
                conn.close()
            else:
                hashed_password = generate_password_hash(password)
                conn.execute(
                    "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                    (name, email, hashed_password, role),
                )
                conn.commit()
                conn.close()
                flash("Registration successful. Please log in.", "success")
                return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash("Welcome back!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    conn = get_db()
    posted_jobs = conn.execute(
        "SELECT * FROM jobs WHERE posted_by = ? ORDER BY posted_at DESC", (user["id"],)
    ).fetchall()
    applications = conn.execute(
        """
        SELECT a.id, a.status, a.applied_at, j.title, j.company
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        WHERE a.user_id = ?
        ORDER BY a.applied_at DESC
        """,
        (user["id"],),
    ).fetchall()
    conn.close()
    return render_template("dashboard.html", user=user, posted_jobs=posted_jobs, applications=applications)


@app.route("/post-job", methods=["GET", "POST"])
@login_required
def post_job():
    user = get_current_user()
    if user["role"] not in ["Employer", "Admin"]:
        flash("Only employers can post jobs.", "warning")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        company = request.form.get("company", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        salary = request.form.get("salary", "").strip()
        category = request.form.get("category", "").strip()
        application_link = request.form.get("application_link", "").strip()
        application_email = request.form.get("application_email", "").strip()

        if not all([title, company, location, description]):
            flash("Please complete the required fields.", "danger")
        else:
            conn = get_db()
            conn.execute(
                """
                INSERT INTO jobs (title, company, location, description, salary, category, application_link, application_email, posted_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (title, company, location, description, salary, category, application_link, application_email, user["id"]),
            )
            conn.commit()
            conn.close()
            flash("Job posted successfully.", "success")
            return redirect(url_for("dashboard"))

    return render_template("post_job.html")


@app.route("/edit-job/<int:job_id>", methods=["GET", "POST"])
@login_required
def edit_job(job_id):
    user = get_current_user()
    conn = get_db()
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()

    if not job:
        abort(404)
    if user["role"] != "Admin" and job["posted_by"] != user["id"]:
        flash("You cannot edit this job.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        company = request.form.get("company", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        salary = request.form.get("salary", "").strip()
        category = request.form.get("category", "").strip()
        application_link = request.form.get("application_link", "").strip()
        application_email = request.form.get("application_email", "").strip()

        if not all([title, company, location, description]):
            flash("Please complete the required fields.", "danger")
        else:
            conn = get_db()
            conn.execute(
                """
                UPDATE jobs
                SET title = ?, company = ?, location = ?, description = ?, salary = ?, category = ?, application_link = ?, application_email = ?
                WHERE id = ?
                """,
                (title, company, location, description, salary, category, application_link, application_email, job_id),
            )
            conn.commit()
            conn.close()
            flash("Job updated successfully.", "success")
            return redirect(url_for("dashboard"))

    return render_template("post_job.html", job=job)


@app.route("/delete-job/<int:job_id>")
@login_required
def delete_job(job_id):
    user = get_current_user()
    conn = get_db()
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if job and (user["role"] == "Admin" or job["posted_by"] == user["id"]):
        conn.execute("DELETE FROM applications WHERE job_id = ?", (job_id,))
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.commit()
        flash("Job deleted successfully.", "success")
    else:
        flash("You cannot delete this job.", "danger")
    conn.close()
    return redirect(url_for("dashboard"))


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    location = request.args.get("location", "").strip()

    conn = get_db()
    jobs = get_matching_jobs(query, location, conn)
    if category:
        jobs = [job for job in jobs if job["category"] == category]
    conn.close()
    return render_template("jobs.html", jobs=jobs, query=query, category=category, location=location)


@app.route("/alerts", methods=["GET", "POST"])
@login_required
def alerts():
    user = get_current_user()
    if user["role"] != "Job Seeker":
        flash("Only job seekers can subscribe to alerts.", "warning")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        keyword = request.form.get("keyword", "").strip()
        location = request.form.get("location", "").strip()
        email = request.form.get("email", "").strip().lower() or user["email"]

        if not keyword and not location:
            flash("Enter a keyword or location for your alert.", "danger")
        else:
            conn = get_db()
            conn.execute(
                "INSERT INTO alerts (user_id, keyword, location, email) VALUES (?, ?, ?, ?)",
                (user["id"], keyword, location, email),
            )
            conn.commit()
            conn.close()
            flash("Alert saved. Matching jobs will appear here instantly.", "success")
            return redirect(url_for("alerts"))

    conn = get_db()
    saved_alerts = conn.execute(
        "SELECT * FROM alerts WHERE user_id = ? ORDER BY created_at DESC",
        (user["id"],),
    ).fetchall()

    matching_jobs = []
    for alert in saved_alerts:
        matching_jobs.extend(get_matching_jobs(alert["keyword"], alert["location"], conn))

    conn.close()
    return render_template("alerts.html", alerts=saved_alerts, matching_jobs=matching_jobs)


@app.route("/delete-alert/<int:alert_id>", methods=["POST"])
@login_required
def delete_alert(alert_id):
    user = get_current_user()
    conn = get_db()
    alert = conn.execute(
        "SELECT * FROM alerts WHERE id = ? AND user_id = ?",
        (alert_id, user["id"]),
    ).fetchone()
    if alert:
        conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
        conn.commit()
        flash("Alert removed.", "success")
    else:
        flash("Alert not found.", "warning")
    conn.close()
    return redirect(url_for("alerts"))


@app.route("/apply/<int:job_id>", methods=["POST"])
@login_required
def apply_job(job_id):
    user = get_current_user()
    if user["role"] != "Job Seeker":
        flash("Only job seekers can apply for jobs.", "warning")
        return redirect(url_for("search"))

    conn = get_db()
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job:
        conn.close()
        abort(404)

    existing = conn.execute(
        "SELECT id FROM applications WHERE job_id = ? AND user_id = ?", (job_id, user["id"])
    ).fetchone()

    if existing:
        flash("You already applied for this job.", "warning")
        conn.close()
        return redirect(url_for("dashboard"))

    conn.execute(
        "INSERT INTO applications (job_id, user_id) VALUES (?, ?)",
        (job_id, user["id"]),
    )
    conn.commit()

    if job["application_link"]:
        conn.close()
        flash("Application recorded. You are being redirected to the employer link.", "success")
        return redirect(job["application_link"])

    if job["application_email"]:
        conn.close()
        flash("Application recorded. Your mail app will open for the employer contact.", "success")
        return redirect(f"mailto:{job['application_email']}")

    conn.close()
    flash("Application submitted successfully.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin")
@login_required
@admin_required
def admin_panel():
    conn = get_db()
    users = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    jobs = conn.execute("SELECT * FROM jobs ORDER BY posted_at DESC").fetchall()
    applications = conn.execute(
        """
        SELECT a.*, u.name AS applicant_name, j.title AS job_title
        FROM applications a
        JOIN users u ON a.user_id = u.id
        JOIN jobs j ON a.job_id = j.id
        ORDER BY a.applied_at DESC
        """
    ).fetchall()
    stats = {
        "users": conn.execute("SELECT COUNT(*) as count FROM users").fetchone()["count"],
        "jobs": conn.execute("SELECT COUNT(*) as count FROM jobs").fetchone()["count"],
        "applications": conn.execute("SELECT COUNT(*) as count FROM applications").fetchone()["count"],
    }
    conn.close()
    return render_template("admin.html", users=users, jobs=jobs, applications=applications, stats=stats)


@app.route("/admin/delete-user/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    current_user = get_current_user()
    if user_id == current_user["id"]:
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for("admin_panel"))

    conn = get_db()
    conn.execute("DELETE FROM applications WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM jobs WHERE posted_by = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash("User removed successfully.", "success")
    return redirect(url_for("admin_panel"))


@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template("500.html"), 500


if __name__ == "__main__":
    app.run(debug=True)
