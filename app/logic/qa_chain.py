import json
import logging
from pprint import pprint
import sqlite3
import re
from langchain_core.runnables import RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from typing import AsyncGenerator, List, Dict

from app.utils.general_utilities import open_txt, open_json
from app.logic.tool_config.base_models import generate_qa_llm, generate_check_llm
from app.data_generation.sql_search_generation import execute_sql_query
from app.schemas.tools import QAToolModel
from app.config import (
    GENERATE_SQL_QUERY_PROMPT_dir,
    GENERIC_ANSWER_PROMPT_dir,
    CHECK_QUERY_PROMPT_dir,
    BROAD_QUERY_PROMPT_dir,
    QA_GENERAL_PROMPT_dir,
    SPECIFIC_ANSWER_PROMPT_dir,
    QA_TOOL_EXPLANATION_dir,
    columns_dir,
    tool_instructions_dir,
    search_table_generation_query_dir
)
from app.logic.tool_utilities.qa_utilities import (
    generate_sql_ids,
    filter_presentation_fields,
    general_presentation_dict,
    check_fields_in_query,
    merge_sql_queries,
    add_id_exclusion,
    parsing_sql_query,
    specific_presentation_dict,
    modify_query,
    extract_column_by_priority,
    reclame_localization,
    city_localization,
    add_geospatial_filter,
    modify_sql_prioridadrk,
    parse_db_answer
)

#----------------------------------------------------------------------------------------------------------

logger = logging.getLogger(__name__)


