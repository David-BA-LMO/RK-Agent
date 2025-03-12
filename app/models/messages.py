from pydantic import Field, field_validator, field_serializer, ConfigDict
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone
from beanie import Document

from app.schemas.message import MessageModel

# ------MODELO PARA LA COLECCIÓN 'MESSAGES'------
class MessagesModel(Document):

    id: str = Field(...,
        alias="_id",
        description="Identificador de la sesión asociada al historial de mensajes"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Marca de tiempo de la creación"
    )
    last_activity: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Marca de tiempo de la última actualización"
    )
    messages: List[MessageModel] = Field(
        default_factory=list, 
        description="Historial de mensajes"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos adicionales del documento"
    )

    class Settings:
        name = "messages"
        id_field = "id"
        use_state_management = True

    model_config = ConfigDict(
        populate_by_name=True,
        ser_json_timedelta="iso8601",
        ser_json_bytes="utf8",
        json_schema_extra={
            "example": {
                "id": "sesion_123",
                "created_at": datetime.now(timezone.utc),
                "last_activity": datetime.now(timezone.utc),
                "messages": [{"content": "XXXX", "is_bot": False, "timestamp": datetime.now(timezone.utc), "metadata": {}}],
                "metadata": {}
            }
        }
    )

    
    # ------ SERIALIZACIÓN A DICT ------
    @field_serializer('created_at', 'last_activity')
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.replace(microsecond=0).isoformat()
    
    def serialize(self) -> dict:
        """Convierte la instancia de mensajes a un diccionario."""
        return self.model_dump()

    
    # ------VALIDACIÓN PARA LA INSTANCIA ------
    @field_validator("id", mode="before")
    def validate_id(cls, value):
        if not isinstance(value, str):
            return str(value)
        return value
    
    @field_validator("last_activity", mode="after")
    def validate_last_activity(cls, value, values):
        created_at = getattr(values, "created_at", None)
        if created_at and created_at > value:
            raise ValueError("Last activity date cannot be before creation date")
        return value
    
    @field_validator("messages", mode="before")
    def validate_tools_data(cls, value):
        """'Valida que messages contenga instancias MessageModel'"""

        if not isinstance(value, list):
            raise ValueError("messages must be a list")
        
        validate_messages = []

        for message in value:
            # Si ya es una instancia válida, lo dejamos así
            if isinstance(message, MessageModel):
                validate_messages.append(message)
            else:
                # Si no, intentamos convertirlo
                try:
                    validate_messages.append(MessageModel(**message))
                except Exception as e:
                    raise ValueError(f"Error converting {message}: {e}")

        return validate_messages
    
    
    # ------DESERIALIZACIÓN DESDE DICT ------
    @classmethod
    def deserialize(cls, data: dict) -> "MessagesModel":
        """Convierte un diccionario a una instancia de MessagesModel."""
        return cls.model_validate(data)
