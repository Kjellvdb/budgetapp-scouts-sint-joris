# ⚡ BudgetApp – Scouts Sint-Joris Aalst

A financial management application to manage budgets, expenses and financial administration for weekends and camps.

The application simplifies financial tracking by combining Excel-based budget management with AI-powered receipt scanning and expense registration.

---

## ✨ Features

- **Authentication & Access Control** – Shared password login with HTTP-only session cookies and in-memory IP rate limiting against brute-force attempts.
- **Budget Management** – Create and manage budgets for weekends and camps.
- **Member Management** – Manage members participating in activities.
- **Visitor Management** – Keep track of visitors and additional participants.
- **Expense Tracking** – Register, organize and categorize expenses.
- **AI Receipt Scanning** – Automatically extract expense information from receipt images using AI.
- **Automatic Categorization** – Categorize expenses into general, alcohol and spirits.
- **Financial Overview** – View financial summaries and monitor expenses.
- **Excel Integration** – Import and export financial data using Excel files.
- **Session Management** – Maintain user sessions and automatically clean up inactive sessions.

## 🛠️ Tech Stack

| Technology  | Purpose                              |
| ----------- | ------------------------------------ |
| Python      | Backend development                  |
| FastAPI     | Web framework, middleware and API    |
| Jinja2      | HTML templating                      |
| Bootstrap 5 | Responsive UI components and styling |
| Uvicorn     | ASGI server                          |
| OpenPyXL    | Excel file processing                |
| Groq        | AI-powered receipt recognition       |
| Pillow      | Image processing                     |
| Pytest      | Automated testing                    |

## 📁 Project Structure

```text
budgetapp-scouts-sint-joris/
│
├── app/
│   ├── routers/
│   │   ├── upload.py
│   │   ├── budget.py
│   │   ├── members.py
│   │   ├── visitors.py
│   │   ├── expenses.py
│   │   ├── ticket_ai.py
│   │   ├── summary.py
│   │   └── download.py
│   │
│   ├── main.py
│   ├── session_store.py
│   ├── session_cleanup.py
│   └── ...
│
├── static/
├── templates/
│   ├── login.html
│   └── ...
│
├── tests/
│   ├── conftest.py
│   ├── test_login.py
│   └── ...
│
├── .github/
│   └── workflows/
│
├── requirements.txt
├── pytest.ini
└── readme.md
```

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/Kjellvdb/budgetapp-scouts-sint-joris.git
cd budgetapp-scouts-sint-joris
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate the environment:

**Windows (PowerShell):**

```powershell
.venv\Scripts\Activate.ps1
```

**Linux / macOS:**

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=qwen/qwen3.8-27b
PASSWORD=your_shared_team_password
```

Replace `your_groq_api_key` with your own Groq API key.

The `GROQ_MODEL` variable is optional and allows you to configure the AI model used for receipt scanning.

Replace `your_shared_team_password` with a secure password that will be used for authentication.

### 5. Start the application

```bash
uvicorn app.main:app --reload
```

The application will be available at:

**http://127.0.0.1:8000**

## 🔒 Security & Authentication

All application routes (except `/login` and `/static/*`) are protected by authentication middleware:

- Users authenticate with the shared `PASSWORD`.
- To prevent brute-force attacks, failed login attempts are tracked per client IP in memory. After **5 failed attempts**, the IP address is temporarily locked out for **15 minutes**.

## 🤖 AI-Powered Receipt Scanning

The application integrates the Groq API to extract financial information from receipt images.

The AI processing workflow:

1. Upload one or more receipt images.
2. Process and optimize the images for AI analysis.
3. Extract product names, quantities, prices and categories.
4. Retrieve relevant receipt information, including dates and totals.
5. Convert the extracted information into structured expense records.
6. Review the extracted expenses before using them in the budget.

The receipt scanning functionality supports multiple images per scan and provides processing updates while the AI analyzes the receipts.

## 🧪 Running Tests

The project uses Pytest for automated testing.

Run the test suite with:

```bash
pytest -v
```
