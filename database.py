import sqlite3
import json
from datetime import datetime

DATABASE = "jobs.db"


def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        company TEXT,
        location TEXT,
        skills TEXT,
        link TEXT UNIQUE,
        source TEXT,
        scraped_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS resumes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        extracted_skills TEXT,
        uploaded_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        resume_id INTEGER NOT NULL,
        job_id INTEGER NOT NULL,
        score INTEGER NOT NULL,
        matched_skills TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(resume_id) REFERENCES resumes(id),
        FOREIGN KEY(job_id) REFERENCES jobs(id)
    )
    """)

    conn.commit()
    conn.close()


def create_user(name, email, password_hash):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
        INSERT INTO users (name, email, password_hash, created_at)
        VALUES (?, ?, ?, ?)
        """, (name, email, password_hash, datetime.now().isoformat()))

        conn.commit()
        return True

    except sqlite3.IntegrityError:
        return False

    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()

    conn.close()

    return dict(user) if user else None


def get_user_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    conn.close()

    return dict(user) if user else None


def delete_all_jobs():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM jobs")

    conn.commit()
    conn.close()


def insert_job(title, company, location, skills, link, source="JobsNepal"):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO jobs (title, company, location, skills, link, source, scraped_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(link) DO UPDATE SET
        title = excluded.title,
        company = excluded.company,
        location = excluded.location,
        skills = excluded.skills,
        source = excluded.source,
        scraped_at = excluded.scraped_at
    """, (
        title,
        company,
        location,
        skills,
        link,
        source,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


def get_all_jobs(limit=None):

    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT id, title, company, location, skills, link, source, scraped_at
    FROM jobs
    ORDER BY id DESC
    """

    if limit:
        query += " LIMIT ?"
        cursor.execute(query, (limit,))
    else:
        cursor.execute(query)

    jobs = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jobs



def save_resume(user_id, filename, extracted_skills):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO resumes (user_id, filename, extracted_skills, uploaded_at)
    VALUES (?, ?, ?, ?)
    """, (
        user_id,
        filename,
        json.dumps(extracted_skills),
        datetime.now().isoformat()
    ))

    resume_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return resume_id


def save_recommendations(user_id, resume_id, matches):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM recommendations WHERE user_id = ?",
        (user_id,)
    )

    for job in matches:
        cursor.execute("""
        INSERT INTO recommendations
        (user_id, resume_id, job_id, score, matched_skills, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            resume_id,
            job["id"],
            job["score"],
            json.dumps(job["matched_skills"]),
            datetime.now().isoformat()
        ))

    conn.commit()
    conn.close()


def get_user_recommendations(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        r.score,
        r.matched_skills,
        j.title,
        j.company,
        j.location,
        j.link
    FROM recommendations r
    JOIN jobs j ON r.job_id = j.id
    WHERE r.user_id = ?
    ORDER BY r.score DESC
    """, (user_id,))

    rows = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return rows


def get_stats(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM jobs")
    total_jobs = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT COUNT(*) AS total FROM resumes WHERE user_id = ?",
        (user_id,)
    )
    total_resumes = cursor.fetchone()["total"]

    conn.close()

    return {
        "total_jobs": total_jobs,
        "total_resumes": total_resumes
    }


if __name__ == "__main__":
    init_db()
    print("Database created successfully.")