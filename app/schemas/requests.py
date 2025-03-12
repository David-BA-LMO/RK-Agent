from pydantic import BaseModel, Field, EmailStr
from datetime import datetime, timezone
from typing import Union

# ------ESQUEMA DE VALIDACIÓN PARA MENSAJES ------
class UserRequest(BaseModel):
    type: str = Field(..., 
        description="Tipo de interacción"
    )
    content: Union[str, tuple[float, float], dict] = Field(..., 
        description="Contenido de la solicitud del usuario"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Marca de tiempo del mensaje de usuario"
    )


# ------ESQUEMA DE VALIDACIÓN PARA EL FORMULARIO------
class FormRequest(BaseModel):
    username: str = Field(..., 
        min_length=3, 
        max_length=50, 
        description="User name"
    )
    email: EmailStr = Field(..., 
        description="Valid email"
    )
    phone: str = Field(
        pattern=r'^\+?1?\d{9,15}$',  # Validación de números telefónicos internacionales
        description="Phone number"
    )
    action: str = Field(
        description="Accion a realizar con los datos personales (demand_visit)"
    )


# ------ESQUEMA DE VALIDACIÓN PARA LA CONFIRMACIÓN DE PROTECCION DE DATOS ------
class ConfirmationRequest(BaseModel):
    accepted: bool = Field(
        description="Indica si el usuario acepta o no compartir datos personales."
    )