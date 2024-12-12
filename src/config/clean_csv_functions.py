# FUNCIONES PARA LIMPAR DATAFRAMES ESPECÍFICOS
import pandas as pd
import sys
import os
current_script_path = os.path.abspath(__file__)
app_directory_path = os.path.dirname(os.path.dirname(current_script_path))
sys.path.append(app_directory_path)
from config.csv_functions import *
from utilities import *
from directories import puntos_playa_dir, barrios_ciudad_dir, TABLE_DESCRIPTION_inm_dir



# FUNCIÓN PARA LIMPIAR EL CSV "INMUEBLES"
name_csv_inm = "inmuebles"

barrios_ciudad = txt_to_dict(barrios_ciudad_dir)
#puntos_playa = txt_to_dict(puntos_playa_dir)

def clean_inm_df(path_csv):
    """
    Función para limpiar y reorganizar el csv de "inmuebles".

    Parámetros: 
        -path_csv: str. Directorio donde se encuentra el csv a limpiar.

    Devuelve_ 
        -df: el DataFrame ya limpiado.

    """
    df = pd.read_csv(path_csv, encoding='utf-8')

    #Transforma valores
    pd.set_option('future.no_silent_downcasting', True)
    df['Aire Acondicionado'] = df['Aire Acondicionado'].replace('no', 0)
    df['Aire Acondicionado'] = df['Aire Acondicionado'].fillna(1)
    df['Aire Acondicionado'] = df['Aire Acondicionado'].astype(int)   

    
    #Función para eliminar las tildes de las columnas
    df = remove_accents_in_columns(df)
    #Función para sustituir los espacios en blanco por guiones bajos en los nombres de las columnas.
    df = eliminate_white_spaces(df)
    #Función para corregir los problemas de codificación de texto
    df = correct_characters_df(df)
    #Elimina las mayúsculas en los nombres de las columnas
    df.columns = [col.lower() for col in df.columns]

    #Recoge la descripción de la tabla de "inmuebles" en un diccionario.
    # Asegurate que las columnas en "TABLE_DESCRIPTION.txt" aparecen nombradas de forma correcta, es decir, con las modificaciones anteriores.
    table_description = txt_to_dict(TABLE_DESCRIPTION_inm_dir)

    #Convertimos las columnas indicadas en "TABLE_DESCRIPTION.txt" a booleanos
    columns_names_to_bool = get_keys_by_values(table_description, "BOOLEAN")
    df = columns_to_bool(df, columns_names_to_bool)

    #Convertimos las columnas indicadas en "TABLE_DESCRIPTION.txt" a booleanos
    columns_names_to_int = get_keys_by_values(table_description, "INTEGER")
    df = columns_to_int(df, columns_names_to_int)
    
    # Usar apply con una expresión lambda para reemplazar los valores
    if 'zona' in df.columns:
        df['zona'] = df['zona'].apply(lambda x: "Centro" if isinstance(x, str) and x.startswith("Centro") else x)
    else:
        print("La columna 'zona' no existe en el DataFrame.")

    #Función para transformar coordenadas
    df = transformar_coordenadas(df)    

    #Función para determinar si el piso está cerca de la playa
    #df = cerca_de_playa(df, puntos_playa)

    #Función para imputar valores a la columna "Población"
    df = completar_poblacion(barrios_ciudad, df)

    #Función para indexar numéricamente cada fila
    df = add_index(df, start_index=0)

    #Eliminamos las columnas que no se encuentren en la descripción "TABLE_DESCRIPTION.txt". Puede haber columnas en la descripción que no estén en el DataFrame
    columns = list(table_description.keys())
    df = drop_columns(df, columns)

    return df


#DEVOLVER FUNCIONES INDEXADAS POR EL NOMBRE DEL CSV CON EL QUE OPERAN
def get_clean_functions():
    clean_df_functions = [
        (name_csv_inm, clean_inm_df)
    ]
    return clean_df_functions

