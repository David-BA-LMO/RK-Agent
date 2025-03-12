import pandas as pd
import sqlite3
from pprint import pprint
import json
import logging
from typing import List
from sqlalchemy.exc import OperationalError, IntegrityError, TimeoutError, SQLAlchemyError

from app.config import (
    clean_total_inm_csv_dir, 
    sql_search_dir, 
    search_table_generation_query_dir,
    table_name,
    columns_dir
)

logger = logging.getLogger(__name__)

#------GENERACIÓN DE CONSULTA CREATE TABLE ------
def generate_create_table(json_columns, output_txt_path, table_name="my_table"):

    column_definitions = ["Id INTEGER PRIMARY KEY"]
    for col in json_columns:
        if col.get("search", False):  # Solo columnas con search = true
            col_name = col.get("name")
            col_type = col.get("type", "TEXT").upper()
            
            # Tratamiento especial para ENUM
            if col_type == "ENUM" and "values" in col:
                enum_values = "', '".join(col["values"])
                col_type = f"TEXT CHECK ({col_name} IN ('{enum_values}'))"

            # Definir restricciones
            constraints = []
            if col.get("primary_key", False):
                constraints.append("PRIMARY KEY")
            if col.get("not_null", False):
                constraints.append("NOT NULL")
            
            # Combinar tipo y restricciones
            column_definition = f"{col_name} {col_type} {' '.join(constraints)}"
            column_definitions.append(column_definition)

    # Crear consulta CREATE TABLE
    create_table_query = f"CREATE TABLE IF NOT EXISTS {table_name} (\n    " + ",\n    ".join(column_definitions) + "\n);"

    # Guardar la consulta en un archivo TXT
    with open(output_txt_path, "w", encoding="utf-8") as output_file:
        output_file.write(create_table_query)

    #pprint(create_table_query)
    return create_table_query


#------ CREACIÓN DE LA TABLA EN LA BASE DE DATOS ------
def generate_search_ddbb(sql_dir: str, table_name: str, table_query=""):
    conn = sqlite3.connect(sql_dir)
    conn.execute("PRAGMA journal_mode = OFF;")  # Mejora rendimiento (desactiva journaling)
    conn.execute("PRAGMA synchronous = OFF;")   # Desactiva sincronización en escritura
    conn.execute("PRAGMA temp_store = MEMORY;") # Usa solo memoria para almacenamiento temporal
    conn.execute("PRAGMA read_uncommitted = TRUE;")  # Permite lecturas sin bloqueos
    conn.execute("PRAGMA locking_mode = EXCLUSIVE;") # Bloquea escritura de otros procesos

    cursor = conn.cursor()

    if table_query:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            cursor.execute(table_query)  # Crea la tabla base
            print(f"Tabla '{table_name}' creada con éxito.")

            cursor.execute(f"CREATE INDEX idx_busquedas_comunes ON {table_name} (NumDormitorios, Precio, Tipo, Operacion);")
            print("Índice compuesto creado en NumDormitorios, Precio, Tipo y Operacion.")

        except sqlite3.Error as e:
            print("Error al crear la tabla SQL:", e)
        finally:
            conn.commit()
    conn.close()

#------ INSERTAR VALORES EN LA BASE DE DATOS ------
def insert_values(db_path: str, csv_path: str, table_name: str, column_names: List):
    try:
        conn =  sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Eliminar todos los datos previos en la tabla
        cursor.execute(f"DELETE FROM {table_name}")

        df = pd.read_csv(csv_path)

        for col in column_names:
            if col not in df.columns:
                df[col] = None  # Si la columna no existe, añadirla con valores nulos

        columns_to_drop = [col for col in df.columns if col not in column_names]
        df.drop(columns=columns_to_drop, inplace=True)
        
        df.to_sql(table_name, conn, if_exists="append", index=False, dtype={col: "TEXT" for col in column_names})

        print("Datos insertados correctamente")
    except Exception as e:
        print("Error al insertar los datos:", e)
    finally:
        conn.commit()
        conn.close()

#------ FUNCIÓN GENÉRICA PARA CONSULTA A LA BASE DE DATOS ------
def execute_sql_query(query: str, db_path: str = sql_search_dir):
    answer = None  # Valor por defecto en caso de error
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        if conn is None:
            raise OperationalError("No se pudo conectar a la base de datos.")

        conn.row_factory = sqlite3.Row # Los resultados se devuelven como diccionarios con los nombres de los campos
        cursor = conn.cursor()
        cursor.execute(query)
        answer = cursor.fetchall()

    except OperationalError as op_err:
        logger.warning(f"OperationalError durante la ejecución SQL: {op_err}")
    except IntegrityError as int_err:
        logger.warning(f"IntegrityError durante la ejecución SQL: {int_err}")
    except TimeoutError as timeout_err:
        logger.warning(f"Timeout durante la ejecución SQL: {timeout_err}")
    except SQLAlchemyError as sql_err:
        logger.warning(f"General SQLAlchemy error durante la ejecución SQL: {sql_err}")
    except Exception as e:
        logger.warning(f"Execution against database has failed: {e}")
    finally:
        if conn:
            conn.close()

    return answer


#------EJECUCIÓN------
def sql_search_generating():
    # Cargar JSON
    with open(columns_dir, "r", encoding="utf-8") as file:
        data = json.load(file)
        json_columns = data.get("api_columns", []) + data.get("enrichment_columns", [])
    column_names = ["Id"]
    for col in json_columns:
        if col.get("search", False): 
            col_name = col.get("name")
            column_names.append(col_name)
            
    table_query = generate_create_table(json_columns, search_table_generation_query_dir, table_name=table_name)
    generate_search_ddbb(sql_search_dir, table_name, table_query)
    insert_values(sql_search_dir, clean_total_inm_csv_dir, table_name=table_name, column_names=column_names)