import pandas as pd
import sys
import os
import json
import numpy as np
from pprint import pprint
from opencage.geocoder import OpenCageGeocode
from typing import List, Dict
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.directories import raw_total_inm_csv_dir, columns_dir, clean_total_inm_csv_dir, reverse_geocode_inm_csv_dir
from data_generation.column_functions import integrating_localization_data, data_type_cleaning, data_cleaning_values
# EXECUTION SCRIPT: "python -m data_generation.data_cleaning"

#-------------------------------------------------------------------------------------------------------------------
#------CONFIGURATION------
# Descripción de columnas
data_columns = {}
with open(columns_dir, 'r') as file:
    data_columns = json.load(file)

api_key = os.getenv("OPENCAGE_KEY")
geocoder = OpenCageGeocode(api_key)


#------FUNCTIONS------
def normalize_text_values(df: pd.DataFrame, column_name: str):
    """
    Modifica los valores de texto en una columna de un DataFrame para estandarizarlos y mejorar su visualización. 
    :param df (pd.DataFrame): El DataFrame que contiene la columna.
    :column_name (str): Nombre de la columna a modificar.
    :returns (pd.DataFrame): El DataFrame con la columna modificada.
    """
    exceptions = {"el", "los", "la", "las", "de", "del", "al",}
    
    def transform_text(text):
        if pd.isna(text):
            return text
        # Convertir todo el texto a mayúsculas
        text = text.upper()
        # Dividir en palabras y capitalizar cada una excepto las excepciones
        words = text.split()
        modified_words = [
            word.capitalize() if word.lower() not in exceptions else word.lower()
            for word in words
        ]
        # Unir las palabras transformadas en una cadena
        return " ".join(modified_words)

    # Aplicar la transformación a la columna
    df[column_name] = df[column_name].apply(transform_text)


# Función para reemplazar caracteres
def remove_accents(text):
    replacements = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U",
    }
    if isinstance(text, str):
        for accented, unaccented in replacements.items():
            text = text.replace(accented, unaccented)
    return text


def reverse_geocode_opencage(lat: float, lon: float) -> List[str]:
    """
    Esta función utiliza la API de OpenCage para realizar geocodificación inversa. A partir de unas coordenadas devuelve la dirección.
    :param lat (float): Latitud
    :param lon (float): Longitud
    :return List(str): Lista con los parámetros de dirección
    """
    try:
        # Verificar valores nulos
        if pd.isnull(lat) or pd.isnull(lon):
            return None, None, None, None, None, None, None, None
        
        lat = float(lat)
        lon = float(lon)

        # Inicialización de variables
        category = ""
        adress = ""
        neighbourhood = ""
        suburb = ""
        hamlet = ""
        village = ""
        road_reference = ""
        borough = ""
        city = ""
        postcode = ""
        road = ""
        town = ""

        # Llamada a la API de OpenCage
        results = geocoder.reverse_geocode(lat, lon)

        if results and len(results) > 0:
            components = results[0].get("components", {})
            category = components.get("_category", "")
            adress = results[0].get("formatted", "")
            postcode = components.get("postcode", "")
            city = components.get("city", "")
            borough = components.get("borough", "")
            neighbourhood = components.get("neighbourhood", "")
            suburb = components.get("suburb", "")
            town = components.get("town", "")
            village = components.get("village", "")
            hamlet = components.get("hamlet", "")
            road = components.get("road", "")
            road_reference = components.get("road_reference", "")
        
        return category, adress, postcode, city, borough, neighbourhood, suburb, town, village, hamlet, road, road_reference

    except Exception as e:
        print(f"Error al obtener dirección para ({lat}, {lon}): {e}")
        return None, None, None, None, None, None, None, None, None, None, None, None

