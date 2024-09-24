from pydantic import BaseModel
from datetime import datetime, timezone
from fastapi_sessions.session_verifier import SessionVerifier
from fastapi_sessions.backends.session_backend import SessionBackend
from starlette.middleware.base import BaseHTTPMiddleware
from uuid import UUID
from typing import List, Optional, Dict
from fastapi import HTTPException, Request, Response
from fastapi import Response
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# Clase Backend de sesión para almacenar y recuperar datos de sesión. Todos las instancias de objetos de sesión deben ser subclases de BaseModel
class SessionData(BaseModel):
    session_id: str
    history: Optional[List[Dict]] = [] # Almacena las conversaciones
    qa_data: Optional[Dict] = [] # Almacena las propiedades de sesión en la herramienta QA incluidos los pares input-SQL
    last_active: datetime # Marca de tiempo de la última interacción
    expiration_time: datetime  # Marca de tiempo de expiración de la sesión


# Implementación de la clase MongoDBBackend con el backend de sesión y la colección de sesiones
class MongoDBBackend(SessionBackend):
    def __init__(self, collection):
        self.collection = collection
    # Métodos CRUD para sesiones
    async def create(self, data: SessionData):
        try:
            await self.collection.insert_one(data.model_dump())
        except Exception as e:
            logger.error(f"ERROR: cannot creat session: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def read(self, session_id: UUID) -> SessionData:
        try: 
            result = await self.collection.find_one({"session_id": str(session_id)})
            if result:
                return SessionData(**result)
            return None
        except Exception as e:
            logger.error(f"ERROR: cannot read session: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def update(self, session_id: UUID, data: SessionData):
        try:
            await self.collection.update_one({"session_id": str(session_id)}, {"$set": data.model_dump()})
        except Exception as e:
            logger.error(f"ERROR: cannot update session: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def delete(self, session_id: UUID):
        try:
            await self.collection.delete_one({"session_id": str(session_id)})
        except Exception as e:
            logger.error(f"ERROR: cannot remove session: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")
    
    def ensure_ttl_index(self):
        try:
            # Crea un índice en expiration_time con un TTL de 0 segundos.
            self.collection.create_index("expiration_time", expireAfterSeconds=0)
        except Exception as e:
            logger.error(f"ERROR: cannot create TTL index: {e}")
            raise HTTPException(status_code=500, detail="Error al configurar índice TTL")


# Clase personalizada de SessionVerifier para verificar la sesión
class CustomSessionVerifier(SessionVerifier):
    def __init__(self, backend: MongoDBBackend):
        self.mongo_backend = backend

    async def verify_session(self, session_id: UUID):
        session = await self.mongo_backend.read(session_id)
        session_expiration_time = session.expiration_time.replace(tzinfo=timezone.utc)
        if not session or datetime.now(timezone.utc) > session_expiration_time:
            if session:
                await self.mongo_backend.delete(session_id)
                return False
        return True


# Clase CookieBackend para escribir, leer y eliminar cookies
class CookieBackend:
    def __init__(self, cookie_name: str, secret_key: str, backend: MongoDBBackend):
        self.cookie_name = cookie_name
        self.secret_key = secret_key
        self.backend = backend

    def write(self, response: Response, session_id: UUID):
        try:
            response.set_cookie(key=self.cookie_name, value=str(session_id), httponly=True)
        except Exception as e:
            logger.error(f"ERROR: cannot write cookie: {e}")
            raise HTTPException(status_code=404, detail="Session not found or expired")

    def read(self, request) -> UUID:
        try: 
            return UUID(request.cookies.get(self.cookie_name))
        except Exception as e:
            logger.error(f"ERROR: cannot read cookie: {e}")
            raise HTTPException(status_code=404, detail="Session not found or expired")

    def delete(self, response: Response):
        try:
            response.delete_cookie(self.cookie_name)
        except Exception as e:
            logger.error(f"ERROR: cannot remove cookie: {e}")
            raise HTTPException(status_code=404, detail="Session not found or expired")
        

# Cada vez que una solicitud HTTP llega a la aplicación, este middleware utiliza la cookie id_session para localizar la sesión en el backend.
class SessionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, mongo_backend, cookie_backend, session_timeout):
        super().__init__(app)
        self.mongo_backend = mongo_backend
        self.cookie_backend = cookie_backend
        self.session_timeout = session_timeout

    async def dispatch(self, request: Request, call_next):

        # Inicializar request.state.session
        request.state.session = None

        # Rutas que no deben requerir autenticación o sesión
        excluded_paths = ["/static", "/templates", "/"]
        if any(request.url.path.startswith(path) for path in excluded_paths):
            return await call_next(request)
        
        session_id = request.cookies.get("session_id")  # Acceso a la cookie de sesión

        logger.info("Retrive session from backend with id:" + str(session_id))

        if session_id:
            # Verificar y cargar la sesión desde MongoDB
            session = await self.mongo_backend.read(session_id)
            logger.info("ID DE SESSIÓN EN LA SESIÓN RECUPERADA: "+session.session_id)
            if session:
                # Verificar si la sesión ha expirado
                if session.expiration_time < datetime.now(timezone.utc):
                    await self.mongo_backend.delete(session_id)
                    response = Response("Session expired", status_code=401)
                    self.cookie_backend.delete(response)
                    return response

                # Asignar la sesión al request.state
                request.state.session = session
            else:
                logger.error("ERROR: Session not found in session backend or session backend is down")
                return Response("Session not found", status_code=404)
        else:
            logger.error("ERROR: session_id not found in cookies")
            return Response("Session not found", status_code=401)

        response = await call_next(request)
        return response
