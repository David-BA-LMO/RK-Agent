import os
import pandas as pd
import sqlite3
import sys
current_script_path = os.path.abspath(__file__)
app_directory_path = os.path.dirname(os.path.dirname(current_script_path))
sys.path.append(app_directory_path)
from utilities import *
from directories import EXCEL_dir, CSV_dir, DB_DIR
from config.clean_csv_functions import get_clean_functions

#-------------------------------------------------------------------------------------------------------------------

#Obtener las funciones de limpieza (indexadas por el nombre del dataframe que limpian)
clean_df_functions = get_clean_functions()

#CONVERSOR DE EXCEL A CSV
def get_csv_dict(excel_directory):
    """
    Función para convertir excels en csv.

    Parámetros: 
        -excel_diectory: str. Directorio de reposición de excel.

    Devuelve_ 
        -csv_dict: dict. Diccionario con el nombre del archivo como clave y la ruta del archivo csv como valor.

    """
    csv_dict = {}  # Asegúrate de que este diccionario esté definido

    for file in os.listdir(excel_directory):
        for file in os.listdir(excel_directory):
            if file.endswith(".xlsx") or file.endswith(".xls"):
                name_file = file.rsplit('.', 1)[0]
                path_excel = os.path.join(excel_directory, file)
                try:
                    # Especificar 'encoding' puede no ser necesario para archivos Excel, pero es un buen hábito cuando se manejan archivos CSV o de texto.
                    excel = pd.read_excel(path_excel, engine='openpyxl')
                    print(f"Archivo '{file}' leído correctamente.")
                except Exception as e:
                    print(f"Error al leer el archivo '{file}': {e}")
        try:
            path_csv = os.path.join(CSV_dir, name_file, name_file + ".csv")
            excel.to_csv(path_csv, index=False, encoding='utf-8')
            csv_dict[name_file] = path_csv  # Almacenamos la ruta del archivo CSV en el diccionario
            print(f"El archivo excel {name_file}.xls ha sido guardado como CSV en {path_csv}")
        except Exception as e:
            print(f"Error al guardar el archivo CSV {name_file}.csv {e}")
    
    return csv_dict


# LIMPIEZA DEL CSV
def clean_csv(csv_dict, clean_df_functions, csv_directory):
    """
    Función para limpiar los archivos csv.

    Parámetros: 
        -csv_dict: dict. Diccionario con el nombre del archivo como clave y la ruta del archivo csv como valor.
        -list_name_csv: list. Lista de tuplas, donde cada tupla contiene un nombre de DataFrame (que coincide con las claves en csv_dict)
                          y una función de limpieza para aplicar a ese DataFrame.

    Devuelve
        -None

    """
    # Iterar sobre las tuplas de nombres de DataFrame y funciones de limpieza
    for df_name, clean_func in clean_df_functions:
        if df_name in csv_dict:
            # Construir la ruta completa al archivo CSV usando el directorio y el nombre del archivo
            path = os.path.join(csv_directory, df_name, df_name+ ".csv")
            # Aplicar la función de limpieza al archivo CSV
            cleaned_df = clean_func(path)
            # Sobrescribir el archivo CSV con el DataFrame limpio
            cleaned_df.to_csv(path, index=False, encoding='utf-8')
            print(f"El archivo CSV {df_name}.csv ha sido limpiado y guardado en {path}")


#CREACIÓN DE BASE DE DATOS SQL
def create_ddbb_path(csv_dict):
    """
    Función para crear la base de datos SQLite a partir de csv

    Parámetros: 
        -csv_dict: dict. Diccionario con el nombre del archivo como clave y el archivo csv como valor.

    Devuelve_ 
        -None.
    """
    db_dict = {}

    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
    
    for name_db, csv_path in csv_dict.items():
        # Construir la ruta de la base de datos
        database_path = os.path.join(DB_DIR, f"{name_db}.db")
        db_dict[name_db] = f"sqlite:///{database_path}" #SQLite no requiere autentificación
        
        # Leer el archivo CSV en un DataFrame de pandas
        df = pd.read_csv(csv_path)
        
        # Conectar a la base de datos SQLite (se crea si no existe)
        conn = sqlite3.connect(database_path)
        
        # Guardar el DataFrame en la base de datos como una tabla
        df.to_sql(name_db, conn, if_exists='replace', index=False)
        
        # Cerrar la conexión
        conn.close()
        print(f"El archivo CSV {csv_path} ha generado una base de datos en {database_path}")
    
    return db_dict


csv_dict = get_csv_dict(EXCEL_dir)
clean_csv(csv_dict, clean_df_functions, CSV_dir)
db_dict = create_ddbb_path(csv_dict)