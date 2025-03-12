from typing import List, Any
from fastapi import Request, HTTPException, Depends
import logging
from datetime import datetime, timezone

from app.dependencies.services_dependencies import get_messages_service
from app.services.messages_service import MessagesService
from app.models.messages import MessagesModel
from app.schemas.message import MessageModel

logger = logging.getLogger(__name__)

# ------RECUPERACIÓN DE LOS MENSAJES DE LA CONSULTA------
async def get_session_id(request: Request) -> str:
    """ Recupera y valida el session_id desde las cookies de la solicitud."""
    
    session_id = getattr(request.state, "session", None)
    if not session_id:
        logging.warning("Session ID not provided in request at messages dependence")
        raise HTTPException(status_code=401, detail="Session ID is missing")

    return str(session_id)

# ------GESTIÓN DE LOS MENSAJES DE CONSULTA------
async def manage_messages(request: Request, messages_service: MessagesService = Depends(get_messages_service)) -> List[MessageModel]:
    """ Dependencia que recupera y valida los mensajes desde MongoDB.
        Recesita recuperar el servicio de mensajes desde la app.       
    """
    messages = {}

    num_last_messages = 4

    try:        
        #------COMPROBAMOS EL ID DE SESIÓN
        id: str = await get_session_id(request)

        #------COMPROBAMOS LA SESIÓN
        messages: MessagesModel = await messages_service.get_messages(id)
        if not messages:
            logging.warning(f"Messages not found in MongoDB.")
            raise HTTPException(status_code=401, detail="Messages not found in MongoDB.")
        
        last_messages: List[MessageModel] = await messages_service.get_last_messages(messages, num_last_messages) or []

        #------ENTREGAMOS EL CONTROL AL ENDPOINT
        return [{"user": msg.content} if not msg.is_bot else {"bot": msg.content, "tool": msg.metadata.get("tool", None) } for msg in last_messages]
    
    except Exception as e:
        logging.error(f"Error in messages dependence: {e}")
        raise HTTPException(status_code=500, detail=f"Error in messages dependence: {e}")

# ------ACTUALIZACIÓN DE LOS MENSAJES ------        
async def update_messages(
        user_timestamp: datetime, 
        user_content: str, 
        bot_content: str, 
        user_metadata: dict, 
        bot_metadata: dict, 
        request: Request):

        try:
            if not isinstance(bot_metadata, dict):
                bot_metadata = {}
            if not isinstance(user_metadata, dict):
                user_metadata = {}
                
            messages_service: MessagesService = get_messages_service(request)
            #------COMPROBAMOS EL ID DE SESIÓN
            id: str = await get_session_id(request)
            
            #------CREAMOS LOS MENSAJES
            # Mensaje de usuario
            user_message = MessageModel(
                content = user_content,
                is_bot = False,
                timestamp = user_timestamp,
                metadata = user_metadata
            )

            # Mensaje del bot
            bot_message = MessageModel(
                content = bot_content,
                is_bot = True,
                timestamp = datetime.now(timezone.utc),
                metadata = bot_metadata
            )
            await messages_service.set_messages(id, user_message, bot_message)

        except Exception as e:
            logging.error(f"Error at messages registry update: {e}")
            raise HTTPException(status_code=500, detail=f"Error at messages registry update: {e}")
    