
const bookResults = document.getElementById("book-results");
const resultCount = document.getElementById("result-count");
const searchForm = document.getElementById("search-form");
const searchInput = document.getElementById("book-search");

const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatMessages = document.getElementById("chat-messages");
const sendButton = document.getElementById("send-button");

// Store recent conversation messages.
const conversationHistory = [];
const MAX_HISTORY_MESSAGES = 10;

function createElement(tag, className, text = "") {
    const element = document.createElement(tag);
    element.className = className;
    element.textContent = text;
    return element;
}

function createBookCard(book) {
    const card = createElement("article", "book-card");

    card.append(
        createElement("h4", "", book.title),
        createElement("p", "", `Author: ${book.author}`),
        createElement("span", "category", book.category),
        createElement("p", "", book.description)
    );

    const available = book.available_copies > 0;

    card.append(
        createElement(
            "div",
            `availability ${available ? "available" : "unavailable"}`,
            available
                ? `${book.available_copies} copies available`
                : "Currently unavailable"
        )
    );

    return card;
}

async function loadBooks(query = "") {
    bookResults.replaceChildren();
    bookResults.append(
        createElement("p", "empty-state", "Loading books...")
    );

    try {
        const response = await fetch(
            `/api/books?q=${encodeURIComponent(query)}`
        );

        if (!response.ok) {
            throw new Error("Unable to load books.");
        }

        const books = await response.json();
        bookResults.replaceChildren();

        resultCount.textContent = `${books.length} book(s) found`;

        if (books.length === 0) {
            bookResults.append(
                createElement(
                    "p",
                    "empty-state",
                    "No books found. Try another search."
                )
            );
            return;
        }

        books.forEach(book => {
            bookResults.append(createBookCard(book));
        });
    } catch (error) {
        bookResults.replaceChildren();
        bookResults.append(
            createElement(
                "p",
                "empty-state",
                "Could not load books. Check that Flask is running."
            )
        );
        resultCount.textContent = "Error";
    }
}

function addMessage(text, type) {
    const message = createElement(
        "div",
        `message ${type}-message`,
        text
    );

    chatMessages.append(message);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function sendQuestion(question) {
    addMessage(question, "user");

    const loading = createElement(
        "div",
        "message assistant-message",
        "SmartLib AI is thinking..."
    );

    chatMessages.append(loading);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    sendButton.disabled = true;

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: question,
                history: conversationHistory
            })
        });

        const data = await response.json();
        loading.remove();

        if (!response.ok) {
            throw new Error(
                data.error || data.answer || "The request failed."
            );
        }

        addMessage(data.answer, "assistant");

        // Store the exchange only after a successful response.
        conversationHistory.push(
            { role: "user", content: question },
            { role: "assistant", content: data.answer }
        );

        // Keep only the most recent 10 messages.
        if (conversationHistory.length > MAX_HISTORY_MESSAGES) {
            conversationHistory.splice(
                0,
                conversationHistory.length - MAX_HISTORY_MESSAGES
            );
        }
    } catch (error) {
        loading.remove();

        addMessage(
            error.message || "Unable to contact the AI assistant.",
            "assistant"
        );
    } finally {
        sendButton.disabled = false;
        chatInput.focus();
    }
}

searchForm.addEventListener("submit", event => {
    event.preventDefault();
    loadBooks(searchInput.value.trim());
});

chatForm.addEventListener("submit", event => {
    event.preventDefault();

    const question = chatInput.value.trim();

    if (!question || sendButton.disabled) {
        return;
    }

    chatInput.value = "";
    sendQuestion(question);
});

loadBooks();
