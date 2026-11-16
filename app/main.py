from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from uuid import uuid4

from app.routers import upload, budget, members, visitors, expenses, ticket_ai, summary, download
from app.session_cleanup import lifespan
from app import session_store

app = FastAPI(title="Budgetapp Scouts Sint-Joris", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.middleware("http")
async def session_middleware(request: Request, call_next):
    cookie_value = request.cookies.get(
        session_store.SESSION_COOKIE_NAME
    )
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
            secure=False, # True bij HTTPS
            samesite="lax",
            path="/",
            max_age=60 * 60 * 24 * 30,
        )
        return response
    finally:
        session_store.reset_session_id(token)

app.include_router(upload.router)
app.include_router(budget.router)
app.include_router(members.router)
app.include_router(visitors.router)
app.include_router(expenses.router)
app.include_router(ticket_ai.router)
app.include_router(summary.router)
app.include_router(download.router)
