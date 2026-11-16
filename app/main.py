from dotenv import load_dotenv
load_dotenv()
from uuid import uuid4
from collections import defaultdict
from fastapi import FastAPI, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse

import os
import time

from app.routers import upload, budget, members, visitors, expenses, ticket_ai, summary, download
from app.session_cleanup import lifespan
from app.templates import templates
from app import session_store

PASSWORD = os.getenv("PASSWORD", None)
AUTH_COOKIE_NAME = "scouts_auth"
MAX_ATTEMPTS = 5
LOCKOUT_TIME = 900

app = FastAPI(title="Budgetapp Scouts Sint-Joris", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

failed_login_attempts = defaultdict(lambda: {"attempts": 0, "locked_until": 0.0})

@app.middleware("http")
async def check_auth(request: Request, call_next):
    path = request.url.path
    if path == "/login" or path.startswith("/static"):
        return await call_next(request)
    if request.cookies.get(AUTH_COOKIE_NAME) != "authenticated":
        return RedirectResponse(url="/login", status_code=303)
    return await call_next(request)

@app.middleware("http")
async def session_middleware(request: Request, call_next):
    cookie_value = request.cookies.get(session_store.SESSION_COOKIE_NAME)
    try:
        session_id = session_store.validate_session_id(cookie_value)
    except ValueError:
        session_id = str(uuid4())
    token = session_store.set_session_id(session_id)
    try:
        session_store.touch_current_session()
        response = await call_next(request)
        response.set_cookie(
            key=session_store.SESSION_COOKIE_NAME,
            value=session_id,
            httponly=True,
            secure=False,
            samesite="lax",
            path="/",
            max_age=60 * 60 * 24 * 30,
        )
        return response
    finally:
        session_store.reset_session_id(token)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = None):
    return templates.TemplateResponse(request, "login.html", {"error": error})

@app.post("/login")
def login_action(request: Request, password: str = Form(...)):
    client_ip = request.client.host
    current_time = time.time()
    tracker = failed_login_attempts[client_ip]
    if current_time < tracker["locked_until"]:
        remaining_minutes = int((tracker["locked_until"] - current_time) / 60) + 1
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": f"Te veel mislukte pogingen. Probeer het over {remaining_minutes} minuten opnieuw."}
        )

    if password != PASSWORD:
        tracker["attempts"] += 1
        if tracker["attempts"] >= MAX_ATTEMPTS:
            tracker["locked_until"] = current_time + LOCKOUT_TIME
            tracker["attempts"] = 0 # Reset teller voor de volgende ronde
            return templates.TemplateResponse(
                request, 
                "login.html", 
                {"error": "Te veel onjuiste pogingen. Je IP is tijdelijk geblokkeerd voor 15 minuten."}
            )
        return RedirectResponse(url="/login?error=1", status_code=303)
    failed_login_attempts.pop(client_ip, None)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value="authenticated",
        httponly=True,
        secure=os.getenv("WEBSITE_HOSTNAME") is not None,
        samesite="lax",
        path="/",
        max_age=60 * 60 * 24 * 30
    )
    return response

app.include_router(upload.router)
app.include_router(budget.router)
app.include_router(members.router)
app.include_router(visitors.router)
app.include_router(expenses.router)
app.include_router(ticket_ai.router)
app.include_router(summary.router)
app.include_router(download.router)
