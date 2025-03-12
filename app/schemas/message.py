from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime, timezone

# ------ESQUEMA DE VALIDACIÓN PARA MENSAJE------

class MessageModel(BaseModel):
    content: Optional[str] = Field(..., 
        description="Contenido textual del mensaje"
    )
    is_bot: bool = Field(
        default=False,
        description="Si el mensaje es generado por el chatbot o no"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Marca de tiempo del mensaje"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Marca de tiempo del mensaje"
    )