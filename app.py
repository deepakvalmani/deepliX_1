from flask import Flask, render_template, request, redirect, flash
import mysql.connector
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with a secure value

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
    name = request.form.get("name")
    email = request.form.get("email")
    message = request.form.get("message")

    try:
        conn = mysql.connector.connect(
            host=os.environ.get("DB_HOST"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD"),
            database=os.environ.get("DB_NAME")
        )

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (name, email, message) VALUES (%s, %s, %s)",
            (name, email, message)
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash(f'Thank you, {name}, your message has been sent successfully.')
    except mysql.connector.Error as db_err:
        flash(f"Database error: {str(db_err)}")
    except Exception as e:
        flash(f"An unexpected error occurred: {str(e)}")

    return redirect("/contact")

if __name__ == "__main__":
    app.run(debug=True)
