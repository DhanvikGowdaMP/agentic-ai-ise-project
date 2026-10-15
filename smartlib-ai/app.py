
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
    history = data.get("history", [])

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

    # Validate conversation history.
    if not isinstance(history, list):
        history = []

    valid_history = []

    for item in history[-10:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = item.get("content")

        if (
            role in ("user", "assistant")
            and isinstance(content, str)
            and content.strip()
            and len(content) <= 3000
        ):
            valid_history.append({
                "role": role,
                "content": content.strip()
            })

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

    # Retrieve catalogue books.
    relevant_books = search_books(question, limit=20)

    if not relevant_books:
        relevant_books = search_books("", limit=20)

    catalogue = json.dumps(
        relevant_books,
        ensure_ascii=False
    )

    system_prompt = f"""
You are SmartLib AI, an intelligent library and programming
learning assistant.

You can answer questions about Java, Python, C, C++,
JavaScript, SQL, DBMS, algorithms, web development,
software engineering, AI, and library services.

LIBRARY CATALOGUE:
{catalogue}

Instructions:
1. Answer the user's actual question directly.

2. Use conversation history to understand follow-up questions.

3. If the user says "in Python, C, C++" after asking about Java classes and objects, explain the same concept in each requested language.

4. Answer general programming questions even if the catalogue has no relevant books.

5. Recommend catalogue books only when relevant.

6. Never invent catalogue titles, authors, or availability.

7. If no suitable catalogue book exists, explain this briefly and offer useful external resources where appropriate.

8. Explain concepts clearly for beginners and include examples.

9. Catalogue availability is sample data, not live inventory.

10. Recommend relevant catalogue books and external learning resources based on the user's question. Do not restrict recommendations to the catalogue when external resources would be more useful or when the catalogue has no suitable books.

11. Interpret short follow-up messages in the context of the previous conversation, including requests for resources, examples, explanations, or alternative programming languages.

12. When the user asks for learning materials, suggest resources appropriate to their subject and skill level, even if they do not explicitly ask for resources outside the catalogue.

13. Clearly distinguish books in the library catalogue from external websites, tutorials, courses, and other learning materials.

14. When recommending external resources, prioritize reliable official documentation and beginner-friendly free resources. Include a brief description and a URL when known.

15. When the user asks about multiple subjects, address each subject separately and recommend relevant learning resources for each one when useful. Do not invent resources or URLs.
"""

    try:
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            *valid_history,
            {
                "role": "user",
                "content": question
            }
        ]

        completion = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.3,
            max_completion_tokens=800
        )

        answer = completion.choices[0].message.content

        if not answer:
            answer = "Sorry, I couldn't generate a response."

        return jsonify({
            "answer": answer
        })

    except Exception as e:
        app.logger.exception("Groq API request failed")

        return jsonify({
            "answer": (
                "The AI request failed. Check the VS Code terminal "
                "for the error."
            )
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

