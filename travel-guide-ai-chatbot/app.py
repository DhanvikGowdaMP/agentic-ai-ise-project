import os
import markdown

from flask import Flask, render_template, request
from dotenv import load_dotenv
from groq import Groq

# Load API key from .env
load_dotenv()

app = Flask(__name__)

api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key) if api_key else None

MODEL_NAME = "openai/gpt-oss-20b"


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/plan", methods=["POST"])
def plan():
    # Read form data
    destination = request.form.get("destination", "").strip()
    days_text = request.form.get("days", "").strip()
    budget_text = request.form.get("budget", "").strip()
    interests = request.form.get("interests", "").strip()

    # Validate required fields
    if not all([destination, days_text, budget_text, interests]):
        return "Please complete all fields.", 400

    try:
        days = int(days_text)
        budget = float(budget_text)

        if not 1 <= days <= 30:
            return "Duration must be between 1 and 30 days.", 400

        if budget <= 0:
            return "Budget must be greater than zero.", 400

    except ValueError:
        return "Please enter valid numbers for days and budget.", 400

    if client is None:
        app.logger.error("GROQ_API_KEY is missing.")
        return "Groq API key is missing. Check your .env file.", 500

    # Short, structured itinerary prompt
    prompt = f"""
Create a concise travel itinerary.

Destination: {destination}
Duration: EXACTLY {days} days
Total budget: Rs. {budget:.0f}
Interests: {interests}

STRICT RULES:
1. Generate exactly {days} days.
2. Use short bullet points, not long paragraphs.
3. Suggest up to 3 activities per day.
4. Do not invent attractions, opening hours, entry fees,
   travel distances, schedules, or accommodation prices.
5. Do not assume accommodation is free.
6. The starting city is unknown. Exclude intercity transport
   from the budget and clearly state this.
7. Label uncertain costs as estimates.
8. Keep the estimated budget within Rs. {budget:.0f}
   when reasonably possible. Do not hide necessary expenses.
9. If reliable information is insufficient, say so.
10. Finish with no more than 3 short travel tips.
11. No lengthy introduction or conclusion.

FORMAT:

# {destination} Travel Plan

## Day 1: [Heading]
- Activity
- Activity
- Activity

Repeat for exactly {days} days.

## Budget Summary
- Accommodation: estimate or unknown
- Food: estimate
- Local transport and activities: estimate
- Intercity transport: excluded
- Total estimated cost: estimate or unavailable

## Travel Tips
- Tip
- Tip
- Tip

Never present an estimate as a verified price.
"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise travel planning assistant. "
                        "Follow the requested duration and format. "
                        "Accuracy is more important than completeness. "
                        "Never fabricate facts to fill gaps."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.2,
            max_completion_tokens=2500,
            reasoning_effort="low",
            reasoning_format="hidden",
        )

        choice = response.choices[0]
        message = choice.message
        itinerary = message.content

        # Diagnose empty responses
        if not itinerary or not itinerary.strip():
            app.logger.error(
                "Groq returned empty content. Finish reason: %s",
                choice.finish_reason,
            )
            return (
                "The AI returned no itinerary text. "
                "Check the VS Code terminal for diagnostic details.",
                502,
            )
        itinerary_html = markdown.markdown(
            itinerary.strip(),
            extensions=["extra", "nl2br"]
        )

        return render_template(
            "result.html",
            destination=destination,
            itinerary_html=itinerary_html,
        )

    except Exception:
        app.logger.exception("Groq itinerary generation failed")
        return (
            "Unable to generate the itinerary. Check the VS Code "
            "terminal for the error details.",
            502,
        )


if __name__ == "__main__":
    app.run(debug=True)