def enrich_localization_values(original_df: pd.DataFrame):
    """
    Genera columnas de localización para cada fila de un DataFrame
    :param df (pd.DataFrame): DataFrame con columnas de "Logitud" y "Latitud" al que añadir las columnas de localización
    :returns (pd.DataFrame): DataFrame original con las columnas ya incluidas.
    """

    print("Comenzando con la geocodificación...")
    rows = []
    # Iterar sobre las filas del DataFrame y actualizar columnas
    for idx, row in original_df.iterrows():
        print(idx)
        category, adress, postcode, city, borough, neighbourhood, suburb, town, village, hamlet, road, road_reference = reverse_geocode_opencage(row["Latitud"], row["Longitud"])
        new_row = {
            "Id": idx,
            "category": category,
            "adress": adress,
            "postcode": postcode,
            "city": city,
            "borough": borough,
            "neighbourhood": neighbourhood,
            "suburb": suburb,
            "town": town,
            "village": village,
            "hamlet": hamlet,
            "road": road,
            "road_reference": road_reference
        }

        rows.append(new_row)
    
    df = pd.DataFrame(rows)

    try:
        df.to_csv(reverse_geocode_inm_csv_dir, index=False, encoding="utf-8")
        print(f"El CSV de geocodificación inversa ha sido guardado en {reverse_geocode_inm_csv_dir}")
    except Exception as e:
        print(f"Error al guardar el archivo CSV de geocodificación inversa : {e}")


#------DATA VIEWING------
def data_viewing():
    df = pd.read_csv(raw_total_inm_csv_dir)
    columns = df.columns

    # Descripciones de las columnas tomadas del JSON
    columns = [item.get("name", None) for item in data_columns["api_columns"]]
    cat_columns = [item.get("name", None) for item in data_columns["api_columns"] if item["type"]=="ENUM"]

    #Ejemplo de fila
    random_row = df.sample(n=1)
    print("\nFila aleatoria del DataFrame")
    print(random_row)

    #Número de items
    print(f"\nTamaño del dataset: {df.shape[0]}")

    #Número de columnas
    print(f"\nNúmero de columnas: {len(columns)}")

    #Número de valores únicos por columnas
    print(f"\nNúmero de valores únicos:\n{df.nunique()}")

    #Número de valores nulos por columnas
    print(f"\nNúmero de valores faltantes:\n{df.isnull().sum()}")

    #Valores únicos de las columnas categóricas
    print("\nValores únicos en cada columna categórica:")
    for cat_column in cat_columns:
        if cat_column in df.columns:  # Verificar si la columna existe en el DataFrame
            print(f"\nValores únicos en {cat_column}: ", df[cat_column].unique().tolist())
        else:
            print(f"La columna {cat_column} no se encuentra en el DataFrame")


#------DATA CLEANING------
def data_cleaning():
    df = pd.read_csv(raw_total_inm_csv_dir, index_col='Id')
    text_columns = [item.get("name", None) for item in data_columns["api_columns"] if item["type"]=="VARCHAR"]

    # Aplicamos una transformación de las columnas de cadenas de texto 
    for text_column in text_columns:
        normalize_text_values(df, text_column)

    # Reemplazo de valores de texto por verdaderos valores nulos
    df.replace(["nan", "s/n", "S/N"], np.nan, inplace=True)

    # Ajustamos los tipos de datos
    df = data_type_cleaning(df, data_columns)

    # Ajuste algunas valores para facilitar la manipulación de los datos
    df = data_cleaning_values(df)

    # Aplicamos geocodificación inversa
    #df = enrich_localization_values(df)

    # Eliminamos todas las tildes
    df = df.map(lambda x: remove_accents(x) if isinstance(x, str) else x)

    #Integramos la información obtenida de la geocodificación con nuestra base de datos
    geocode_df = pd.read_csv(reverse_geocode_inm_csv_dir, index_col="Id")
    df = integrating_localization_data(df, geocode_df)

    # Convertimos el DataFrama en CSV y lo guardamos
    try:
        df.to_csv(clean_total_inm_csv_dir, encoding="utf-8")
        print(f"El archivo con el CSV limpiado se ha guardado correctamente como {clean_total_inm_csv_dir}")
    except Exception as e:
        print(f"Error al guardar el archivo CSV con los datos limpiados: {e}")


#-------EXECUTION------

#data_viewing()
data_cleaning()