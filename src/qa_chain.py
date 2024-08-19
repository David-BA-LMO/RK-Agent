from langchain_core.example_selectors import SemanticSimilarityExampleSelector
from langchain.chains import create_sql_query_chain
import pandas as pd
import sqlite3
from langchain_openai import OpenAIEmbeddings
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_core.output_parsers import JsonOutputParser
from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import (
    FewShotPromptTemplate,
    ChatPromptTemplate,
    PromptTemplate)
from src.utilities import *
from src.directories import (
    FORMAT_QUERY_PROMPT_dir,
    QUERY_EXAMPLES_dir, 
    COLUMNS_DESCRIPTION_dir, 
    GENERATE_SQL_QUERY_PROMPT_dir, 
    DB_DIR,
    ANSWER_QUERY_PROMPT_dir,
    TABLE_DESCRIPTION_inm_dir,
    CHECK_QUERY_PROMPT_dir,
    NEW_SEARCH_PROMPT_dir,
    db_name
)
import os
from src.config.base_models import generate_qa_llm


fields_required = ["tipo", "operacion", "poblacion"]


#----------------------------------------------------------------------------------------------------------


# GENERAMOS LAS PLANTILLAS PARA CADA PROMPT
database_path = os.path.join(DB_DIR, f"{db_name}.db")
COLUMNS_DESCRIPTION_txt = txt_to_str(COLUMNS_DESCRIPTION_dir)
COLUMNS_DESCRIPTION_dict = txt_to_dict(COLUMNS_DESCRIPTION_dir)
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


