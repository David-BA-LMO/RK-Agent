from fastapi import APIRouter, Depends, Body, Request
from fastapi.responses import StreamingResponse
from datetime import datetime
from pprint import pprint
import logging
import json
from typing import List, Dict, Any

from app.logic.router_chain import Router_chain
from app.logic.qa_chain import QAChain
from app.config import welcome_message
from app.schemas.requests import UserRequest
from app.dependencies.combined_dependencies import combined_dependencies
from app.dependencies.session_dependece import update_session
from app.dependencies.messages_dependence import update_messages
from app.models.session import SessionModel
from app.schemas.tools import QAToolModel
from app.logic.form_chain import Form_chain

logger = logging.getLogger(__name__)

router = APIRouter()

# ------ RUTA PARA MENSAJE DE BIENVENIDA ------
@router.get("/welcome-message") # Ruta para obtener el mensaje de bienvenida
async def get_welcome_message():
    return {"message": welcome_message}

# ------ RUTA PARA ENVIAR AL AGENTE IA ------
@router.post("/chat")
async def chat(
    request: Request,
    user_request: UserRequest = Body(...),
    context: dict = Depends(combined_dependencies),
    
) -> StreamingResponse:
    """Procesa el mensaje del usuario y genera una respuesta del chatbot"""

    # Agregar el nombre del usuario
    
    # ----CONTEXTO DE LA DEPENDENCIAS
    # Es necesario que 'context.get("messages_context")' como 'context.get("tools_data")' sean diccionarios para asegurar la mutabilidad
    try:
        session: SessionModel = context.get("session_context")
        history: List[Dict[str,Any]] = context.get("messages_context")
        username = session.name

        user_timestamp: datetime = user_request.timestamp
        type: str = user_request.type
        content = user_request.content
    
    except Exception as e:
            logging.error(f"Error retriving session objects in route /chat: {e}")
            raise Exception(f"Error retriving session objects in route /chat: {e}")

    # ----FUNCIÓN ASÍNCRONA GENERADORA DE RESPUESTAS
    async def response_stream():
        
        try:        
            print(f"SESSION CONTEXT 1: {session}")
            partial_answers = []
            bot_matadata = {}
            user_matadata = {}
            input = ""

            # ---- PROCESADO DE RESPUESTA CUANDO SE EXIGE LOCALIZACIÓN
            if type=="inm_localization_action":
                localization: tuple = content
                tools_data: dict = session.tools_data
                qa_tool: QAToolModel = tools_data.get("qa_tool")
                print(f"QA TOOL: {qa_tool}")
                qa_tool.inm_localization = localization
                user_matadata["type"] = type

                # Generación la respuesta del chatbot.
                async for partial_response in QAChain.direct_execute(input, qa_tool):

                    # las respuestas son diccionarios en formato {"type": type, "content": content}
                    yield json.dumps(partial_response) + "\n" # Importante el salto de línea para dividir las respuestas
                    if partial_response["type"] == "text":
                        partial_answers.append(partial_response["content"])
                    if partial_response["type"] == "metadata":
                        bot_matadata[partial_response["key"]] = partial_response["content"]

            # ---- PROCESADO DE RESPUESTA CUANDO SE PIDEN DATOS PERSONALES
            if type=="personal_form_action":
                personal_data: dict = content
                user_matadata["type"] = type

                # Generación la respuesta del chatbot.
                async for partial_response in Form_chain.execute(personal_data):

                    # las respuestas son diccionarios en formato {"type": type, "content": content}
                    yield json.dumps(partial_response) + "\n" # Importante el salto de línea para dividir las respuestas
                    if partial_response["type"] == "text":
                        partial_answers.append(partial_response["content"])
                    if partial_response["type"] == "metadata":
                        bot_matadata[partial_response["key"]] = partial_response["content"]

            # ---- PROCESADO DE RESPUESTA GENÉRICO PARA INPUT DE USUARIO
            if type=="text":
                input: str = content
                user_matadata["type"] = type
                        
                # Generación la respuesta del chatbot.
                async for partial_response in Router_chain.execute(input, session, history, username):

                    # las respuestas son diccionarios en formato {"type": type, "content": content}
                    yield json.dumps(partial_response) + "\n" # Importante el salto de línea para dividir las respuestas
                    if partial_response["type"] == "text":
                        partial_answers.append(partial_response["content"])
                    if partial_response["type"] == "metadata":
                        bot_matadata[partial_response["key"]] = partial_response["content"]
                    else:
                        pass

            print(f"BOT METADATA: {bot_matadata}")
            answer = "".join(partial_answers)        
            await update_session(session, request)
            await update_messages(user_timestamp, input, answer, user_matadata, bot_matadata, request)

        except Exception as e:
            logger.error(f"Error in /chat route: {e}")
            yield {"type": "text", "content": "Lo siento, ahora mismo no podemos atenderte."}

    return StreamingResponse(response_stream(), media_type="text/event-stream")