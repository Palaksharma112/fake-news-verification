from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import requests
from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime


# ---------------- FLASK SETUP ---------------- #

app = Flask(__name__)
app.secret_key = "fake_news_secret_key"


# ---------------- DATABASE ---------------- #

def create_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # User table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    # History table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            news TEXT,
            result TEXT,
            confidence REAL,
            date TEXT
        )
    """)

    conn.commit()
    conn.close()


# ---------------- REGISTER USER ---------------- #

def register_user(username, password):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO users(username, password) VALUES (?,?)",
            (username, password)
        )
        conn.commit()
        return True

    except:
        return False

    finally:
        conn.close()


# ---------------- LOGIN CHECK ---------------- #

def login_user(username, password):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (username, password)
    )

    user = cursor.fetchone()

    conn.close()

    return user


# ---------------- SAVE HISTORY ---------------- #

def save_history(username, news, result, confidence):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO history(username, news, result, confidence, date)
        VALUES(?,?,?,?,?)
        """,
        (
            username,
            news,
            result,
            confidence,
            datetime.now().strftime("%d-%m-%Y %H:%M")
        )
    )

    conn.commit()
    conn.close()


# ---------------- GET HISTORY ---------------- #

def get_history(username):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT news, result, confidence, date
        FROM history
        WHERE username=?
        ORDER BY id DESC
        """,
        (username,)
    )

    data = cursor.fetchall()

    conn.close()

    return data


# ---------------- WEB SCRAPING ---------------- #

def scrape_news():

    url = "https://www.bbc.com/news"

    response = requests.get(
        url,
        headers={
            "User-Agent":
            "Mozilla/5.0"
        }
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    headlines = []

    for h in soup.find_all("h2"):
        text = h.get_text(strip=True)

        if text:
            headlines.append(text)

    return headlines


# ---------------- VERIFY NEWS ---------------- #

def verify_news(user_news, scraped_news):

    highest_score = 0

    for news in scraped_news:

        vector = TfidfVectorizer(
            stop_words="english"
        ).fit_transform(
            [user_news, news]
        )

        score = cosine_similarity(
            vector[0],
            vector[1]
        )[0][0]

        if score > highest_score:
            highest_score = score


    confidence = highest_score * 100


    if confidence >= 50:
        result = "REAL NEWS"

    elif confidence >= 20:
        result = "SUSPICIOUS NEWS"

    else:
        result = "FAKE NEWS"


    return result, round(confidence, 2)


# ---------------- ROUTES ---------------- #

@app.route("/")
def index():
    return redirect("/login")


# REGISTER

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        if register_user(username, password):
            return redirect("/login")

        return render_template(
            "register.html",
            error="Username already exists!"
        )

    return render_template("register.html")


# LOGIN

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        user = login_user(
            username,
            password
        )

        if user:
            session["user"] = username
            return redirect("/dashboard")

        return render_template(
            "login.html",
            error="Invalid username or password!"
        )


    return render_template("login.html")


# DASHBOARD

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():

    if "user" not in session:
        return redirect("/login")


    result = None
    confidence = None


    if request.method == "POST":

        user_news = request.form["news"]

        headlines = scrape_news()

        result, confidence = verify_news(
            user_news,
            headlines
        )

        save_history(
            session["user"],
            user_news,
            result,
            confidence
        )


    return render_template(
        "dashboard.html",
        username=session["user"],
        result=result,
        confidence=confidence
    )


# HISTORY

@app.route("/history")
def history():

    if "user" not in session:
        return redirect("/login")


    data = get_history(
        session["user"]
    )


    return render_template(
        "history.html",
        history=data,
        username=session["user"]
    )


# LOGOUT

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# ---------------- MAIN ---------------- #

if __name__ == "__main__":

    create_db()

    app.run(
        debug=True
    )