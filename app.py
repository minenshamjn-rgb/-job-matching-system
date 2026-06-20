from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime
import os

from database import (
    init_db,
    create_user,
    get_user_by_email,
    get_user_by_id,
    save_resume,
    get_all_jobs,
    get_stats,
    save_recommendations,
    get_user_recommendations
)

from resume_parser import extract_skills
from scraper import scrape_jobs
from matcher import match_jobs


app = Flask(__name__)

app.secret_key = "change-this-secret-key"

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

init_db()


def allowed_pdf(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() == "pdf"


def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "error")
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


@app.context_processor
def inject_user():
    user = None

    if "user_id" in session:
        user = get_user_by_id(session["user_id"])

    return {
        "current_user": user
    }


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)

        success = create_user(
            name,
            email,
            password_hash
        )

        if not success:
            flash("Email already exists. Please login.", "error")
            return redirect(url_for("login"))

        flash("Account created successfully. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = get_user_by_email(email)

        if not user:
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))

        if not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))

        session["user_id"] = user["id"]

        flash("Logged in successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():

    stats = get_stats(session["user_id"])
    jobs = get_all_jobs(limit=6)
    recommendations = get_user_recommendations(session["user_id"])

    return render_template(
        "dashboard.html",
        stats=stats,
        jobs=jobs,
        recommendations=recommendations
    )


@app.route("/refresh-jobs", methods=["POST"])
@login_required
def refresh_jobs():

    result = scrape_jobs(
        limit=30,
        refresh=True
    )

    if result["success"]:
        flash(result["message"], "success")
    else:
        flash(result["message"], "error")

    return redirect(url_for("dashboard"))


@app.route("/upload", methods=["GET"])
@login_required
def upload_page_redirect():
    return redirect(url_for("dashboard"))


@app.route("/upload", methods=["POST"])
@login_required
def upload_resume():

    if "resume" not in request.files:
        flash("No resume selected.", "error")
        return redirect(url_for("dashboard"))

    file = request.files["resume"]

    if file.filename == "":
        flash("Please choose a resume file.", "error")
        return redirect(url_for("dashboard"))

    if not allowed_pdf(file.filename):
        flash("Only PDF resumes are allowed.", "error")
        return redirect(url_for("dashboard"))

    original_filename = secure_filename(file.filename)

    saved_filename = (
        str(session["user_id"]) +
        "_" +
        datetime.now().strftime("%Y%m%d%H%M%S") +
        "_" +
        original_filename
    )

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        saved_filename
    )

    file.save(filepath)

    try:
        skills = extract_skills(filepath)

    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("dashboard"))

    resume_id = save_resume(
        session["user_id"],
        original_filename,
        skills
    )

    scrape_result = scrape_jobs(
        limit=30,
        refresh=True
    )

    jobs = match_jobs(skills)

    save_recommendations(
        session["user_id"],
        resume_id,
        jobs
    )

    return render_template(
        "results.html",
        filename=original_filename,
        skills=skills,
        jobs=jobs,
        scrape_result=scrape_result
    )


@app.route("/api/jobs")
def api_jobs():

    jobs = get_all_jobs()

    return jsonify({
        "count": len(jobs),
        "jobs": jobs
    })


@app.route("/api/scrape", methods=["POST"])
@login_required
def api_scrape():

    result = scrape_jobs(
        limit=30,
        refresh=True
    )

    return jsonify(result)


@app.route("/api/recommendations")
@login_required
def api_recommendations():

    recommendations = get_user_recommendations(
        session["user_id"]
    )

    return jsonify({
        "count": len(recommendations),
        "recommendations": recommendations
    })


@app.route("/api/status")
def api_status():

    jobs = get_all_jobs()

    return jsonify({
        "system": "Nepal Smart Job Matcher",
        "status": "running",
        "total_jobs": len(jobs),
        "features": [
            "User Login",
            "PDF Resume Upload",
            "Resume Skill Extraction",
            "Dynamic Web Scraping",
            "SQLite Database",
            "Job Matching",
            "Retry Handling",
            "Proxy Rotation",
            "Scheduler Ready",
            "User-Specific Recommendations"
        ]
    })


@app.route("/logout")
def logout():

    session.clear()

    flash("Logged out successfully.", "success")

    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)