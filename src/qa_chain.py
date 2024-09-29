import os
import re
import asyncio
from sqlalchemy.exc import OperationalError, IntegrityError, SQLAlchemyError
from langchain_core.runnables import RunnableLambda
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_core.output_parsers import StrOutputParser
from langchain.output_parsers import BooleanOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import AIMessage
from typing import Dict, AsyncGenerator, List
from session_manager import SessionData
from src.utilities import *
from src.directories import (
    GENERATE_SQL_QUERY_PROMPT_dir, 
    DB_DIR,
    ANSWER_QUERY_PROMPT_dir,
    CHECK_QUERY_PROMPT_dir,
    NEW_SEARCH_PROMPT_dir,
    db_name,
)
from src.config.base_models import generate_qa_llm, generate_check_llm
from src.format_answer import qa_format_text
import logging



#----------------------------------------------------------------------------------------------------------


# GENERAMOS LAS PLANTILLAS PARA CADA PROMPT
database_path = os.path.join(DB_DIR, f"{db_name}.db")
NEW_SEARCH_PROMPT = txt_to_str(NEW_SEARCH_PROMPT_dir)
CHECK_QUERY_PROMPT = txt_to_str(CHECK_QUERY_PROMPT_dir)
ANSWER_QUERY_PROMPT = txt_to_str(ANSWER_QUERY_PROMPT_dir)
GENERATE_SQL_QUERY_PROMPT = txt_to_str(GENERATE_SQL_QUERY_PROMPT_dir)

logger = logging.getLogger(__name__)


