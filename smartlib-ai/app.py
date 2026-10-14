
import json
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from groq import Groq

# --------------------------------------------------
# 1. PROJECT CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

# Load configuration from this project's .env file.
load_dotenv(dotenv_path=ENV_PATH, override=True)

DATABASE_DIR = BASE_DIR / "database"
DATABASE_PATH = DATABASE_DIR / "books.db"
BOOKS_JSON_PATH = BASE_DIR / "data" / "books.json"

app = Flask(__name__)

# --------------------------------------------------
# 2. GROQ API CONFIGURATION
# --------------------------------------------------

api_key = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile"
)

# Never print the API key itself.
print(f"Environment file exists: {ENV_PATH.is_file()}")
print(f"Groq API key detected: {bool(api_key)}")
print(f"Groq API key length: {len(api_key)}")
print(f"Groq model configured: {GROQ_MODEL}")

groq_client = Groq(api_key=api_key) if api_key else None

# --------------------------------------------------
# 3. DATABASE CONNECTION
# --------------------------------------------------

def get_db_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


# --------------------------------------------------
# 4. INITIALIZE DATABASE AND IMPORT SAMPLE BOOKS
# --------------------------------------------------

def initialize_database():
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    if not BOOKS_JSON_PATH.is_file():
        raise FileNotFoundError(
            f"Sample book dataset not found: {BOOKS_JSON_PATH}"
        )

    with open(BOOKS_JSON_PATH, "r", encoding="utf-8") as file:
        books = json.load(file)

    with get_db_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                available_copies INTEGER NOT NULL DEFAULT 0
            )
        """)

        count = connection.execute(
            "SELECT COUNT(*) FROM books"
        ).fetchone()[0]

        # Import sample records only when the table is empty.
        if count == 0:
            connection.executemany("""
                INSERT INTO books (
                    id,
                    title,
                    author,
                    category,
                    description,
                    available_copies
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                (
                    book["id"],
                    book["title"],
                    book["author"],
                    book["category"],
                    book["description"],
                    book["available_copies"]
                )
                for book in books
            ])

    print(f"SQLite database ready: {DATABASE_PATH}")

    with get_db_connection() as connection:
        total = connection.execute(
            "SELECT COUNT(*) FROM books"
        ).fetchone()[0]

    print(f"Books currently stored: {total}")


# --------------------------------------------------
# 5. SEARCH BOOKS
# --------------------------------------------------

def search_books(query="", limit=20):
    query = query.strip()

    with get_db_connection() as connection:
        if query:
            pattern = f"%{query}%"

            rows = connection.execute("""
                SELECT *
                FROM books
                WHERE title LIKE ?
                   OR author LIKE ?
                   OR category LIKE ?
                   OR description LIKE ?
                ORDER BY title
                LIMIT ?
            """, (
                pattern,
                pattern,
                pattern,
                pattern,
                limit
            )).fetchall()
        else:
            rows = connection.execute("""
                SELECT *
                FROM books
                ORDER BY title
                LIMIT ?
            """, (limit,)).fetchall()

    return [dict(row) for row in rows]


# --------------------------------------------------
# 6. HOME PAGE
# --------------------------------------------------

@app.route("/")
def home():
    return render_template("index.html")


# --------------------------------------------------
# 7. BOOK SEARCH API
# --------------------------------------------------

@app.route("/api/books", methods=["GET"])
def get_books():
    query = request.args.get("q", "").strip()
    books = search_books(query)
    return jsonify(books)


# --------------------------------------------------
# 8. GROQ CHATBOT API
# --------------------------------------------------

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}

    question = data.get("message", "")

    if not isinstance(question, str):
        return jsonify({
            "error": "The message must be text."
        }), 400

    question = question.strip()

    if not question:
        return jsonify({
            "error": "Please enter a question."
        }), 400

    if len(question) > 1000:
        return jsonify({
            "error": "Please keep your question under 1000 characters."
        }), 400

    if groq_client is None:
        app.logger.error(
            "Groq client unavailable. Check the project .env file."
        )
        return jsonify({
            "error": (
                "Groq API key is missing. Check the .env file "
                "beside app.py and restart Flask."
            )
        }), 503

    # Retrieve the catalogue for grounding AI responses.
    relevant_books = search_books(question, limit=20)

    # The small sample catalogue can be supplied for recommendations
    # even when the question does not match a book field.
    if not relevant_books:
        relevant_books = search_books("", limit=20)

    catalogue = json.dumps(
        relevant_books,
        ensure_ascii=False
    )

    system_prompt = f"""
You are SmartLib AI, a helpful library assistant.

Use this catalogue from the SQLite database as the source of truth
for book titles, authors, descriptions, categories and availability.

CATALOGUE:
{catalogue}

Instructions:
1. Recommend books that exist in the provided catalogue.
2. Do not invent book availability or catalogue records.
3. A book with available_copies equal to zero is unavailable.
4. If a requested book is absent, explain that it is not listed
   in the current sample catalogue.
5. You may explain general educational and library topics.
6. Keep answers concise, clear and friendly.
7. Remind users that availability is sample project data,
   not a live college library inventory.
"""

    try:
        completion = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            temperature=0.3,
            max_completion_tokens=500
        )

        answer = completion.choices[0].message.content

        if not answer:
            answer = "Sorry, I couldn't generate a response."

        return jsonify({
            "answer": answer
        })

    
    except Exception as e:
        print("\n========== GROQ API ERROR ==========", flush=True)
        print(type(e).__name__, flush=True)
        print(str(e), flush=True)
        print("====================================\n", flush=True)

        return jsonify({
            "answer": "The AI request failed. Check the VS Code terminal for the error."
        }), 502



# --------------------------------------------------
# 9. RUN APPLICATION
# --------------------------------------------------


# Initialize the database when the application starts
initialize_database()

# Run locally
if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )

