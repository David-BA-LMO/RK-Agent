# Esta clase sirve para combinar las diversas dependencias necesarias en una misma ruta. Dichas dependencias recuperan un objeto de sesión
# y devuelven un diccionario por separado. Estos se combinan en esta esta dependencia, que cede el control a la ruta a través de un yield.
# En cuanto la ejecución de esta acabe, el diccionario retorna a cada una de las dependencias que se encargarán de las actualizaciones. 

from fastapi import Depends
import logging
from typing import List

from app.dependencies.session_dependece import manage_session
from app.dependencies.messages_dependence import manage_messages
from app.models.session import SessionModel
from app.schemas.message import MessageModel

logger = logging.getLogger(__name__)

async def combined_dependencies(
    session_context: SessionModel = Depends(manage_session),
    messages_context: List[MessageModel] = Depends(manage_messages)
):                                
    try:
        if not isinstance(session_context, SessionModel):
            raise ValueError(f"Session object 'tools_data' must be a Pydantic SessionModel, but instead {type(session_context).__name__} ")
        if not isinstance(messages_context, list) or not all(isinstance(msg, MessageModel) for msg in messages_context):
            raise ValueError(f"Session object 'messages' must be a list of Pydantic MessagesModel, but instead {type(messages_context).__name__} ")
    
        return {
            "session_context": session_context,
            "messages_context": messages_context
        }

    except Exception as e:
        logging.error(f"Error passing session objects: {e}")
        raise Exception(f"Error passing session objects: {e}")