class QAChain:
    
    def __init__(self):
        # Inicializamos el lock para la clase
        self.lock = asyncio.Lock()

        # Campos requeridos para ejecutar una consulta SQL
        self.required_fields = ["tipo", "operacion", "poblacion"]

        # MODELOS DE LENGUAJE
        self.text2sql_llm = generate_qa_llm()

        self.check_llm = generate_check_llm()

        # CONEXIÓN A BASE DE DATOS
        self.database_path = os.path.join(DB_DIR, f"{db_name}.db")
        self.db = None
        self._dialect = None
        self._table_info = None

        # PROMPTS
        self.text2sql_prompt = PromptTemplate.from_template(GENERATE_SQL_QUERY_PROMPT) # Prompt para la tarea text2sql
        self.new_search_prompt = PromptTemplate.from_template(NEW_SEARCH_PROMPT) # Prompt para chequear si se requiere o no nueva búsqueda
        self.answer_query_prompt = PromptTemplate.from_template(ANSWER_QUERY_PROMPT) # Prompt para responder a la consulta SQL 
        self.check_query_prompt = PromptTemplate.from_template(CHECK_QUERY_PROMPT) # Prompt para indicar al cliente que es necesaria más información.
        
        # Diccionario para arrancar la búsqueda en base de datos
        self.dict_text2sql = {
            "input": "",
            "dialect": None,
            "table_info": None,
            "top_k": 3,
            "last_query": ""
        }
    
        # CADENAS
        # Cadena para para chequear si se requiere o no nueva búsqueda
        self.check_new_search_chain = self.new_search_prompt | self.check_llm | BooleanOutputParser(false_val="False", true_val="True")

        # Cadena text2sql con un parsing final para evitar consultas SQL sintácticamente incorrectas
        self.text2sql_chain = self.text2sql_prompt | self.text2sql_llm | RunnableLambda(self.parsing_sql_query)

        # Convertimos la función de chequear la consulta en un Runnable
        self.check_query = RunnableLambda(lambda x: self.check_fields_in_query(x))

        # Indicamos el diccionario que debería devolver
        self.route_check_query_chain = self.text2sql_chain | self.check_query

        # Cadena cuando falta en la consulta SQL alguno de los campos requeridos 
        self.missing_fields_chain = self.check_query_prompt | self.check_llm | StrOutputParser()

        # Cadena cuando se considera que ya se ha recuperado información de la base de datos y se trata de responder al cliente
        self.answer_chain = self.answer_query_prompt | self.text2sql_llm | StrOutputParser()

 
    # Función para chequear que la consulta SQL contiene los campos requeridos. Si no hay campos requeridos, retorna una lista vacía
    def check_fields_in_query(self, info: Dict) -> List[str]:
        self.last_query = info["sql_query"]
        query = info["sql_query"]
        fields_in_query = []
        try:
            if self.required_fields:
                # Encuentra todos los campos en la consulta
                fields_in_query = re.findall(r'\b\w+\b', query.lower())
                
                # Filtra los campos de la consulta que NO están en self.missing_fields
                fields_not_in_missing = [field for field in self.required_fields if field.lower() not in fields_in_query]
            else:
                fields_not_in_missing = []
        except Exception as e:
            logger.error("Cannot check missing fields: "+str(e))
        
        return {"sql_query": query, "missing_fields": fields_not_in_missing}
    

    # Función para tratar la consuta SQL que devuelve el LLM
    def parsing_sql_query(self, raw_query: AIMessage) -> str:
        if hasattr(raw_query, 'content'):
            raw_query = raw_query.content
        # Remueve las comillas invertidas si están presentes
        cleaned_query = raw_query.strip().strip('```').strip()
        
        # Si las comillas invertidas están al principio y al final, quítalas
        if cleaned_query.startswith("sql"):
            cleaned_query = cleaned_query[3:].strip()

        return {"sql_query": cleaned_query}
    

    #-----EJECUCIÓN CONTRA LA BASE DE DATOS------
    def execute_query(self, sql_query: str):
        try:
            return self.db.run(sql_query) 
        except OperationalError as op_err:
            logger.error(f"OperationalError during SQL execution: {op_err}")
            raise Exception(status_code=500, detail="ERROR: Operational error during SQL execution.")
        except IntegrityError as int_err:
            logger.error(f"IntegrityError during SQL execution: {int_err}")
            raise Exception(status_code=500, detail="ERROR: Integrity constraint violated during SQL execution.")
        except TimeoutError as timeout_err:
            logger.error(f"Timeout during SQL execution: {timeout_err}")
            raise Exception(status_code=504, detail="ERROR: SQL execution timed out.")
        except SQLAlchemyError as sql_err:
            logger.error(f"General SQLAlchemy error during SQL execution: {sql_err}")
            raise Exception(status_code=500, detail="ERROR: A database error occurred during SQL execution.")
        except Exception as e:
            logger.info("SQL execution against database failed")
            raise Exception(status_code=500, detail=f"ERROR: SQL execution against database failed:" + str(e))



    #------ENRUTADOR------
    async def route(self, info: Dict, input: str, session: SessionData, history: str) -> AsyncGenerator[str, None]:
        """
        Esta función enruta hacia la ejecución y respuesta de la consulta si no hay campos faltantes, o
        hacia una cadena específica para pedir información al usuario. Toma estos parámetros:
            - input: input del usuario.
            - sql_query(str): consulta SQL. Pasado en el dict "info".
            - missing_fields(List): campos faltantes. Pasado en el dict "info".
        Devuelve un generador asincrónico.
        """
        result = ""
        if not info["missing_fields"]:
            # Ejecutamos la consulta SQL
            yield "loading-db:start"
            result = self.execute_query(info["sql_query"])

            # Actualizamos la sesión
            async with self.lock:
                if(result):
                    session.qa_data["result"] = result # Actualización de "result" en sesión
                    text_sql = {"input": input, "sql": info["sql_query"]}
                    session.qa_data["sql_queries"].append(text_sql) # Actualización de "sql_queries" en sesión
            logger.info("RESULTADO: "+ str(result))
            logger.info("RESULTADO EN SESIÓN: "+str(session.qa_data["result"]))

            # Respondemos
            async for partial_message in self.answer_result(input, history, session):
                yield partial_message
        # Si existen campos faltantes avisamos al usuario de la necesidad de aportar más información
        else:
            try:
                answer = await self.missing_fields_chain.ainvoke({"input": input, "missing_fields": info["missing_fields"]}) # Indicamos al cliente que faltan campos en la consulta SQL
                yield answer
            except Exception as e:
                logger.error("'missing fields' chain failed")

    

    #------GENERACIÓN DE SQL------
    async def generate_query(self, input: str, session: SessionData) -> str:
        """
        Esta función genera la consulta SQL tomando estos parámetros:
            - input(str): input del cliente.
            - last_query (Dict): cláusulas WHERE de la consulta realizada previamente. No tiene por qué haber sido ejecutada. Recogida de la sesión.
        Devuelve un diccionario con dos valores:
            - missing_fields(List): campos faltantes necesarios para ejecutar la consulta SQL
            - sql_query(str): consulta SQL.
        """
        self.open_db_connection()
        dict_prompt = self.dict_text2sql
        dict_prompt["input"] = input
        if(session.qa_data["last_query"]!=None):
            dict_prompt["last_query"] = str(session.qa_data["last_query"])

        answer = None
        # Generamos la consulta SQL
        try:
            logger.info("COMPLETE PROMPT "+ str(dict_prompt))
            answer = await self.route_check_query_chain.ainvoke(dict_prompt) # Esta cadena devuelve el la consulta SQL y los campos faltantes si los hubiera
        except Exception as e:
            logger.error("Text2SQL chain failed: "+ str(e))
            raise Exception(status_code=500, detail="ERROR: Text2SQL chain failed:" + str(e))
        async with self.lock:
            logger.info("NUEVA QUERY: "+ answer["sql_query"])
            session.qa_data["missing_fields"] = answer["missing_fields"]    # Actualización de "missing_fields" en sesión
            logger.info("DICT DE CLAUSULAS: "+ str(extract_where_clauses(answer["sql_query"])))
            session.qa_data["last_query"] = extract_where_clauses(answer["sql_query"])     # Actualización de "last_query" en sesión:
        return answer



    #------GENERACIÓN DE RESPUESTA------
    async def answer_result(self, input: str, history: str, session: SessionData) -> AsyncGenerator[str, None]:
        """
        Esta función genera la consulta SQL tomando estos parámetros:
            - input (str): input del cliente.
            - result (str): resultado obtenido previamente. Recogida de la sesión.
            - history (str): historial de conversación
        Devuelve un generador asincrónico.
        """
        try:
            yield "loading-db:end"
            async for partial_answer in self.answer_chain.astream({"input": input, "result": str(session.qa_data["result"]), "history": history}):
                yield partial_answer
        except Exception as e:
            logger.error(f"ERROR: answer chain failed: {e}")
            raise Exception(status_code=500, detail=f"ERROR: answer chain chain failed: {e}")


    # Función que enruta toda la herramienta QA
    async def execute(self, input: str, history: str, session: SessionData) -> AsyncGenerator[str, None]:
        
        # Comprobamos si hay campos faltantes
        missing_fields = None
        if(len(session.qa_data["missing_fields"])>0):
            missing_fields = ' '.join(map(str, session.qa_data["missing_fields"]))
        else:
            missing_fields = ''

        # ¿Está el usuario solicitando una nueva búsqueda?
        new_search_answer = True
        try:
            new_search_answer = await self.check_new_search_chain.ainvoke({"input": input, "history": history, "missing_fields": missing_fields})
            async with self.lock:
                session.qa_data["new_search"] = new_search_answer   # Actualización de "new_search" en sesión
        except Exception as e:
            logger.error(f"'checking new search' chain failed: {e}")
            raise Exception(status_code=500, detail="ERROR: 'checking new search' chain failed:" + str(e))

        # Si consulta ya se ha ejecutado: "new_search" = False.
        if session.qa_data["new_search"] == False:
            async for partial_answer in self.answer_result(input = input, session = session, history = history):
                yield partial_answer
        # Si el cliente reclama una nueva búsqueda o que todavía no se ha completado la consulta: "new_search" = True.
        else:
            info = await self.generate_query(input, session)
            async for partial_answer in self.route(info = info, input = input, session = session, history = history):
                yield partial_answer


    def open_db_connection(self):
        """
        Asegura que la conexión a la base de datos está abierta. Si no lo está, la abre.
        También cachea `table_info` y `dialect` después de la primera conexión.
        """
        if self.db is None:
            self.db = SQLDatabase.from_uri(f"sqlite:///{self.database_path}", sample_rows_in_table_info=4)
            
            self._dialect = self.db.dialect
            self._table_info = self.db.table_info

            self.dict_text2sql["dialect"] = self._dialect
            self.dict_text2sql["table_info"] = self._table_info


                

            
            
    