from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from uuid import uuid4, UUID
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from session_manager import SessionData, MongoDBBackend, CustomSessionVerifier, CookieBackend
from src.router_chain import Router_chain
from pydantic import BaseModel, UUID4
import os
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging
import asyncio
from logging.handlers import RotatingFileHandler
from src.directories import welcome_message


 # Modelo de datos JSON que recibe _chat() y _end_session()
class ChatRequest(BaseModel):
    user_input: str
    session_id: UUID4



# Configuración del logger con rotación (limitados). 20000 bytes y 5 archivos de respaldo máximos
file_handler  = RotatingFileHandler('app.log', maxBytes=20000, backupCount=1)
# Configura el handler para la consola
console_handler = logging.StreamHandler()
logging.basicConfig(handlers=[file_handler, console_handler], level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ------CLASE DE INICIO------
class MainApp:

    #------CONSTRUCTOR------
    def __init__(self):
        # Inicializar FastAPI
        self.app = FastAPI()
        # Ruta a la base de datos de MongoDB
        load_dotenv()
        self.MONGO_URI = os.getenv("MONGO_URI")
        if self.MONGO_URI is None or self.MONGO_URI == "":
            print("MONGO_URI is not founded")
            exit(1)
        self.client = AsyncIOMotorClient(self.MONGO_URI) # Motor de MongoDB para operaciones CRUD asincrónicas
        
        self.db = self.client.db # Base de datos de MongoDB. El nombre está definido en docker-compose.yml 
        self.sessions_collection = self.db.sessions # Colección para almacenar las sesiones de usuario
        self.session_router_chain = {}  # Aquí se guardarán las instancias de lógica del chatbot

        # Crear instancias del backend y frontend
        self.mongo_backend = MongoDBBackend(self.sessions_collection) #Backend de sesión
        self.cookie_backend = CookieBackend(cookie_name="session_id", secret_key=os.getenv("SECRET_KEY", "supersecretkey"), backend=self.mongo_backend) # Backend de cookies
        
        # Se define el tiempo de espera de la sesión en minutos
        session_timeout_minutes = int(os.getenv("SESSION_TIMEOUT"))
        self.session_timeout = timedelta(minutes=session_timeout_minutes)

        # Verificar si la sesión ha expirado
        self.session_verifier = CustomSessionVerifier(backend=self.mongo_backend ) # Verificador de sesión

        self.app.mount("/static", StaticFiles(directory="static"), name="static") # Se monta el directorio de archivos estáticos

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
        async def chat(request: ChatRequest, response: Response):
            if not await self.session_verifier.verify_session(str(request.session_id)): # Verificación de sesión
                raise HTTPException(status_code=404, detail="Session not found or expired")
            return await self._chat(response, request.user_input, request.session_id) # Interacción con el chatbot

        @self.app.post("/end_session")
        async def end_session(response: Response, session_id: UUID = Depends(self.cookie_backend.read)):
            return await self._end_session(response, str(session_id))
        
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
    async def _start_session(self, response: Response):
        # Crear una nueva sesión con un ID único
        session_id = uuid4()
        current_time = datetime.now(timezone.utc) # Se obtiene la hora actual
        session_data = SessionData(
            session_id=str(session_id), # se crea una sesión con un ID único
            data={"conversation": []},  # data es un diccionario. Iniciamos un elemento "conversation" que es una lista (la cual almacenará diccionarios)
            last_active=datetime.now(timezone.utc), # Establece el instante de inicio de la sesión
            expiration_time=current_time + self.session_timeout # Establece el tiempo de expiración de la sesión
        )
        session_logic = Router_chain() # Crear la lógica del chatbot para la sesión
        self.session_router_chain[str(session_id)] = session_logic # Se almacena en un diccionario con el ID de la sesión como clave
        
        await self.mongo_backend.create(str(session_id), session_data) # Creamos la sesión en la base de datos
        self.cookie_backend.write(response, str(session_id)) # Esta función utiliza el objeto Response para adjuntar la cookie al encabezado HTTP enviada al cliente
        logger.info("Session started with id: " + str(session_id))
        return {"session_id": str(session_id)}


    #------MANEJO DE INTERACCIÓNES USUARIO-CHATBOT------
    # Utiliza la cookie del cliente para identificar la sesión
    async def _chat(self, response: Response, user_input: str, session_id: UUID):

        # Verificar si la sesión existe en la colección de sesiones del backend de MongoDB
        session = await self.mongo_backend.read(str(session_id)) # Se obtiene la sesión con el ID proporcionado
        if not session:
            logger.info("ERROR: Session not found" + {str(e)})
            raise HTTPException(status_code=404, detail="Session not found")
        else:
            logger.info("Session verified with id: " + str(session_id))
        
        # Recuperar la instancia de Router_chain, que contiene las cadenas de enrutamiento del chatbot
        router_chain = self.session_router_chain.get(str(session_id))
        if not router_chain:
            logger.info("ERROR: Session logic not found:" + {str(e)})
            raise HTTPException(status_code=500, detail="Session logic not found")
        else:
            logger.info("Session logic found with id: " + str(session_id))

        # EJECUCIÓN DEL CHATBOT
        chatbot_response = None
        try:
            chatbot_response = router_chain.execute_chatbot(user_input) 
        except Exception as e:
            logger.info("ERROR: Logic execute failed", {e})
            raise HTTPException(status_code=500, detail="Logic failed: " + str(e))
        
        # Actualización de la sesión
        try:
            conversation_entry = {"user": user_input, "bot": chatbot_response, "timestamp": datetime.now(timezone.utc)}
            # Dentro del objeto de datos de la sesión, se añade la conversación. Cada entrada es un diccionario con el mensaje del usuario, la respuesta del chatbot y la marca de tiempo
            session.data["conversation"].append(conversation_entry)
            # Se actualiza el instante de la última interacción
            session.last_active = datetime.now(timezone.utc)
            session.expiration_time = session.last_active + self.session_timeout
            await self.mongo_backend.update(str(session_id), session)
        except Exception as e:
            logger.info("ERROR: Session update failed", {e})
            raise HTTPException(status_code=500, detail="Session update failed: " + str(e))

        # Función de generador para enviar la respuesta secuencialmente
        async def response_stream():
            # Iterar sobre la respuesta en pasos de dos caracteres
            for i in range(0, len(chatbot_response), 2):
                # Obtener un par de caracteres
                chunk = chatbot_response[i:i+2]
                # Enviar el par de caracteres seguido de un espacio
                yield chunk + ' '
                # Simular la pausa entre envíos
                await asyncio.sleep(0.1)

        return StreamingResponse(response_stream(), media_type="text/plain")


    #------CIERRE DE SESIÓN------  
    async def _end_session(self, response: Response, session_id: UUID):
        # Terminar la sesión actual
        await self.mongo_backend.delete(str(session_id))
        self.cookie_backend.delete(response)
        self.session_router_chain.pop(str(session_id), None)
        logger.info("Session stopped with id: " + str(session_id))
        return {"detail": "Session ended"}

# Iniciar la aplicación
main_app = MainApp()
app = main_app.app