class QAChain:

    # ------PLANTILLAS DE PROMPTS------
    QA_GENERAL_PROMPT = open_txt(QA_GENERAL_PROMPT_dir)
    CHECK_QUERY_PROMPT = open_txt(CHECK_QUERY_PROMPT_dir)
    GENERIC_ANSWER_PROMPT = open_txt(GENERIC_ANSWER_PROMPT_dir)
    GENERATE_SQL_QUERY_PROMPT = open_txt(GENERATE_SQL_QUERY_PROMPT_dir)
    BROAD_QUERY_PROMPT = open_txt(BROAD_QUERY_PROMPT_dir)
    SPECIFIC_ANSWER_PROMPT = open_txt(SPECIFIC_ANSWER_PROMPT_dir)
    QA_TOOL_EXPLANATION = open_txt(QA_TOOL_EXPLANATION_dir)

    # Columnas de la base de datos. Obtenidas a partir de un JSON
    column_names = ["Id"]
    with open(columns_dir, "r", encoding="utf-8") as file:
        data = json.load(file)
        json_columns = data.get("api_columns", []) + data.get("enrichment_columns", [])
    for col in json_columns:
        if col.get("search"): 
            col_name = col.get("name")
            column_names.append(col_name)


    # ------MODELOS DE LENGUAJE------
    text2sql_llm = generate_qa_llm()
    check_llm = generate_check_llm()
    qa_general_llm = generate_check_llm()

    dialect = "sqlite"
    table_info = open_txt(search_table_generation_query_dir)

    # ------PROMPTS------
    text2sql_prompt  = PromptTemplate.from_template(GENERATE_SQL_QUERY_PROMPT)
    qa_general_prompt = PromptTemplate.from_template(QA_GENERAL_PROMPT) # Prompt para chequear si se requiere o no nueva búsqueda
    generic_answer_prompt = PromptTemplate.from_template(GENERIC_ANSWER_PROMPT) # Prompt para responder a la consulta SQL 
    check_query_prompt = PromptTemplate.from_template(CHECK_QUERY_PROMPT) # Prompt para indicar al cliente que es necesaria más información.
    broad_query_prompt = PromptTemplate.from_template(BROAD_QUERY_PROMPT)
    specific_answer_prompt = PromptTemplate.from_template(SPECIFIC_ANSWER_PROMPT)
    qa_tool_explanation_prompt = PromptTemplate.from_template(QA_TOOL_EXPLANATION)


    # ------CADENAS------
    # Cadena general para conocer las intenciones del usuario: si desea una nueva búsqueda o más información sobre un inmueble ya localizado.
    qa_general_chain = qa_general_prompt | qa_general_llm | StrOutputParser()

    # Cadena para resolver dudas acerca del procedimiento de búsqueda de inmuebles
    qa_tool_explanation_chain = qa_tool_explanation_prompt | qa_general_llm | StrOutputParser()

    # Cadena text2sql con un parsing final para evitar consultas SQL sintácticamente incorrectas
    text2sql_chain = text2sql_prompt | text2sql_llm | RunnableLambda(parsing_sql_query)

    # Cadena cuando falta en la consulta SQL alguno de los campos requeridos 
    missing_fields_chain = check_query_prompt | check_llm | StrOutputParser()

    # Cadena para responder al usuario sobre la recuperación (exitosa o no) de resultados
    generic_answer_chain = generic_answer_prompt | text2sql_llm | StrOutputParser()

    # Cadena para presentar información detallada de un solo Inmueble.
    specific_answer_chain = specific_answer_prompt | text2sql_llm | StrOutputParser()

    # Consulta para generar una nueva consulta SQL más laxa cuando no se han encontrado datos
    broad_query_chain = broad_query_prompt | text2sql_llm |  RunnableLambda(parsing_sql_query)


    # ------INSTRUCCIONES PARA CADENAS-------
    tool_instructions = open_json(tool_instructions_dir)
    text2sql_chain_instructions = tool_instructions["text2sql_chain"]
    searched_instructions = tool_instructions["searched_chain"]
    present_instructions = tool_instructions["present_chain"]


    #------EJECUCIÓN DE LA HERRAMIENTA------
    @classmethod
    async def execute(cls, input: str, qa_tool: QAToolModel, user_name: str = None) -> AsyncGenerator[str, None]:
        """
        Esta función coordina toda la herramienta de QA. En pocas palabras, la herramienta se ejecuta en dos pasos. Por un lado una búsqueda preliminar de varios inmuebles de acuerdo a la consulta del usuario. Luego el usuario puede demandar una nueva búsqueda o ampliar la información de los inmuebles presentados.
        Esta función contiene cuatro posibles generadores: para la presentación específica de un inmueble, para consultas de un inmueble ya presentado, para la presentación general de varios inmuebles y para indicar al usuario la necesidad de incorporar más datos a la búsqueda.
            - input (str): petición del usuario.
            - user_name (str): nombre indicado por el usuario. Para referencias personalizadas.
            - qa_tool (QAToolModel): modelo pydantic para la gestión de toda la herramienta QA.
        Devuelve un generador asincrónico.
        """

        print(f"ÚLTIMA CONSULTA: {qa_tool.last_query}")
        input = qa_tool.buffer_input + " \n" + input # Input combinado con buffer
        original_query = "" # Consulta SQL generada y limpiada
        missing_fields = "" # Campos faltantes
        
        # ------PASO 1: DETECCIÓN DE LA INTENCIÓN DEL USUARIO------
        # Ejecutamos la cadena general siempre que se haya presentado previamente algún inmueble (qa_tool.searched_inms). Esta consulta permite discriminar si el usuario demanda una nueva búsqueda o más información sobre un piso ya presentado.

        if qa_tool.searched_inms:

            # ----RECUPERAMOS DATOS DE LOS INMUEBLES BUSCADOS
            try:
                list_inm_id: list = [id for id in qa_tool.searched_inms]
                print(f"IDS YA BUSCADOS: {list_inm_id}")
                last_searched_query: str = generate_sql_ids(list_inm_id)  # Consulta a la base de datos con los IDs buscados
                last_searched_result: List[sqlite3.Row] = execute_sql_query(last_searched_query)
                last_searched_parsed: Dict[int, Dict] = parse_db_answer(last_searched_result) # Resultados parseados por columna
                last_searched_filtered: Dict[int, Dict] = filter_presentation_fields(last_searched_parsed) # Resultados filtrados por columnas
                selected_id = None # ID del inmueble seleccionado para presentación detallada
                new_search = False

            except Exception as e:
                logger.error(f"Unspected error retriving searched properties: {e}")
                raise Exception(f"ERROR: Unspected error retriving searched properties: {e}")

            try:
                # ----CADENA PARA LA DETECCIÓN DE INMUEBLES O NUEVA BÚSQUEDA
                # Esta cadena devuelve el ID al que el usuario hace referencia. También puede devolver "new" si se reclama una nueva búsqueda o "none" en caso de que no sea capaz de encontrar la referencia a ningún inmueble.

                last_searched_filtered_str: str = json.dumps(last_searched_filtered)
                general_result = await cls.qa_general_chain.ainvoke({"history_inm": last_searched_filtered_str, "input": input})
                print(f"RESULTADO GENERAL: {general_result}")

                if general_result == "new":
                    new_search = True

                else:
                    match = re.search(r'\d+', general_result) 
                    if match:
                        selected_id = int(match.group())
                    elif qa_tool.presented_inms:
                        selected_id = qa_tool.presented_inms[-1] # Si no se ha obtenido un ID suponemos que el inmueble de interés es el último presentado
                    else:
                        selected_id = qa_tool.searched_inms[-1] # Si aun así no se ha obtenido un ID suponemos que el inmueble de interés es el último buscado
                        
            except Exception as e:
                logger.error(f"Unspected error in General QA tool: {e}")
                raise Exception(f"ERROR: Unspected error in General QA tool: {e}")

            if not new_search and selected_id in qa_tool.presented_inms:
                try:
                    # ------PASO 2: RESPUESTAS ACERCA DE UN INMUEBLE YA PRESENTADO ------
                    # Ejecutamos esta cadena para responder al usuario ante cuestiones genéricas de un inmueble ya presentado, es decir, el ID seleccionado se encuentra en la lista de inmuebles presentados (qa_tool.presented_inms).

                    print(f"ID A COSULTAR: {selected_id}")
                    selected_searched_parsed: Dict[str, str] = last_searched_parsed.get(selected_id) # Resultados parseados por columna (todas las columnas)
                    selected_inm_tuple: tuple[Dict, str, str, List[str], tuple[float, float]] = specific_presentation_dict(selected_searched_parsed, selected_id)
                    selected_searched_parsed: Dict[str, str] = selected_inm_tuple[0] # Datos del inmueble parseados y enriquecidos

                    
                    selected_searched_parsed_str = json.dumps(selected_searched_parsed)
                    
                    specific_present_dict = {
                        "user_name": user_name,
                        "input": input,
                        "selected_inm": selected_searched_parsed_str
                    }

                    specific_present_dict["instruction"] = (
                        next(
                            (item["description"] for item in cls.present_instructions if item["key"] == "already_presented")
                        )
                    )

                    async for partial_message in cls.specific_answer_chain.astream(specific_present_dict):
                            yield {"type": "text", "content": partial_message}
                    yield {"type": "metadata", "key": "chain", "content": "specific_answer_chain"}

                    return

                except Exception as e:
                    logger.error(f"Unspected error in more info property tool: {e}")
                    raise Exception(f"ERROR: Unspected error in more info property tool: {e}")

            if not new_search and selected_id not in qa_tool.presented_inms:
                try:
                    # ------PASO 3: PRESENTACIÓN DETALLADA DE UN INMUEBLE------
                    # Ejecutamos esta cadena para la presentación de un inmueble, cuyo ID ya habrá sido localizado en el PASO 1 y NO se encuentra en la lista de inmuebles ya presentados (qa_tool.presented_inms). Esta presentación incluye al inmueble, fotos y localización.

                    # ----AÑADIMOS INFORMACIÓN ADICIONAL AL INMUEBLE PRESENTADO
                    print(f"ID A PRESENTAR: {selected_id}")
                    selected_searched_parsed: Dict[str, str] = last_searched_filtered.get(selected_id) # Resultados parseados por columna (columnas de presentacion)
                    selected_inm_tuple: tuple[Dict, str, str, List[str], tuple[float, float]] = specific_presentation_dict(selected_searched_parsed, selected_id)
                    selected_searched_parsed: Dict[str, str] =  selected_inm_tuple[0] # Datos del inmueble parseados y enriquecidos
                    url_inm: str = selected_inm_tuple[1] 
                    main_photo: str = selected_inm_tuple[2]
                    url_photos_inm: list = selected_inm_tuple[3]
                    localization_inm: tuple[float, float] = selected_inm_tuple[4]

                    specific_present_dict = {
                        "user_name": user_name,
                        "input": input,
                        "selected_inm": selected_searched_parsed
                    }

                    specific_present_dict["instruction"] = (
                        next(
                            (item["description"] for item in cls.present_instructions if item["key"] == "to_present")
                        )
                    )

                    # ---- IMAGENES DEL INMUEBLE
                    if main_photo:
                        yield {"type": "image", "content": main_photo}

                    if url_photos_inm:
                        for url in url_photos_inm:
                            yield {"type": "image", "content": url}

                    # ----PRESENTACIÓN TEXTUAL DEL INMUEBLE
                    async for partial_message in cls.specific_answer_chain.astream(specific_present_dict):
                            yield {"type": "text", "content": partial_message}
                    yield {"type": "metadata", "key": "chain", "content": "specific_answer_chain"}

                    # ----URL Y LOCALIZACIÓN DEL INMUEBLE
                    if url_inm:
                        yield {"type": "url", "content": url_inm}

                    if localization_inm:
                        yield {"type": "coord", "content": localization_inm}

                    qa_tool.presented_inms.append(selected_id)

                    return
                
                except Exception as e:
                    logger.error(f"Unspected error in presentation property tool: {e}")
                    raise Exception(f"ERROR: Unspected error in presentation property tool: {e}")

        # ------PASO 4: GENERACIÓN DE LA CONSULTA SQL------
        # Este paso es realmente el primero en ejecutarse en el primer flujo de esta herramienta.
        query = ""
        try:
            # ------ INPUT PROMPT DE GENERACIÓN DE LA CONSULTA SQL
            text2sql = { # Diccionario de entrada para la cadena de generación de consultas SQL
                "input": json.dumps({"text": input, "query": qa_tool.last_query}),
                "dialect": cls.dialect,
                "table_info": cls.table_info,
            }
            text2sql["last_result_instruct"] = (
                next(
                    (item["description"] for item in cls.text2sql_chain_instructions if item["key"] == "last_result_instruct")
                ) if qa_tool.last_query else ""
            )

            # ------ GENERACIÓN DE LA CONSULTA SQL
            query: str = await cls.text2sql_chain.ainvoke(text2sql) 
            yield {"type": "metadata", "key": "sql_query", "content": query}
            print(f"CONSULTA SQL PURA: {query}")

        except Exception as e:
            logger.error(f"Unexpected error in query generation: {e}")
            raise Exception(f"ERROR: Unexpected error in query generation: {e}")
        
        try:
            # ------ TRATAMIENTO DE LA CONSULTA SQL
            # Modificación general de la consulta
            original_query: str = modify_query(query)

            # Añadimos las restricciones de Ids de inmuebles ya presentados
            if qa_tool.searched_inms:
                original_query: str = add_id_exclusion(original_query, [key for key in qa_tool.searched_inms])                
            print(f"CONSULTA SQL TRATADA: {original_query}")

            # ------ COMPROBACIÓN DE CAMPOS FALTANTES
            missing_fields: List[str] = check_fields_in_query(original_query, qa_tool.inm_localization)
            print(f"CAMPOS FALTANTES: {missing_fields}")

            # Añadimos clausulas WHERE de la consulta previa
            if missing_fields and qa_tool.last_query:
                original_query: str = merge_sql_queries(original_query, qa_tool.last_query)
                print(f"CONSULTA SQL CON LAS CONDICIONES PREVIAS AÑADIDAS: {original_query}")

            # ------ CACTUALIZACIÓN DE LA HERRAMIENTA
            qa_tool.last_query = query # Actualizamos última consulta con la consulta sin modificar 
            qa_tool.last_modify_query = original_query # Actualizamos última consulta con la consulta sin modificar     
            qa_tool.missing_fields = missing_fields # Actualizamos los campos faltantes
            yield {"type": "metadata", "key": "sql_query", "content": query}

            print(f"CAMPOS FALTANTES EN SESIÓN : {qa_tool.missing_fields}")
            print(f"CONSULTA SQL TRATADA 2: {original_query}")

        except Exception as e:
            logger.error(f"Unexpected error in query adaptation: {e}")
            raise Exception(f"ERROR: Unexpected error in query adaptation: {e}")

            
        # ------PASO 5: EJECUTAMOS LA CONSULTA O DEMANDAMOS CAMPOS FALTANTES------
        # ------ DEMANDA DE CAMPOS FALTANTES
        if qa_tool.missing_fields:
            try:
                qa_tool.buffer_input = input # Añadimos el input al buffer para acumularlo en el próximo flujo
                
                async for partial_message in cls.missing_fields_chain.astream({"input": input, "missing_fields": str(qa_tool.missing_fields)}):
                    yield {"type": "text", "content": partial_message}
                yield {"type": "metadata", "key": "chain", "content": "missing_fields_chain"}

                is_localization = reclame_localization(qa_tool.missing_fields)
                if not qa_tool.inm_localization and is_localization:
                    city_location: tuple = city_localization(original_query)
                    yield {"type": "function", "content": "generateMapLocalization", "input": city_location}
            
            except Exception as e:
                logger.error(f"Unexpected error in missing fields feedback: {e}")
                raise Exception(f"ERROR: Unexpected error in missing fields feedback: {e}")
            
        # ------ EJECUCIÓN Y PRESENTACIÓN DE RESULTADOS
        else:
            async for partial_message in cls.direct_execute(input, qa_tool, user_name):
                yield partial_message
            

    @classmethod
    async def direct_execute(cls, input: str, qa_tool: QAToolModel, user_name: str = None) -> AsyncGenerator[str, None]:
        """
        Esta función asume que la consulta SQL esta totalmente bien formada y directamente la ejecuta, tras lo cual se realiza la presentación general de los inmuebles localizados.
        """
        query = qa_tool.last_modify_query
        input = qa_tool.buffer_input + " \n" + input # Input combinado con buffer
        qa_tool.buffer_input = ""
        results = ""

        # ------PASO 6: AMPLIACIÓN DE CONSULTA SQL SI NO HAY RESULTADOS------
        modified_query = query
        if not results:
            try:
                alt_query_dict = {}
                alt_query_dict["dialect"] = cls.dialect

                num_limit_searches = 5
                while num_limit_searches>0:

                    alt_query_dict["last_query"] = modified_query
                    
                    # ------ GENERAMOS UNA CONSULTA ALTERNATIVA
                    # Extraemos la columna de la consulta SQL con menor importancia (máxima prioridad de eliminación)
                    column_to_remove: str = extract_column_by_priority(modified_query, num_limit_searches)

                    alt_query_dict["remove_column"] = column_to_remove

                    alt_query: str = await cls.broad_query_chain.ainvoke(alt_query_dict)

                    print(f"CONSULTA AMPLIADA: {alt_query}")

                    # ------ EJECUTAMOS LA CONSULTA
                    results = execute_sql_query(alt_query)
                    modified_query = alt_query

                    if results:
                        break
                    
                    num_limit_searches-=1

            except Exception as e:
                logger.error(f"Unexpected error in broad query loop: {e}")
                raise Exception(f"ERROR: Unexpected error in broad query loop: {e}")
            

         # ----- ULTIMOS AÑADIDOS A LA CONSULTA
        try:
            # Añadimos búsqueda geoespacial (solo para web)
            if qa_tool.inm_localization:
                query = add_geospatial_filter(query, qa_tool.inm_localization)
                qa_tool.inm_localization = None

            # Añadimos cláusula de filtrado y orden
            query = modify_sql_prioridadrk(query)

            results = execute_sql_query(query)
            print(f"RESULTADO FINAL: {results}")

        except Exception as e:
                logger.error(f"Unexpected error in query adaptation: {e}")
                raise Exception(f"Unexpected error in query adaptation: {e}")


        # ------PASO 7: PRESENTACIÓN GENÉRICA DE INMUEBLES ------
        data_results_content = []
        if results: # En caso de que la consulta obtenga resultados
            try:
                # ------ LIMPIEZA DE LOS RESULTADOS
                data_results: Dict[int, Dict] = general_presentation_dict(results)
                qa_tool.searched_inms.extend(data_results.keys()) # Añadimos el ID a la lista inmuebles buscados
                data_results_content: List[Dict] = list(data_results.values())
                yield {"type": "metadata", "key": "modified_sql_query", "content": {"query": modified_query, "results": json.dumps(data_results)}}

            except Exception as e:
                logger.error(f"Unspected error preparing data for presentation: {e}")
                raise Exception(f"ERROR: Unspected preparing data for presentation: {e}")
            
        else:
            yield {"type": "metadata", "key": "modified_sql_query", "content": {"query": modified_query, "results": "no results"}}

        # ------ INPUT PROMPT DE PRESENTACIÓN GENÉRICA DE INMUEBLES
        # En cualquier caso, se ejecuta la cadena de presentación del inmueble, la cual es también capaz de lidiar con situaciones en las que no se ha localizado ningún inmueble.
        try:
            answer_dict = {
                "user_name": user_name,
                "input": input,
                "original_query": query,
                "modified_query": modified_query,
            }
            answer_dict["result_instruct"] = (
                next(
                    (item["description"] for item in cls.searched_instructions if item["key"] == "result_instruct")
                ) if results
                else ""
            )
            answer_dict["not_result_instruct"] = (
                next(
                    (item["description"] for item in cls.searched_instructions if item["key"] == "not_result_instruct")
                ) if not results
                else ""
            )
            answer_dict["modified_query_instruct"] = (
                next(
                    (item["description"] for item in cls.searched_instructions if item["key"] == "modified_query_instruct")
                ) if query!=modified_query and results
                else ""
            )

            logger.info(f"CONSULTA ORIGINAL: {query}")
            logger.info(f"CONSULTA DEFINITIVA: {modified_query}")

            # ------ CADENA DE PRESENTACIÓN GENÉRICA DE INMUEBLES
            async for partial_message in cls.generic_answer_chain.astream(answer_dict):
                yield {"type": "text", "content": partial_message}
            yield {"type": "metadata", "key": "chain", "content": "generic_presentation_chain"}
            
            if results:
                print(f"RESULTADOS A DEVOLVER A LA PRESENTACIÓN: {data_results_content}")
                yield {"type": "function", "content": "generalPresentation", "input": data_results_content}


        except Exception as e:
            logger.error(f"Unspected error property presentation: {e}")
            raise Exception(f"ERROR: Unspected error property presentation: {e}")