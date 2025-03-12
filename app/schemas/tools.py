from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field 

class QAToolModel(BaseModel):
    missing_fields: List[str] = Field(
        default_factory=list, 
        description="Campos faltantes para ejecutar la consulta"
    )
    last_query: Optional[str] = Field(
        default=None,
        description="La última consulta SQL ejecutada o intentada"
    )
    last_modify_query: Optional[str] = Field(
        default=None,
        description="La última consulta SQL ejecutada o intentada"
    )
    last_result: Dict[str, Any] = Field(
        default_factory=dict, 
        description="La última respuesta dada por la base de datos, parseada con nombres de columnas"
    )
    searched_inms: List[int] = Field(
        default_factory=list, 
        description="Lista de IDs de inmuebles ya buscados"
    )
    presented_inms: List[int] = Field(
        default_factory=list, 
        description="Lista de IDs de inmuebles ya presentados"
    )
    inm_localization: Optional[tuple[float, float]] = Field(
        default=None, 
        description="Localización (latitud, longitud) indicada para búsqueda generada en la animación."
    )
    buffer_input: str = Field(
        default="", 
        description="Input anterior cuando hay campos requeridos"
    )
    
    
class RouterToolModel(BaseModel):
    is_answer_name: bool = Field(
        default=False, 
        description="Indica si se le preguntado al usuario por su nombre"
    )
    
    
class VisitToolModel(BaseModel):
    selected_prop: Dict[int, Dict] = Field(
        default_factory=dict, 
        description="Inmueble seleccionado para la visita. Exclusivamente uno"
    )
    

class RAGToolModel(BaseModel):
    status: str = Field(
        default="", 
        description="Atributo de prueba"
    )
    
    