from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from typing import Dict, AsyncGenerator,List
import re
import sqlite3
import logging
import json
from pprint import pprint

from app.config import (
    ID_OF_INTEREST_PROMPT_dir,
    CONFIRM_VISIT_PROMPT_dir,
)
from app.logic.tool_config.base_models import generate_book_llm
from app.utils.general_utilities import open_txt
from app.schemas.tools import VisitToolModel
from app.logic.tool_utilities.visit_utilities import extract_data
from app.data_generation.sql_search_generation import execute_sql_query
from app.logic.tool_utilities.qa_utilities import (
    generate_sql_ids,
    filter_presentation_fields,
    parse_db_answer
)

logger = logging.getLogger(__name__)

#----------------------------------------------------------------------------------------------------------

class VisitChain:

    # PLANTILLA DE PROMPTS
    ID_OF_INTEREST_PROMPT = open_txt(ID_OF_INTEREST_PROMPT_dir)
    CONFIRM_VISIT_PROMPT = open_txt(CONFIRM_VISIT_PROMPT_dir)
    
    # PROMPTS
    id_of_interest_prompt = PromptTemplate.from_template(ID_OF_INTEREST_PROMPT) # Prompt para obtener el id del inmueble de interés
    confirm_visit_prompt = PromptTemplate.from_template(CONFIRM_VISIT_PROMPT) # Prompt para pedir confirmación al usuario

    # MODELOS DE LENGUAJE
    book_llm = generate_book_llm()

    # CADENAS
    # Cadena para obtener el id del inmueble de interés
    id_of_interest_chain = id_of_interest_prompt | book_llm | StrOutputParser()

    # Cadena para pedir confirmación al usuario
    confirm_visit_chain = confirm_visit_prompt | book_llm | StrOutputParser()


    #------EJECUCIÓN DE LA HERRAMIENTA------
    @classmethod
    async def execute(cls, input: str, visit_tool: VisitToolModel, presented_inms: List[int], user_name: str, personal_data: bool) -> AsyncGenerator[str, None]:
        """
        Esta función coordina toda la herramienta de visitas. Primero selecciona el inmueble por el que el usuario parece haber mostrado interes, tras lo cual responde con una breve descripción del inmueble de manera que el usuario sepa el inmueble para el que se esta considerando realizar la visita. También genera una ventana 
        """

        data_inm = "" # Guarda los datos del inmueble seleccionado

        #------SELECCIÓN DE ID A PARTIR DEL HISTORIAL
        if not visit_tool.selected_prop: # Si todavía no se ha seleccionado un inmueble de interés. El reinicio de esta variable se realiza en la ruta de confirmación del formulario.
            try: 
                # ---- RECUPERAMOS LOS DATOS DE LOS INMUEBLES PRESENTADOS
                list_inm_id: list = [id for id in presented_inms]
                last_searched_query: str = generate_sql_ids(list_inm_id)  # Consulta a la base de datos con los IDs buscados
                last_searched_result: List[sqlite3.Row] = execute_sql_query(last_searched_query)
                last_searched_parsed: Dict[int, Dict] = parse_db_answer(last_searched_result) # Resultados parseados por columna
                last_searched_filtered: Dict[int, Dict] = filter_presentation_fields(last_searched_parsed) # Resultados filtrados
                last_searched_filtered_str: str = json.dumps(last_searched_filtered)
                print(f"INMUEBLES PRESENTADOS: {presented_inms}")

                # ---- OBTENEMOS EL INMUEBLE DE INTERES
                selected_id = await cls.id_of_interest_chain.ainvoke({"input": input, "inm_data": last_searched_filtered_str})
                match = re.search(r'\d+', selected_id) 
                if match:
                    selected_id = int(match.group())
                else:
                    selected_id = presented_inms[-1] # Si no se ha obtenido un ID suponemos que el inmueble de interés es el último presentado

                data_inm: Dict[str, str] = last_searched_filtered.get(selected_id)
                visit_tool.selected_prop = {selected_id: data_inm}
                print(f"ID SELECCIONADO PARA VISITA: {selected_id}")              

            except Exception as e:
                logger.error(f"Unspected error in resolution the property of interest: {e}")
                raise Exception(status_code=500, detail=f"Unspected error in resolution the property of interest: {e}")

            #------GENERAMOS LA PETICIÓN DE CONFIRMACIÓN
            # Independientemente de si se resuelve el inmueble de interés, se ejecuta la cadena de confirmación de visita, ya que esta también es capaz de responder a dudas del usuario.
            async for partial_message in cls.confirm_visit_chain.astream({"user_name": user_name, "selected_inm": data_inm}):
                yield {"type": "text", "content": partial_message}
            yield {"type": "metadata", "key": "chain", "content": "confirm_visit_chain"}
            
            if not personal_data:
                yield {"type": "function", "content": "generateConfirmationPopup", "input": "demand_visit"}

            return
        
        else:
            yield {"type": "text", "content": "Lo sentimos, pero solo es posible realizar una sola reserva por usuario"}