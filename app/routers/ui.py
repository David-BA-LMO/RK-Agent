from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from typing import Dict
from pathlib import Path
import logging
from fastapi import APIRouter, Depends, Request, Body

from app.schemas.requests import FormRequest, ConfirmationRequest
from app.utils.api_calls import fetch_demand
from app.services.user_service import UserService
from app.models.session import SessionModel
from app.models.user import UserModel
from app.dependencies.services_dependencies import get_users_service
from app.dependencies.session_dependece import manage_session, update_session
from app.schemas.tools import VisitToolModel

router = APIRouter()

logger = logging.getLogger(__name__)

#------RUTAS-----
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_interface():
    """Sirve la interfaz principal del chatbot"""
    try:
        html_path = Path("static/html/index.html")
        return html_path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        logging.error(f"Error occurred in interface serving: {e}")
        return HTMLResponse(
            content="<h1>Error: Interfaz no encontrada</h1>",
            status_code=404
        )

@router.post("/submit-form")
async def submit_form(
    request: Request,
    form_request: FormRequest = Body(...),
    user_service: UserService = Depends(get_users_service),
    session: SessionModel = Depends(manage_session)
):
    """Crea o actualiza un nuevo usuario con los datos del formulario"""
    print(f"FORMULARIO: {form_request}")
    try:
        email: str = form_request.email
        username: str = form_request.username
        phone: str = form_request.phone
        action: str = form_request.action

        user: UserModel = await user_service.get_user(phone = phone)

        print(f"USUARIO OBTENIDO: {user}")
        if not user:
            logger.warning(f"User not found. Creating a new user...")
            user: UserModel = await user_service.create_user(username=username, email=email, phone=phone)
            print(f"USUARIO CREADO: {user}")

        # Realizamos acciones opcionales
        if action == "demand_visit":
            demand_visit(session, user)

        id = getattr(request.state, "session", None)
        if not id:
            logging.warning("Session ID not provided in request at messages dependence")
            raise HTTPException(status_code=401, detail="Session ID is missing")

        else:
            print(f"TIPO DE DATO PHONE: {type(user.phone)}")
            await user_service.update_user(user, id)

        # Actualizamos el objeto sesion incluyendo el nombre
        session.name = username
        await update_session(session, request)

        return {"source": "/submit-form", "status": "success"}

    except Exception as e:
        logging.error(f"Error occurred in user updating: {e}")
        raise Exception(f"Error occurred in user updating: {e}")
    
    
@router.post("/confirm-data")
async def confirm_data(
    request: Request,
    confirm_request: ConfirmationRequest = Body(...),
    session: SessionModel = Depends(manage_session)
):
    print(f"CONFIRMACIÓN: {confirm_request}")
    session.personal_data = confirm_request.accepted
    await update_session(session, request)
    return {"source": "/confirm-data", "status": "success"}


#------ACCIONES-----
def demand_visit(session: SessionModel, user: UserModel) :

    visit_tool: VisitToolModel = session.tools_data.get("visit_tool")
    selected_prop: Dict[int, Dict] = visit_tool.selected_prop

    selected_prop_id: int = next(iter(selected_prop)) # Suponemos que el diccionario solo contiene un solo item

    data = {
        "nombre": user.username,
        "telefono": user.phone,
        "email": user.email,
        "id_inmueble": str(selected_prop_id)
    }

    if not session.personal_data:
        visit_tool.selected_prop = {}

    fetch_demand(data)
    

