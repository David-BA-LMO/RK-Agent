from fastapi import APIRouter
from app.routers import chat, session, ui, health, whatsapp

def main_router() -> APIRouter:
    router = APIRouter()

    router.include_router(ui.router, tags=["Interface"])
    router.include_router(session.router, tags=["Login-Logout"])
    router.include_router(chat.router, tags=["Chat"])
    router.include_router(whatsapp.router, tags=["Whatsapp-Chat"])
    router.include_router(health.router, tags=["Health"])
    return router