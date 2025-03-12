from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
import json
from typing import AsyncGenerator, List, Dict, Any
import logging
import ast 

from app.utils.general_utilities import open_txt, open_json
from app.logic.qa_chain import QAChain
from app.logic.rag_chain import RagChain
from app.logic.visit_chain import VisitChain
from app.models.session import SessionModel
from app.schemas.tools import RouterToolModel, QAToolModel, VisitToolModel
from app.config import (
    CLASSIFICATION_PROMPT_dir,
    PRESENTATION_PROMPT_dir,
    CONTACT_PROMPT_dir,
    NAME_PROMPT_dir,
    ANSWER_NAME_PROMPT_dir,
    OFF_TOPIC_PROMPT_dir,
    contact_info_json_dir,
    tool_instructions_dir,    
)
from app.logic.tool_config.base_models import generate_router_llm

logger = logging.getLogger(__name__)

class Router_chain:

    # ----  MODELOS DE LENGUAJE
    llm = generate_router_llm()

    # ---- PLANTILLAS DE PROMPTS
    CLASSIFICATION_PROMPT = open_txt(CLASSIFICATION_PROMPT_dir)
    PRESENTATION_PROMPT = open_txt(PRESENTATION_PROMPT_dir)
    CONTACT_PROMPT = open_txt(CONTACT_PROMPT_dir)
    OFF_TOPIC_PROMPT = open_txt(OFF_TOPIC_PROMPT_dir)
    NAME_PROMPT = open_txt(NAME_PROMPT_dir)
    ANSWER_NAME_PROMPT = open_txt(ANSWER_NAME_PROMPT_dir)

    # ---- PROMPTS
    classification_prompt = PromptTemplate.from_template(CLASSIFICATION_PROMPT)
    presentation_prompt = PromptTemplate.from_template(PRESENTATION_PROMPT)
    contact_prompt = PromptTemplate.from_template(CONTACT_PROMPT)
    off_topic_prompt = PromptTemplate.from_template(OFF_TOPIC_PROMPT)
    name_prompt = PromptTemplate.from_template(NAME_PROMPT)
    answer_name_prompt = PromptTemplate.from_template(ANSWER_NAME_PROMPT)

    # ---- CADENAS 
    classification_chain = classification_prompt | llm | StrOutputParser()   #Cadena clasificadora
    presentation_chain = presentation_prompt | llm | StrOutputParser()  # Cadena de presentación
    contact_chain = contact_prompt | llm | StrOutputParser()  # Cadena de información de contacto
    off_topic_chain = off_topic_prompt | llm | StrOutputParser()  # Cadena de consultas ajenas a la app
    name_chain = name_prompt | llm | StrOutputParser()  # Cadena para reconocimiento del nombre
    answer_name_chain = answer_name_prompt | llm | StrOutputParser() # Cadena para contestar al nombre del usuario

    #---- INSTRUCCIONES DE LA CADENA ENRUTADORA
    try:
        contact_info: str = json.dumps(open_json(contact_info_json_dir))

        tool_instructions: List[Dict] = open_json(tool_instructions_dir).get("route_chain")
        
    except Exception as e:
            logger.error(f"Unexpected error in routing chain configuration: {e}")
            raise Exception(f"ERROR: Unexpected error in routing chain configuration: {e}")
            
    
    @classmethod
    async def execute(cls, input: str, session: SessionModel, history: List[Dict[str, Any]], user_name: str = None) -> AsyncGenerator[str, None]:
        """Esta función enruta la consulta del usuario a alguna de las herramientas disponibles del agente"""
        
        tools_data: Dict = session.tools_data
        router_tool: RouterToolModel = tools_data.get("router_tool")
        qa_model: QAToolModel = tools_data.get("qa_tool")
        visit_model: VisitToolModel = tools_data.get("visit_tool")

        print(f"HISTORIAL: {json.dumps(history)}")

        try:
            #------MODIFICACIÓN DINÁMICA DE LAS INSTRUCCIONES
            tool_instructions = cls.tool_instructions
            if not qa_model.presented_inms:
                tool_instructions = [item for item in tool_instructions if item["key"]!="visita"]
            if router_tool.is_answer_name:
                tool_instructions = [item for item in tool_instructions if item["key"]!="off-topic"]

            valid_values = [item["key"] for item in tool_instructions]

            #------CADENA ENRUTADORA
            result = await cls.classification_chain.ainvoke({
                "input": input, 
                "history": json.dumps(history), 
                "tool_instructions": json.dumps(tool_instructions),
                "valid_values": str(valid_values)
            })
            if result.startswith("[") and result.endswith("]"):
                result = ast.literal_eval(result)[0]

            print(f"CADENA ENRUTADURA: {result}")

            router_tool.is_answer_name = False

        except Exception as e:
             logger.error(f"Error in router context access: {e}")
             raise Exception(f"Error in router context access: {e}")

        #------HERRAMIENTAS DEL AGENTE IA
        # Es necesario que todas las instancias dinámicas pasadas a las cadenas sean diccionarios para asegurar la mutabilidad
        result = result.strip('"\'')
        if result not in valid_values:
            result = ""

        if result == "busqueda":
            async for message in QAChain.execute(input, qa_model, user_name): # Herramienta Text2SQL
                yield message
            yield {"type": "metadata", "key": "tool", "content": "busqueda"}

        elif result == "info":
            async for message in RagChain.query_rag(input, history, user_name): # Herramienta RAG
                yield message
            yield {"type": "metadata", "key": "tool", "content": "info"}

        elif result == "visita":
            async for message in VisitChain.execute(input, visit_model, qa_model.presented_inms, user_name, session.personal_data): # Herramienta de organización de visitas
                yield message
            yield {"type": "metadata", "key": "tool", "content": "visita"}

        elif result == "contacto": 
            async for message in cls.contact_chain.astream({"input": input, "contact_info": cls.contact_info, "user_name": user_name}): # Herramienta de contacto
                yield {"type": "text", "content": message}
            yield {"type": "metadata", "key": "chain", "content": "contact_chain"}
            yield {"type": "metadata", "key": "tool", "content": "contacto"}

        elif result == "nombre": 
            user_name = await cls.name_chain.ainvoke({"input": input})
            session.name = user_name
            async for message in cls.answer_name_chain.astream({"input": input, "user_name": user_name}):
                yield {"type": "text", "content": message}
            yield {"type": "metadata", "key": "chain", "content": "answer_name_chain"}
            yield {"type": "metadata", "key": "tool", "content": "nombre"}

        elif result == "bienvenida":
            if not user_name:
                router_tool.is_answer_name = True
            async for message in cls.presentation_chain.astream({"input": input, "user_name": user_name}):
                yield {"type": "text", "content": message}
            yield {"type": "metadata", "key": "chain", "content": "presentation_chain"}
            yield {"type": "metadata", "key": "tool", "content": "bienvenida"}

        elif result == "off-topic": 
            async for message in cls.off_topic_chain.astream({"input": input}):
                yield {"type": "text", "content": message}
            yield {"type": "metadata", "key": "chain", "content": "off_topic_chain"}
            yield {"type": "metadata", "key": "tool", "content": "off-topic"}
    

      #self.enrouting_chain = {"route": self.classification_chain, "input": lambda x: x["input"], "history": lambda x: x["history"] } | RunnableLambda(self.route) # Cadena de enrutamiento


