from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnableGenerator
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_core.output_parsers import StrOutputParser
from langchain.output_parsers import BooleanOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import AIMessage
import asyncio
from langchain_core.callbacks import BaseCallbackHandler
from typing import Any, Dict, List
from src.utilities import *
from src.directories import (
    FORMAT_QUERY_PROMPT_dir,
    QUERY_EXAMPLES_dir,
    GENERATE_SQL_QUERY_PROMPT_dir, 
    DB_DIR,
    ANSWER_QUERY_PROMPT_dir,
    TABLE_DESCRIPTION_inm_dir,
    CHECK_QUERY_PROMPT_dir,
    NEW_SEARCH_PROMPT_dir,
    db_name,
    db_search_callback
)
import os
from src.config.base_models import generate_qa_llm, generate_check_llm
import logging
import re


#----------------------------------------------------------------------------------------------------------


# GENERAMOS LAS PLANTILLAS PARA CADA PROMPT
database_path = os.path.join(DB_DIR, f"{db_name}.db")
NEW_SEARCH_PROMPT = txt_to_str(NEW_SEARCH_PROMPT_dir)
TABLE_DESCRIPTION = txt_to_dict(TABLE_DESCRIPTION_inm_dir)
CHECK_QUERY_PROMPT = txt_to_str(CHECK_QUERY_PROMPT_dir)
QUERY_EXAMPLES = txt_to_list_dict(QUERY_EXAMPLES_dir)
ANSWER_QUERY_PROMPT = txt_to_str(ANSWER_QUERY_PROMPT_dir)
FORMAT_QUERY_PROMPT = txt_to_str(FORMAT_QUERY_PROMPT_dir)
GENERATE_SQL_QUERY_PROMPT = txt_to_str(filepath = GENERATE_SQL_QUERY_PROMPT_dir)

ANSWER_QUERY_PROMPT = ANSWER_QUERY_PROMPT.format(columns_description = "", input = "{input}", result = "{result}")
    # Esta función convierte un diccionario con tipos de datos en forma de string a un diccionario con tipos de datos de Python.
TABLE_DESCRIPTION = string_to_type(TABLE_DESCRIPTION)

logger = logging.getLogger(__name__)


