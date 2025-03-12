from fastapi import Request, HTTPException, Depends
from datetime import datetime, timezone
import logging

from app.dependencies.services_dependencies import get_session_service
from app.services.sessions_service import SessionService
from app.models.session import SessionModel

logger = logging.getLogger(__name__)

# ------RECUPERACIÓN DEL ID DE SESIÓN DE LA CONSULTA------
async def get_session_id(request: Request) -> str:
    """ Recupera y valida el session_id desde las cookies de la solicitud."""

    session_id = getattr(request.state, "session", None)
    if not session_id:
        logging.warning("Session ID not provided in request at session dependence")
        raise HTTPException(status_code=401, detail="Session ID is missing")

    return str(session_id)
            

# ------GESTIÓN DE LA SESIÓN DE CONSULTA------
async def manage_session(request: Request, session_service: SessionService = Depends(get_session_service)) -> SessionModel:
    """ Dependencia que recupera y valida la sesión desde Redis. Espera a la ejecución del endpoint y actualiza la sesión
        Recesita recuperar el servicio de sesiones desde la app.       
    """

    try:
        #------COMPROBAMOS LA SESIÓN EN LA SOLICITUD
        id: str = await get_session_id(request)

        #------COMPROBAMOS LA SESIÓN EN REDIS
        session: SessionModel = await session_service.get_session(id)
        if not session:
            logging.warning(f"Session not found in Redis.")
            raise HTTPException(status_code=401, detail="Session not found in Redis.")

        if session.expiry_date and datetime.now(timezone.utc) >= session.expiry_date:
            logging.info(f"Session has expired.")
            await session_service.delete_session(id)
            raise HTTPException(status_code=401, detail="Session has expired.")

        #------ENTREGAMOS EL CONTROL AL ENDPOINT
        return session

    except Exception as e:
        logging.error(f"Error in session dependence: {e}")
        raise HTTPException(status_code=500, detail=f"Error in session dependence: {e}")
        

# ------ACTUALIZACIÓN DE LA SESIÓN------
async def update_session(session: SessionModel, request: Request):

    try:
        session_service: SessionService = get_session_service(request)
        await session_service.save_session(session)

    except Exception as e:
        logging.error(f"Error at session update: {e}")
        raise HTTPException(status_code=500, detail=f"Error at session update: {e}")

        