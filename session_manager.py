from pydantic import BaseModel
from datetime import datetime, timezone
from fastapi_sessions.session_verifier import SessionVerifier
from fastapi_sessions.backends.session_backend import SessionBackend
from uuid import UUID
from fastapi import HTTPException
from fastapi import Response
from datetime import datetime


# Clase Backend de sesión para almacenar y recuperar datos de sesión. Todos las instancias de objetos de sesión deben ser subclases de BaseModel
class SessionData(BaseModel):
    session_id: str
    data: dict # Almacena las conversaciones
    last_active: datetime # Marca de tiempo de la última interacción
    expiration_time: datetime  # Marca de tiempo de expiración de la sesión


# Implementación de la clase MongoDBBackend con el backend de sesión y la colección de sesiones
class MongoDBBackend(SessionBackend):
    def __init__(self, collection):
        self.collection = collection
    # Métodos CRUD para sesiones
    async def create(self, session_id: UUID, data: SessionData):
        try:
            await self.collection.insert_one(data.model_dump())
        except Exception as e:
            print(f"Error al crear la sesión: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def read(self, session_id: UUID) -> SessionData:
        try: 
            result = await self.collection.find_one({"session_id": str(session_id)})
            if result:
                return SessionData(**result)
            return None
        except Exception as e:
            print(f"Error al leer la sesión: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def update(self, session_id: UUID, data: SessionData):
        try:
            await self.collection.update_one({"session_id": str(session_id)}, {"$set": data.model_dump()})
        except Exception as e:
            print(f"Error al actualizar la sesión: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def delete(self, session_id: UUID):
        try:
            await self.collection.delete_one({"session_id": str(session_id)})
        except Exception as e:
            print(f"Error al eliminar la sesión: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")


# Clase personalizada de SessionVerifier para verificar la sesión
class CustomSessionVerifier(SessionVerifier):
    def __init__(self, backend: MongoDBBackend):
        self.mongo_backend = backend

    async def verify_session(self, session_id: UUID):
        session = await self.mongo_backend.read(session_id)
        if not session or datetime.now(timezone.utc) > session.expiration_time:
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
            print(f"Error al escribir la cookie: {e}")
            raise HTTPException(status_code=404, detail="Session not found or expired")

    def read(self, request) -> UUID:
        try: 
            return UUID(request.cookies.get(self.cookie_name))
        except Exception as e:
            print(f"Error al leer la cookie: {e}")
            raise HTTPException(status_code=404, detail="Session not found or expired")

    def delete(self, response: Response):
        try:
            response.delete_cookie(self.cookie_name)
        except Exception as e:
            print(f"Error al eliminar la cookie: {e}")
            raise HTTPException(status_code=404, detail="Session not found or expired")
