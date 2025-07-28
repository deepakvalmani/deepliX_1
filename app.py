from flask import Flask, render_template, request, redirect, flash, session
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import bcrypt

# Load environment variables
load_dotenv('credentials.env')

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fallback_secret_key")

# Email & admin configs
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")
ADMIN_USER = os.environ.get("ADMIN_USER")
ADMIN_HASH = os.environ.get("ADMIN_HASHED_PASS")

# Login tracking
login_attempts = {}
BLOCK_DURATION_MINUTES = 15
MAX_ATTEMPTS = 3

DB_PATH = "database.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # to access by column name
    return conn

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/submit", methods=["POST"])
def submit():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    message = request.form.get("message", "").strip()

    if not name or not email or not message:
        flash("All fields are required.")
        return redirect("/contact")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (name, email, message) VALUES (?, ?, ?)",
            (name, email, message)
        )
        conn.commit()
        conn.close()
    except Exception as db_err:
        flash("Database error occurred.")
        print("DB ERROR:", db_err)
        return redirect("/contact")

    try:
        user_subject = "Thanks for contacting Deeplix!"
        user_body = f"""Hi {name},\n\nThank you for reaching out to Deeplix.
We've received your message and will get back to you shortly.\n\nYour Message:\n{message}\n\n— Deeplix Team"""

        admin_subject = f"New Contact Message from {name}"
        admin_body = f"New message from {name} <{email}>:\n\n{message}"

        def send_email(to, subject, body):
            msg = MIMEMultipart()
            msg["From"] = EMAIL_USER
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(EMAIL_USER, EMAIL_PASSWORD)
                server.send_message(msg)

        send_email(email, user_subject, user_body)
        send_email(ADMIN_EMAIL, admin_subject, admin_body)

        flash(f"Thank you, {name}. Your message has been sent.")
    except Exception as e:
        flash("Email error. Message was saved successfully.")
        print("EMAIL ERROR:", e)

    return redirect("/contact")

# Admin login and session management
app.permanent_session_lifetime = timedelta(minutes=30)

@app.before_request
def check_admin_session_timeout():
    session.permanent = True
    if session.get("admin_logged_in"):
        now = datetime.now()
        last_activity_str = session.get("last_activity")
        if last_activity_str:
            last_activity = datetime.strptime(last_activity_str, '%Y-%m-%d %H:%M:%S')
            if (now - last_activity).total_seconds() > 1800:
                session.pop("admin_logged_in", None)
                session.pop("last_activity", None)
                flash("Logged out due to 30 minutes of inactivity.", "warning")
                return redirect("/login")
        session["last_activity"] = now.strftime('%Y-%m-%d %H:%M:%S')

@app.route("/login", methods=["GET", "POST"])
def login():
    ip = request.remote_addr
    agent = request.headers.get('User-Agent', '')
    identifier = f"{ip}:{agent}"
    now = datetime.now()

    if identifier in login_attempts:
        attempts = login_attempts[identifier]
        if attempts["count"] >= MAX_ATTEMPTS and now < attempts["blocked_until"]:
            remaining_time = int((attempts["blocked_until"] - now).total_seconds() / 60)
            flash(f"You have been blocked for {remaining_time} more minute(s).")
            return render_template("login.html", blocked=True, remaining_time=remaining_time)

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == ADMIN_USER and bcrypt.checkpw(password.encode(), ADMIN_HASH.encode()):
            session["admin_logged_in"] = True
            session["last_activity"] = now.strftime('%Y-%m-%d %H:%M:%S')

            # Reset attempt counter correctly
            login_attempts[identifier] = {"count": 0, "blocked_until": now}

            return redirect("/admin_messages")

        else:
            if identifier not in login_attempts:
                login_attempts[identifier] = {"count": 1, "blocked_until": now}
            else:
                login_attempts[identifier]["count"] += 1
                if login_attempts[identifier]["count"] >= MAX_ATTEMPTS:
                    login_attempts[identifier]["blocked_until"] = now + timedelta(minutes=BLOCK_DURATION_MINUTES)

            remaining = MAX_ATTEMPTS - login_attempts[identifier]["count"]
            flash(f"Invalid credentials. {remaining if remaining > 0 else 0} attempt(s) left.")
            return render_template("login.html", blocked=remaining <= 0, remaining_time=BLOCK_DURATION_MINUTES)

    return render_template("login.html", blocked=False, remaining_time=0)

@app.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    session.pop("last_activity", None)
    flash("You have been logged out.")
    return redirect("/login")

@app.route("/admin_messages")
def admin_messages():
    if not session.get("admin_logged_in"):
        flash("Please log in to view messages.")
        return redirect("/login")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM messages ORDER BY created_at DESC")
        rows = cursor.fetchall()
        messages = [dict(row) for row in rows]
        cursor.close()
        conn.close()
        return render_template("admin_messages.html", messages=messages)
    except Exception as e:
        flash("⚠️ Database connection failed. Please try again.")
        return redirect("/login")



def initialize_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Check if the 'messages' table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
    exists = cursor.fetchone()
    if not exists:
        cursor.execute("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ SQLite table 'messages' created.")
    else:
        print("ℹ️ SQLite table 'messages' already exists.")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    initialize_db()
    app.run(debug=True, host="0.0.0.0", port=3000)
