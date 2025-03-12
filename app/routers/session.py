import logging
import uuid
import redis
import hashlib
import os
from fastapi import APIRouter, Response, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from itsdangerous import Signer
from pprint import pprint

from app.services.sessions_service import SessionService
from app.services.messages_service import MessagesService
from app.dependencies.services_dependencies import get_session_service, get_messages_service

router = APIRouter()

logger = logging.getLogger(__name__)

async def create_object_sessions(request: Request, phone: str = None) -> str:
    """ 
    Función destinada a crear la sesión si no existe previamente. 
    Se llama tanto desde la ruta /login (para sesiones desde web) como desde el Middleware (para sesiones desde Whatsapp)
    """
    try:
        # ----RECUPERAMOS LOS SERVICIOS DE SESIONES
        session_service: SessionService = get_session_service(request)
        messages_service: MessagesService = get_messages_service(request)
        
        if phone:
            id = f"wat_{hashlib.sha256(phone.encode()).hexdigest()}"  # Utilizamos el numero de telefono hasheado como id desde Whatsapp
            metadata = {"source": "whatsapp"}
        else:
            id = f"web_{str(uuid.uuid4())}"  # Utilizamos un formato UUID como id desde Web
            metadata = {"source": "web"}

        # ----CREACIÓN DE SESIÓN
        session = await session_service.get_session(id)
        if not session:
            is_session = await session_service.create_session(id = id, metadata=metadata)        
            if not is_session:
                logging.error(f"Error creating session at /login route")
                raise HTTPException(status_code=401, detail="Error creating session at /login route")
            logging.info(f"Session created sucessfully in Redis")
        else:
            logging.info(f"Session retrieved sucessfully from Redis")

        # ----CREACIÓN DE REGISTRO DE MENSAJES
        messages = await messages_service.get_messages(id)
        if not messages:
            is_message = await messages_service.create_messages(id = id, metadata=metadata)
            if not is_message:
                logging.error(f"Error creating messages registry at /login route")
                raise HTTPException(status_code=401, detail="Error creating messages registry at /login route")
            logging.info(f"Message registry created sucessfully in MongoDB")
        else:
            logging.info(f"Message registry retrieved sucessfullyfrom MongoDB")

        return id

    except Exception as e:
            logger.error(f"Error processing session objects: {e}")
            return JSONResponse({"error": "Internal Server Error"}, 500)

# ------ LOGIN ------
@router.post("/login")
async def login(request: Request, response: Response):
    """Crea una nueva sesión en Redis y establece la cookie"""    
    try:        
        # ----CREACIÓN DE OBJETOS DE SESIÓN
        id = await create_object_sessions(request)

        # ----REGISTRO DE COOKIE
        signer = Signer(os.getenv("MIDDLEWARE_SECRET_KEY"))
        signed_id = signer.sign(id).decode() 

        response.set_cookie(
            secure=True,
            key="id",
            value=signed_id,
            httponly=True,
            samesite="Lax",
            max_age=86400
        )

        logging.info(f"Cookie stablised sucessfully")
        return {"message": "Session created"}
    
    except redis.RedisError as e:
        logging.error(f"Redis error creating new session: {e}")
        return JSONResponse(
            status_code=503,
            content={"error": "Redis is unavailable. Please try again later."}
        )
    except Exception as e:
        logging.error(f"Error occurred at session objects creation: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Error occurred at session objects creation."}
        )

# ------ LOGOUT ------
@router.post("/logout")
async def logout(
    request: Request, 
    response: Response
) -> dict:
    """ Endpoint para cerrar la sesión del usuario. """
    cookie_name = "id"
    id = request.cookies.get(cookie_name)

    if not id:
        raise HTTPException(status_code=401, detail="Session ID not found")

    try:
        result = SessionService.delete_session(id)
        if result == 0:
            logging.warning(f"Session not found during logout.")
            raise HTTPException(status_code=404, detail="Session not found")
        
        response.delete_cookie(key=cookie_name)
        logging.info(f"Session deleted successfully.")
        return {"message": "Logged out successfully"}

    except Exception as e:
        logging.error(f"Failed to logout session: {e}")
        raise HTTPException(status_code=500, detail="Failed to logout")