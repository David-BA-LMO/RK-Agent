from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime, timezone
import asyncio
from pprint import pprint
import logging
import os
import json
from typing import List, Dict, Any

from app.logic.router_chain import Router_chain
from app.dependencies.combined_dependencies import combined_dependencies
from app.dependencies.session_dependece import update_session
from app.dependencies.messages_dependence import update_messages
from app.models.session import SessionModel
from app.utils.general_utilities import is_valid_twilio_media

logger = logging.getLogger(__name__)

router = APIRouter()

account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
from_phone =os.getenv('TWILIO_TO_NUMBER')

# ------ RUTA PARA MENSAJES DE WHATSAPP ------
@router.post("/whats-message")
async def chat(
    request: Request,
    background_tasks: BackgroundTasks,
    context: dict = Depends(combined_dependencies) 
):
    """Webhook que procesa el mensaje del usuario y genera una respuesta del chatbot para WhatsApp""" 
    chatbot_response = ""
    #client = request.app.state.twilio_client
    partial_answers = []
    alt_content = []

    
    # ----CONTEXTO DE LA DEPENDENCIAS
    # Es necesario que 'context.get("messages_context")' como 'context.get("tools_data")' sean diccionarios para asegurar la mutabilidad
    try:
        session: SessionModel = context.get("session_context")
        history: List[Dict[str,Any]] = context.get("messages_context")

        user_timestamp: datetime = datetime.now(timezone.utc)
        
        if not hasattr(request.state, "body"):
             raise ValueError(f"Request body not found in request atributtes")
        
        input = request.state.body
        user_name = request.state.user_name
        user_phone = request.state.phone

        user_metada = {"type": "text"}
        bot_matadata = {}
        
        input.strip()
    
    except Exception as e:
            logging.error(f"Error retriving session objects in route /whats-message: {e}")
            raise Exception(f"Error retriving session objects in route /whats-message: {e}")

    # ----GENERACIÓN ASÍNCRONA DE RESPUESTA DEL CHATBOT
    try:        
        async for partial_response in Router_chain.execute(input, session, history, user_name):

            # las respuestas son diccionarios en formato {"type": type, "content": content}
            json.dumps(partial_response) + "\n" # Importante el salto de línea para dividir las respuestas
            if partial_response["type"] == "text":
                partial_answers.append(partial_response["content"])
            if partial_response["type"] == "metadata":
                bot_matadata: dict = partial_response["content"]
            if partial_response["type"] == "image":
                alt_content.append(partial_response)
            if partial_response["type"] == "url":
                alt_content.append(partial_response)
            if partial_response["type"] == "function" and partial_response["content"] == "generalPresentation":
                alt_content = order_generic_presentation(partial_response["input"])

        #----ACTUALIZACIÓN DE OBJETOS DE SESIÓN
        chatbot_response = "".join(partial_answers)
        await update_session(session, request)
        await update_messages(user_timestamp, input, chatbot_response, user_metada, bot_matadata, request)

        #----ENVIO DEL MENSAJE A TWILIO
        response = MessagingResponse()

        # Mensajes con texto
        msg_main = response.message()
        msg_main.body(chatbot_response)

        if alt_content:
            background_tasks.add_task(send_whatsapp_message, user_phone, alt_content)
        
        print(f"RESPUESTA XML: {response}")

        return Response(str(response), media_type="application/xml")
    
    except Exception as e:
        response = MessagingResponse()
        response.message("Lo siento, ahora mismo no podemos atenderte.")
        return Response(str(response), media_type="application/xml")
    

async def send_whatsapp_message(user_phone: str, messages: List[Dict]):

    await asyncio.sleep(10)

    try:
        client = Client(account_sid, auth_token)
        print(f"TWILIO PHONE: {from_phone}")
        print(f"USER PHONE: {user_phone}")
        num_images = 0
        max_images = 6

        for msg in messages:
            # Si el mensaje es solo texto
            if msg["type"] == "image":
                message = client.messages.create(
                    to = user_phone,
                    from_ = os.getenv("TWILIO_TO_NUMBER"),
                    media_url = msg["content"]
                )
            # Si el mensaje es solo una imagen
            elif msg["type"] == "url":
                if num_images<max_images:
                    url = msg["content"]
                    if not is_valid_twilio_media(url):
                        url = "https://www.agenciaiglesias.com/wp-content/uploads/2020/04/RK-IGLESIAS-H-500x123-1.png"

                    message = client.messages.create(
                        to = user_phone,
                        from_ = os.getenv("TWILIO_TO_NUMBER"),
                        body = url
                    )
                    num_images+=1
            # Si el mensaje es texto e imagen
            elif msg["type"]=="data":
                url = msg["main_image"]
                if not is_valid_twilio_media(url):
                    url = "https://www.agenciaiglesias.com/wp-content/uploads/2020/04/RK-IGLESIAS-H-500x123-1.png"

                message = client.messages.create(
                    to = user_phone,
                    from_= os.getenv("TWILIO_TO_NUMBER"),
                    body = msg["main_text"],
                    media_url= url
                )

            while True:
                message_status = client.messages(message.sid).fetch().status
                if message_status in ["delivered", "sent", "failed"]:
                    break
                await asyncio.sleep(0.5)

    except Exception as e:
        logger.error(f"An error ocurring in background messages: {e}")
        raise Exception(f"An error ocurring in background messages: {e}")


def order_generic_presentation(present_inm: List[Dict]) -> List[Dict]:
    """ Función para dar orden de envio de datos diversos que combinan imagenes, texto y URLs"""
    ordered_data = []
    for inm in present_inm:
        content_dict = {
            "type": "data",
            "main_text": present_format(inm["data_inm"]),
            "main_image": inm.get("url_media")
        }
        ordered_data.append(content_dict)
        ordered_data.append({"type": "url", "content": inm.get("url", "")})
    return ordered_data
    

def present_format(data_inm: Dict) -> str:
    """ Función para devolver un formato de datos para la presentación preliminar de inmuebles"""

    direccion: str = data_inm.get("Direccion", " ").strip()
    barrio: str = data_inm.get("Barrio", " ").strip()
    poblacion: str = data_inm.get("Poblacion", " ").strip()
    provincia: str = data_inm.get("Provincia", " ").strip()
    num_dormitorios: str = data_inm.get("NumDormitorios", "?")
    if num_dormitorios is None or str(num_dormitorios).lower() == "none":
        num_dormitorios = "?"
    num_aseos: str = data_inm.get("NumAseos", "?")
    if num_aseos is None or str(num_aseos).lower() == "none":
        num_aseos = "?"
    metros_utiles: str = data_inm.get("Metros_Utiles", "?")
    if metros_utiles is None or str(metros_utiles).lower() == "none":
        metros_utiles: str = data_inm.get("Metros_Construidos", "?")
    if metros_utiles is None or str(metros_utiles).lower() == "none":
        metros_utiles = "?"
    precio: str = data_inm.get("Precio", "Precio no disponible")
    if precio is None or str(precio).lower() == "none":
        precio = "?"

    # Construcción del texto de presentación
    presentation = "\n".join(filter(None, [
        f"{direccion}, {barrio}\n"
        f"{poblacion}, {provincia}\n"
        f"🛏 {num_dormitorios} |  🚽 {num_aseos} |  📏 {metros_utiles}m²\n",
        f"💰 *{precio}€*\n"
    ]))

    return presentation