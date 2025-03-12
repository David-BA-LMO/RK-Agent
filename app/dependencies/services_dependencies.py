from fastapi import Request, HTTPException
import logging

from app.services.sessions_service import SessionService
from app.services.messages_service import MessagesService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

def get_session_service(request: Request) -> SessionService:
    """Obtiene la instancia de SessionService desde el estado de la app"""

    try:
        session_service: SessionService = getattr(request.app.state, "sessions_service", None)
    
        if session_service is None:
            raise AttributeError("sessions service not found in app state")

        return session_service

    except AttributeError as e:
        logger.error(f"Sessions service not found in app state: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error while retrieving session service: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
def get_messages_service(request: Request) -> MessagesService:
    """Obtiene la instancia de MessagesService desde el estado de la app"""

    try:
        messages_service: MessagesService = getattr(request.app.state, "messages_service", None)
        
        if messages_service is None:
            raise AttributeError("Messages service not found in app state")
        return messages_service
    
    except AttributeError as e:
        logger.error(f"Messages service not found in app state: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error while retrieving messages service: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
def get_users_service(request: Request) -> UserService:
    """Obtiene la instancia de UserService desde el estado de la app"""

    try:
        users_service: UserService = getattr(request.app.state, "users_service", None)
        if users_service is None:
            raise AttributeError("Users service not found in app state")
        
        return users_service
    
    except AttributeError as e:
        logger.error(f"Users service not found in app state: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error while retrieving users service: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")