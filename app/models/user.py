from datetime import datetime, timezone
from typing import List, Dict, Any
from pydantic import EmailStr, Field, field_validator, field_serializer, ConfigDict
from typing import List
import uuid
from beanie import Document

# ------MODELO PARA LA COLECCIÓN 'USERS'------
class UserModel(Document):
    username: str = Field(
        default="",
        description="Nombre del usuario"
    )
    email: EmailStr = Field(
        default="",
        description="Correo electrónico del usuario"
    )
    phone: str = Field(
        default="",
        description="Número de teléfono del usuario"
    )
    session_ids: List[str] = Field(
        default_factory=list,
        description="Lista de sesiones asociadas al usuario"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Fecha de creación"
    )
    last_activity: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Última actualización. Cada modificación de los datos se considera una actualización"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos adicionales del documento"
    )
    
    class Settings:
        name = "users"
        id_field = "phone"

    model_config = ConfigDict(
        populate_by_name=True,
        ser_json_timedelta="iso8601",
        ser_json_bytes="utf8",
        json_schema_extra={
            "example": {
                "username": "johndoe",
                "email": "johndoe@example.com",
                "phone": "123456789",
                "session_ids": ["sesion_123", "sesion_456"],
                "metadata": {}
            }
        }
    )


    # ------ SERIALIZACIÓN A DICT ------
    @field_serializer('created_at', 'last_activity')
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.isoformat()
    
    def serialize(self) -> dict:
        """Convierte la instancia de la usuario a un diccionario."""
        return self.model_dump()


    # ------VALIDACIÓN PARA LA INSTANCIA ------    
    @field_validator("last_activity", mode="after")
    def validate_last_activity(cls, value, values):
        created_at = getattr(values, "created_at", None)
        if created_at and created_at > value:
            raise ValueError("Last activity date cannot be before creation date")
        return value

    @field_validator("email", mode="before")
    def validate_email(cls, value):
        if not isinstance(value, str) or "@" not in value:
            raise ValueError("Invalid email format")
        return value

    @field_validator("session_ids", mode="before")
    def validate_session_ids(cls, value):
        if not isinstance(value, list) or not all(isinstance(s, str) for s in value):
            raise ValueError("session_ids must be a list of strings")
        return value
    
    @field_validator("phone", mode="before")
    def validate_phone(cls, value):
        if not value.isdigit() or len(value) < 9:
            raise ValueError("Phone number must be at least 9 digits and contain only numbers")
        return value
    

    # ------DESERIALIZACIÓN DESDE DICT ------
    @classmethod
    def deserialize(cls, data: dict) -> "UserModel":
        """Convierte un diccionario a una instancia de UserModel."""
        return cls.model_validate(data)