class QAChain:
    
    def __init__(self):

        self.result = None

        # Función callback
        self.send_to_client = None
        
        # Variable que se activa solo cuando se ejecuta una nueva búsqueda.
        self.new_search = True

        #Variable que se activa para permtir el bucle de completitud de consulta.
        self.need_more_info_for_query = False

        # Campos requeridos para ejecutar una consulta SQL
        self.required_fields = ["tipo", "operacion", "poblacion"]

        # MODELOS DE LENGUAJE
        self.text2sql_llm = generate_qa_llm()

        self.check_llm = generate_check_llm()

        # BASE DE DATOS
        self.database_path = os.path.join(DB_DIR, f"{db_name}.db")

        self.db = SQLDatabase.from_uri(
            f"sqlite:///{database_path}",
            sample_rows_in_table_info = 4, #Número de filas de ejemplo
        )

        # PROMPTS
        self.text2sql_prompt = PromptTemplate.from_template(GENERATE_SQL_QUERY_PROMPT) # Prompt para la tarea text2sql

        self.new_search_prompt = PromptTemplate.from_template(NEW_SEARCH_PROMPT) # Prompt para chequear si se requiere o no nueva búsqueda
        
        self.answer_query_prompt = PromptTemplate.from_template(ANSWER_QUERY_PROMPT) # Prompt para responder a la consulta SQL
        
        self.check_query_prompt = PromptTemplate.from_template(CHECK_QUERY_PROMPT) # Prompt para indicar al cliente que es necesaria más información.
        
        # Diccionario para arrancar la búsqueda en base de datos
        self.dict_text2sql = {
            "input": "",
            "dialect": self.db.dialect,
            "table_info": self.db.table_info,
            "top_k": 3
        }
    
        # CADENAS
        # Cadena para para chequear si se requiere o no nueva búsqueda
        self.check_new_search_chain = self.new_search_prompt | self.check_llm | BooleanOutputParser(false_val="False", true_val="True")

        # Cadena que text2sql con un parsing final para evitar consultas SQL sintácticamente incorrectas
        self.text2sql_chain = self.text2sql_prompt | self.text2sql_llm | RunnableLambda(self.parsing_sql_query)

        # Cadena que genera la consulta SQL y pasa el input a la siguiente
        self.route_text2sql_chain = RunnableParallel({
            "input": lambda input: input["input"],
            "sql_query": self.text2sql_chain
        })

        # Convertimos la función de chequear la consulta en un Runnable
        self.check_query = RunnableLambda(lambda x: self.check_fields_in_query(x))

        # Indicamos el diccionario que debería devolver
        self.route_check_query_chain = RunnableParallel({
            "input": lambda input: input["input"],
            "sql_query": lambda input: input["sql_query"],
            "missing_fields": self.check_query
        })

        # Esta cadena devuelve tanto el input, como la consulta SQL y la lista de campos requeridos faltantes 
        self.full_text2sql_chain = self.route_text2sql_chain | self.route_check_query_chain

        # Convertimos la función de ejecutar consulta SQL la consulta en un Runnable
        self.execute_query = RunnableGenerator(self.route)

        # Cadena completa
        self.full_chain = self.full_text2sql_chain | self.execute_query

        # Cadena cuando falta en la consulta SQL alguno de los campos requeridos 
        self.missing_fields_chain = self.check_query_prompt | self.check_llm | StrOutputParser()

        # Cadena cuando se considera que ya se ha recuperado información de la base de datos y se trata de responder al cliente
        self.answer_chain = self.answer_query_prompt | self.check_llm | StrOutputParser()

 
    # Función para chequear que la consulta SQL contiene los campos requeridos. Si no hay campos requeridos, retorna una lista vacía
    def check_fields_in_query(self, info: Dict) -> List[str]:
        query = info["sql_query"]
        missing_fields_list = []
        
        if self.required_fields:
            # Verifica que todos los campos requeridos estén en la consulta
            fields_in_query = re.findall(r'\b\w+\b', query.lower())
            
            # Filtra y mantiene solo los campos que están en la lista de requeridos
            missing_fields_list = [field for field in self.required_fields if field.lower() not in fields_in_query]
            
        return missing_fields_list
    

    # Función para tratar la consuta SQL que devuelve el LLM
    def parsing_sql_query(self, raw_query: AIMessage) -> str:
        if hasattr(raw_query, 'content'):
            raw_query = raw_query.content
        # Remueve las comillas invertidas si están presentes
        cleaned_query = raw_query.strip().strip('```').strip()
        
        # Si las comillas invertidas están al principio y al final, quítalas
        if cleaned_query.startswith("sql"):
            cleaned_query = cleaned_query[3:].strip()

        return cleaned_query


    # Esta función recoge la consulta y los campos faltantes, ejecuta la consulta y responde al cliente
    async def route(self, info):
        async for message in info:
            print("MENSAJE:", message)
            yield message
        """
        query = info["sql_query"]
        input = info["input"]

        if not any(field in info["missing_fields"] for field in self.required_fields):
            try:
                await self.send_to_client("loading:start")
                self.result = await self.db.run("query") # Ejecutamos la consulta SQL
            except Exception as e:
                logger.info("ERROR: SQL execution against database failed")
                raise Exception(status_code=500, detail=f"ERROR: SQL execution against database failed:" + str(e))
            try:
                answer = await self.answer_chain.ainvoke({"input": input, "result": self.result}) # Respondemos al cliente
                await self.send_to_client("loading:end")
                yield answer
            except Exception as e:
                logger.info("ERROR: response chain failed")
        else:
            try:
                answer = await self.missing_fields_chain.ainvoke({"input": input}) # Indicamos al cliente que faltan campos en la consulta SQL
                yield answer
            except Exception as e:
                logger.info("ERROR: 'missing fields' chain failed")
        """
    
    # Función que enruta según el resultado de la cadena check_new_search_chain. 
    # Un filtro para evitar que se realice nuevas búsquedas cuando no son reclamadas por el usuario
    async def check_last_query(self, input: str, history):
        # Comprobamos si es necesaria una nueva búsqueda
        try:
            self.search_result = await self.check_new_search_chain.ainvoke({"input": input, "history": history})
        except Exception as e:
            logger.info("ERROR: 'checking new search' chain failed:")
            raise Exception(status_code=500, detail="ERROR: 'checking new search' chain failed:" + str(e))
        
        # En función del resultado enrutamos hacia una u otra cadena        
        if self.new_search == False and self.need_more_info_for_query == False:
            # Si la petición del cliente está relacionado con la consulta realizada previamente y esa consulta ya ha sido completada.
            try:
                answer = await self.answer_chain.ainvoke({"input": input, "result": self.result})
                yield answer
            except Exception as e:
                logger.info("ERROR: answe chain chain failed")
                raise Exception(status_code=500, detail="ERROR: answe chain chain failed:" + str(e))
        else:
            # Si el cliente reclama una nueva búsqueda o que todavía no se ha completado la consulta.
            self.dict_text2sql["input"] = input 
            self.new_search = True
            try:
                async for message in self.full_chain.astream(self.dict_text2sql):
                    yield message
            except Exception as e:
                logger.info("ERROR: 'generating query' chain failed")
                raise Exception(status_code=500, detail="ERROR: 'generating query' chain failed:" + str(e))
            
    
    # Setter para el callback
    def set_send_to_client(self, send_to_client):
        self.send_to_client = send_to_client