class QAChain:

    def __init__(self):
        self.llm = generate_qa_llm()
        #--------------------------------------------------------------------
        # GENERACIÓN DE LA BASE DE DATOS
        self.db = SQLDatabase.from_uri(
                        f"sqlite:///{database_path}",
                        sample_rows_in_table_info = 0, #Número de filas de ejemplo
                        #custom_table_info = TABLE_DESCRIPTION,
                        include_tables = ""
                )
        #context = db.get_context()
        #print(context["table_info"]) #Información de las tablas de la base de datos.
        self.sql_dialect = self.db.dialect

        #--------------------------------------------------------------------
        # GENERACIÓN DEL SELECTOR DE EJEMPLOS DE CONSULTAS SQL
        self.example_selector = SemanticSimilarityExampleSelector.from_examples(
                    QUERY_EXAMPLES,
                    OpenAIEmbeddings(),
                    FAISS,
                    k = 2,
                    input_keys=["input"],
            )

        #--------------------------------------------------------------------
        # GENERACIÓN DEL PROMPT Y CADENA PARA CREACIÓN DE CONSULTA SQL
        self.few_shot_prompt = FewShotPromptTemplate(
                #examples = examples, #solo cuando no incorporamos un example_selector.
                example_selector = self.example_selector,
                example_prompt = PromptTemplate.from_template("Input: {input}\nAI: {query}"),
                prefix = f"{GENERATE_SQL_QUERY_PROMPT}",
                suffix = "\nInput: {input}\nSQL query: ", #obligatorio
                input_variables=["input", "top_k", "table_info", "dialect"], #Estos argumentos son exigidos por el generador de consultas.
            )
    
        # Cadena de generación de consulta SQL. Si se incluye un prompt, es necesario que este incluya los args 'top_k' y 'table_info'
        self.generate_query = create_sql_query_chain(
                llm = self.llm, 
                db = self.db,
                prompt = self.few_shot_prompt
        )

        #Cadena que genera una consulta SQL a partir de texto y la ejecuta contra la base de datos
        self.sql_chain = self.generate_query | self.execute_query | StrOutputParser()

        #--------------------------------------------------------------------
        # 3 - EJECUCIÓN DE CONSULTA Y FORMATO DE RESPUESTA
        # Prompt que recoge la la consulta definitiva en formato JSON y la información recuperada de la base de datos
        self.answer_prompt = ChatPromptTemplate.from_template(ANSWER_QUERY_PROMPT)
        # Cadena para presentar la información recuperada de la base de datos
        self.answer_chain = self.answer_prompt | self.llm | StrOutputParser()

        # Variable que se activa solo cuando se ejecuta una nueva búsqueda.
        self.new_search = True
        # Variable donde recogemos la consulta formateada recopilada en la conversación con el cliente
        self.definitive_human_query = None
        # Variable donde recogemos la información recuperada de la base de datos.
        self.query_result = None

         #--------------------------------------------------------------------
        # 2 - CAPTURA DE LOS CRITERIOS DE BÚSQUEDA 
        # Esta función genera una clase Pydantic cuyas variables están sacadas de las claves de dos diccionarios. Uno de ellos contiene como valores las descripciones de la variable, el otro el tipo de dato
        self.QueryFormat = pydantic_class_by_dict("DatabaseFilters", descriptions = COLUMNS_DESCRIPTION_dict, types = TABLE_DESCRIPTION)
        #print(DatabaseFilters.model_json_schema())

        # Formato JSON de salida para la cadena de formateo
        self.JSONparser = JsonOutputParser(pydantic_object=self.QueryFormat)

        # Prompt con las instrucciones para formatear la consulta del cliente
        self.format_query_prompt = PromptTemplate(
            template= FORMAT_QUERY_PROMPT,
            input_variables=["query", "history"],
            partial_variables={"format_instructions": self.JSONparser.get_format_instructions()},
        )

        # Cadena para formatear la consulta del cliente
        self.format_query_chain = self.format_query_prompt | self.llm | self.JSONparser

        # Prompt con las instrucciones para comprobar que la consulta está completa
        self.check_query_prompt = PromptTemplate.from_template(CHECK_QUERY_PROMPT)
        
        # Cadena para comprobar que la consulta está completa
        self.check_query_chain = self.check_query_prompt | self.llm | StrOutputParser()

        #Variable que se activa para permtir el bucle de completitud de consulta.
        self.need_more_info_for_query = False

        #--------------------------------------------------------------------
        # 1 - COMPROBACIÓN DE NECESIDAD DE USO MEMORIA
        # Prompt que recoge el último input del cliente y el historial de conversación
        self.new_search_prompt = PromptTemplate.from_template(NEW_SEARCH_PROMPT)

        # Cadena para comprobar si el último mensaje se relaciona con la conversación previa o exige una nueva búsqueda
        self.check_new_search_chain = self.new_search_prompt | self.llm | StrOutputParser()


    #--------------------------------------------------------------------
    # EJECUCIÓN DE LA CONSULTA SQL
    # La ejecución de la consulta la realizaremos con Pandas, de manera que se genera un DataFrame con los nombres de las columnas.
    def execute_query(self, query):
        print("Consulta SQL: ",query)
        conn = sqlite3.connect(self.database_path)
        try:
            df = pd.read_sql_query(query, conn)
        except Exception as e:
            print("Error en la consulta: ", e)
        print(df)
        if df.empty:
            return "Lo sentimos, pero no disponemos de momento de ningún inmueble con esas características"
        else:
            return df.iloc[0].to_string()

 
    def get_database_content(self, input):
        if self.new_search:
            # Este es el caso en el que generamos una nueva búsqueda (new_search = True.
            elements = [f"{k}: {v}" for k, v in self.definitive_human_query.items()]
            elements_chain = ", ".join(elements)
            final_human_query = str(elements_chain)
            self.query_result = self.sql_chain.invoke({"question": final_human_query}) # GENERACIÓN DE CONSULTA SQL
            print("Resultado de la consulta: ", self.query_result)
            return self.answer_chain.invoke({"input": input, "result": self.query_result})
        else:
            # Este es el caso en el que ya hemos recuperado la información de la base de datos (new_search = False) y no es necesario ejecutar una nueva búsqueda ni consulta.
            return self.answer_chain.invoke({"input": input, "result": self.query_result})


    # Función para comprobar si la salida de la cadena de formateo es correcta. 
    # Si faltan campos, enruta hacia la cadena que exige al cliente completar esos campos. 
    # Si está completa redirige a la cadena de generación y ejecución de consultas SQL contra la base de datos
    def check_query(self, input, history, fields_required=fields_required):

        output = self.format_query_chain.invoke({"input": input, "history": history.messages})
        history.add_ai_message(str(output))

        # "output" es un diccionario que recoge las indicaciones del cliente para luego ser usadas en la consulta a la base de datos.
        # Por optimización, eliminamos todos los valores del diccionario con valores nulos.
        output = {k: value for k, value in output.items() if value is not None}

        # Verifica si todas las claves requeridas están en el diccionario "output".
        check = all(key in output for key in fields_required)
        print("Resultado:", output, "\nCampos: ",fields_required)
        if check:
            # Ruta para generar y ejecutar una consulta SQL en función de la consulta del cliente.
            self.need_more_info_for_query = False
            self.definitive_human_query = output
            return str(output), self.get_database_content(input)
        else:
            # Ruta para exigir la completitud de la consulta al cliente
            self.need_more_info_for_query = True
            re_format_query = self.check_query_chain.invoke({"input": output})
            return str(output), re_format_query
        


    # Función enrutadora según el resultado de la cadena check_new_search_chain.
    def check_last_query(self, input, history):

        new_search = self.check_new_search_chain.invoke({"input": input, "history": history.messages})
        
        if new_search == "False" and self.need_more_info_for_query == False:
            # Si la petición del cliente está relacionado con la consulta realizada previamente y esa consulta ya ha sido completada.
            return self.get_database_content(input)
        else:
            # Entendemos que el cliente reclama una nueva búsqueda o que todavía no se ha completado la consulta. Pasamos a la función que formatea y comprueba la consulta del cliente
            new_search = True
            return self.check_query(input, history)

    
