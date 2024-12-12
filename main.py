from fastapi import FastAPI, Depends, HTTPException, Response, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from uuid import uuid4, UUID
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from session_manager import SessionData, MongoDBBackend, CustomSessionVerifier, CookieBackend, SessionMiddleware
from src.router_chain import Router_chain
from pydantic import BaseModel, UUID4
from typing import Dict
import os
from dotenv import load_dotenv
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
from src.directories import welcome_message
import sys

current_script_path = os.path.abspath(__file__)
app_directory_path = os.path.dirname(os.path.dirname(current_script_path))
sys.path.append(app_directory_path)


# Configuración del logger con rotación (limitados). 20000 bytes y 5 archivos de respaldo máximos
file_handler  = RotatingFileHandler('logs/app.log', maxBytes=20000, backupCount=1)
# Configura el handler para la consola
console_handler = logging.StreamHandler()
logging.basicConfig(handlers=[file_handler, console_handler], level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Modelo de datos JSON que recibe _chat()
class ChatRequest(BaseModel):
    user_input: str

# Modelo de datos JSON que recibe _update_session()
class ChatUpdateRequest(BaseModel):
    user_input: str
    bot_response: str

# ------CLASE DE INICIO------
class MainApp:

    #------CONSTRUCTOR------
    def __init__(self):
        # Inicializar FastAPI
        self.app = FastAPI()

        # Ruta a la base de datos de MongoDB
        load_dotenv()
        self.MONGO_URI = os.getenv("MONGO_URI")
        self.client = AsyncIOMotorClient(self.MONGO_URI) # Motor de MongoDB para operaciones CRUD asincrónicas
        
        self.db = self.client.db # Base de datos de MongoDB. El nombre está definido en docker-compose.yml 
        self.sessions_collection = self.db.sessions # Colección para almacenar las sesiones de usuario
        self.session_router_chain = {}  # Aquí se guardarán las instancias de lógica del chatbot

        # Crear instancias del backend
        self.mongo_backend = MongoDBBackend(self.sessions_collection) #Backend de sesión
        self.cookie_backend = CookieBackend(cookie_name="session_id", secret_key=os.getenv("SECRET_KEY"), backend=self.mongo_backend) # Backend de cookies
        session_timeout_minutes = int(os.getenv("SESSION_TIMEOUT")) 
        self.session_timeout = timedelta(minutes=session_timeout_minutes) # Se define el tiempo de espera de la sesión en minutos

        # Verificador de sesión
        self.session_verifier = CustomSessionVerifier(backend=self.mongo_backend) # Verificador de sesión

        # Se monta el directorio de archivos estáticos
        self.app.mount("/static", StaticFiles(directory="static"), name="static")

        # Agregar el middleware de sesión
        self.app.add_middleware(
            SessionMiddleware,
            mongo_backend=self.mongo_backend,
            cookie_backend=self.cookie_backend,
            session_timeout=self.session_timeout
        )

        # Instancias de la lógica de la aplicación
        self.router_chain = Router_chain()

        # Registrar rutas
        self._register_routes()


    #------REGISTRO DE RUTAS------
    def _register_routes(self):
        @self.app.get("/", response_class=HTMLResponse)
        async def read_root():
            return self.get_html_response()
        
        @self.app.post("/start_session")
        async def start_session(response: Response):
            return await self._start_session(response)

        @self.app.post("/chat")
        async def chat(chat_request: ChatRequest, request: Request):
            return await self._chat(chat_request.user_input, request) # Interacción con el chatbot
        
        @self.app.post("/end_session")
        async def end_session(response: Response, session_id: UUID = Depends(self.cookie_backend.read)):
            return await self._end_session(response, session_id)
        
        @self.app.get("/welcome-message") # Ruta para obtener el mensaje de bienvenida
        async def get_welcome_message():
            return {"message": welcome_message}


    #------RESPUESTA HTML------ 
    def get_html_response(self):
        index_path = Path("templates/index.html")
        if index_path.exists():
            return index_path.read_text(encoding="utf-8")
        else:
            return HTMLResponse(content="<h1>404: File Not Found</h1>", status_code=404)


    # -----INICIO DE SESIÓN------
    async def _start_session(self, response: Response) -> Dict[str, str]:
        # Crear una nueva sesión con un ID único
        session_id = uuid4()
        current_time = datetime.now(timezone.utc) # Se obtiene la hora actual
        session_data = SessionData(
            session_id=str(session_id), # session_id único para la sesión
            history=[], # Historial de conversacion
            qa_data = {  # Almacena las propiedades de sesión en la herramienta QA incluidos los pares input-SQL
                "sql_queries": [], 
                "missing_fields": [],
                "last_query": None, 
                "new_search": True,
                "result": ""
            }, 
            last_active=current_time, # Establece el instante de inicio de la sesión
            expiration_time=current_time + self.session_timeout # Establece el tiempo de expiración de la sesión
        )
        await self.mongo_backend.create(session_data) # Creamos la sesión en la base de datos
        self.cookie_backend.write(response, session_id) # Esta función adjuntar la cookie al encabezado HTTP enviada al cliente
        logger.info("INFO: New session with id:" + str(session_id))
        return {"session_id": str(session_id)} # Se recibe el id_session en el lado del cliente en formato JSON


    #------ENVÍO DE MENSAJES AL CHATBOT------
    async def _chat(self, user_input: str, request: Request) -> StreamingResponse:

        session_id = request.cookies.get("session_id")
        logger.info(f"New message from session with id: {session_id}")

        # Verificar si la sesión existe en la colección de sesiones del backend de MongoDB
        try:
            session = request.state.session
        except HTTPException as e:
            logger.error(f"We cannot retrive session with id: {session_id}"+ str(e))
            raise HTTPException(status_code=404, detail=f"Session not found or expired: {e}")

        # Generador de respuestas del chatbot en tiempo real
        async def response_stream():
            try:
                complete_response = ""
                # Generación la respuesta del chatbot. Es posible que en cada llamada se generen múltiples mensajes
                async for partial_response in self.router_chain.execute(user_input, session):
                    complete_response += partial_response
                    yield partial_response
            except Exception as e:
                logger.error(f"Logic execute failed {e}")
                yield "ERROR: Logic failed: " + str(e)
            await self.update_session(session, user_input, complete_response)

        return StreamingResponse(response_stream(), media_type="text/plain")

    
    #------ACTUALIZACIÓN DE LA SESIÓN------
    async def update_session(self, session: SessionData, input:str, complete_response: str):
        
        # Actualización de la sesión después de completar la generación de la respuesta
        try:
            # Dentro del objeto de datos de la sesión, se añade la conversación.
            conversation_entry = {
                "user": input, 
                "bot": complete_response, 
                "timestamp": datetime.now(timezone.utc)
            }
            session.history.append(conversation_entry)
            session.last_active = datetime.now(timezone.utc) # Se actualiza el instante de la última interacción
            session.expiration_time = session.last_active + self.session_timeout
            await self.mongo_backend.update(session.session_id, session)
        except Exception as e:
            logger.error(f"Session update failed: {e}")
            return "ERROR: Session update failed: " + str(e)    


    #------CIERRE DE SESIÓN------  
    async def _end_session(self, response: Response, session_id: UUID):
        try:
            await self.mongo_backend.delete(session_id) # Eliminamos la sesión del backend
            self.cookie_backend.delete(response) # Eliminar la cookie de la respuesta
            logger.info("INFO: Session removed with id:" + str(session_id))
        except Exception as e:
            logger.error(f"Failed to end session with id: {session_id}, error: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to end session due to an internal error")
        


# Iniciar la aplicación
main_app = MainApp()
app = main_app.app


