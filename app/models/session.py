import os
from typing import Dict, Any, Union, Optional
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field, field_validator, field_serializer, ConfigDict

from app.schemas.tools import QAToolModel, RouterToolModel, VisitToolModel, RAGToolModel

# ------MODELO SESIÓN DE REDIS------
class SessionModel(BaseModel):
    id: str = Field(...,
        alias="_id",
        description="Identificador de la sesión"
    )
    name: Optional[str] = Field(
        default= None,
        description="Nombre del usuario en la sesión"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Identificador de la sesión"
    )
    last_activity: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Marca de tiempo de la última actualización"
    )
    expiry_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=int(os.getenv("SESSION_EXPIRE_MINUTES", "30"))),
        description="Marca de tiempo de expiración de la sesión"
    )
    status: str = Field(
        default="active",
        description="Estado actual de la sesión"
    )
    tools_data: Dict[str, Union[QAToolModel, VisitToolModel, RAGToolModel, RouterToolModel]] = Field(
        default_factory=lambda: SessionModel.create_tools_data(),
        description="Valores para el uso de herramientas del chatbot"
    )
    personal_data: bool = Field(
        default=False, 
        description="Indica si se ha aceptado compartir datos personales (solo Web)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos adicionales de la sesión"
    )
    
    

    @staticmethod
    def create_tools_data() -> Dict[str, BaseModel]:
        return {
            "qa_tool": QAToolModel(),
            "visit_tool": VisitToolModel(),
            "rag_tool": RAGToolModel(),
            "router_tool": RouterToolModel()
        }

    model_config = ConfigDict(
        populate_by_name=True,
        ser_json_timedelta="iso8601",
        ser_json_bytes="utf8",
        json_schema_extra={
            "example": {
                "id": "sesion_123",
                "name": "Francisco",
                "created_at": datetime.now(timezone.utc),
                "last_activity": datetime.now(timezone.utc),
                "status": "active",
                "tools_data": {},
                "metadata": {}
            }
        }
    )

    # ------ SERIALIZACIÓN A JSON ------
    @field_serializer('created_at', 'last_activity', 'expiry_date')
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.replace(microsecond=0).isoformat()
    
    def serialize(self) -> str:
        """Convierte la instancia de la sesión a JSON."""
        return self.model_dump_json()

    # ------ VALIDACIONES PARA LA INSTANCIA ------
    @field_validator("id", mode="before")
    def validate_id(cls, value):
        if not isinstance(value, str):
            return str(value)
        return value
        
    @field_validator("last_activity", mode="after")
    def validate_last_activity(cls, value, values):
        created_at = getattr(values, "created_at", None)
        if created_at and created_at > value:
            raise ValueError("last activity date cannot be before creation date")
        return value
    
    @field_validator("expiry_date", mode="after")
    def validate_expiry_date(cls, value: datetime) -> datetime:
        if value <= datetime.now(timezone.utc):
            raise ValueError("expiry_date debe ser una fecha futura.")
        return value


    @field_validator("tools_data", mode="before")
    def validate_tools_data(cls, value):
        """'Valida que tools_data contenga instancias de modelos válidos.'"""
        if not isinstance(value, dict):
            raise ValueError("tools_data must be a dictionary")

        valid_models = {
            "qa_tool": QAToolModel, 
            "visit_tool": VisitToolModel, 
            "rag_tool": RAGToolModel, 
            "router_tool": RouterToolModel
        }

        for key, model_data in value.items():
            if key not in valid_models:
                raise ValueError(f"Invalid tool key: {key}")

            # Si ya es una instancia válida, lo dejamos así
            if isinstance(model_data, valid_models[key]):
                continue

            # Si no, intentamos convertirlo
            try:
                value[key] = valid_models[key](**model_data)
            except Exception as e:
                raise ValueError(f"Error converting {key}: {e}")

        return value
    
    # ------DESERIALIZACIÓN DESDE JSON ------
    @classmethod
    def deserialize(cls, json_data: str) -> "SessionModel":
        """Convierte un JSON a una instancia de SessionModel."""
        return cls.model_validate_json(json_data)