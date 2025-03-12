import logging
from itsdangerous import Signer, BadSignature
from fastapi import Request, Response, HTTPException
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.routers.session import create_object_sessions
logger = logging.getLogger(__name__)

class SessionMiddleware(BaseHTTPMiddleware):

    def __init__(self, app, secret_key):
        super().__init__(app)
        self.cookie_name = "id"
        self.excluded_paths = ["/login", "/", "/welcome-message"]
        self.signer = Signer(secret_key)

    async def dispatch(self, request: Request, call_next) -> Response:
        
        #----MANEJO DE RUTA A WHATSAPP
        if request.url.path == "/whats-message":
            return await self.handle_whatsapp_request(request, call_next)

        #----EXCLUSIÓN DE RUTAS DEL MIDDLEWARE
        if request.url.path in self.excluded_paths or request.url.path.startswith("/static/"):
            return await call_next(request)

        #----RECUPERACIÓN DEL ID EN LA COOKIE
        signed_id = request.cookies.get(self.cookie_name)
        
        if not signed_id:
            logger.error("Session ID not found in session cookie")
            return JSONResponse(
                {"error": "Sesión expirada o inválida"},
                status_code=401
            )

        # ----VERIFICACIÓN DE SESIÓN
        try:
            id = self.signer.unsign(signed_id).decode()
            request.state.session = id
            
        except BadSignature:
            logger.error("Invalid session firm")
            return JSONResponse(
                {"error": "Sesión manipulada o inválida"},
                status_code=401
            )

        # ----REENVÍO DE COOKIE
        response = await call_next(request)
        response.set_cookie(
            secure=True,
            key="id",
            value=self.signer.sign(id).decode(),
            httponly=True,
            samesite="Lax",
            max_age=86400
        )

        return response
    
    async def handle_whatsapp_request(self, request: Request, call_next):
        """Manejo especializado para solicitudes de WhatsApp"""
        try:
            #----VALIDACIÓN DE TWILIO
            form_data = await request.form()
            if not form_data or not input:
                raise HTTPException("Invalid message format")
            
            phone = form_data.get('From')
            request.state.phone = phone
            request.state.body = form_data.get('Body')
            request.state.user_name = form_data.get('ProfileName')
            
            #----RECUPERAMOS SESIÓN DE REDIS
            # Se comprueba si existen los objetos de sesión y en caso contrario se crea uno nuevo de forma independiente.
            id = await create_object_sessions(request, phone = phone) 
                
            request.state.session = id # El id es el número de teléfono hasheado
            response = await call_next(request)
            return response
            
        except Exception as e:
            logger.error(f"Error processing WhatsApp message: {e}")
            return JSONResponse({"error": "Internal Server Error"}, 500)