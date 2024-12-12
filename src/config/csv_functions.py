import numpy as np
import re
import unicodedata
import ftfy
import pandas as pd
import unicodedata

#Función pensada para transformar los formatos de coordenadas en el DataFrame
def transformar_coordenadas(df):
    # Función para transformar un valor individual
    def transformar_valor(valor, es_latitud=True):
        try:
            # Intenta convertir a float si es una cadena
            valor_float = float(valor)
        except ValueError:
            # Si falla, retorna np.nan
            return np.nan
        
        # Convierte a string para procesamiento
        valor_str = str(valor)
        
        # Determina la posición para insertar el punto decimal
        punto_posicion = 2
        
        # Verifica si la longitud del string es suficiente para insertar un punto
        if len(valor_str) > punto_posicion:
            valor_transformado = valor_str[:punto_posicion] + '.' + valor_str[punto_posicion:]
        else:
            # Si no es suficiente, considera el valor como inválido
            return np.nan
        
        # Convierte de nuevo a float y retorna
        return float(valor_transformado)
    
    # Aplica la transformación a cada columna respectivamente
    df['latitud'] = df['latitud'].apply(lambda x: transformar_valor(x, es_latitud=True))
    df['longitud'] = df['longitud'].apply(lambda x: transformar_valor(x, es_latitud=False))
    
    return df

# Función para convertir coordenadas a decimal
def coordenadas_a_decimal(coordenada):
    """
    Esta función recibe como argumento una coordenada y la convierte en una coordenada decimal

    Parámetros:
        - coordenada: tupla de dos valores, latitud y longitud.

    Retorna:
        - tupla de coordenada decimal
    """
    lat_texto, lon_texto = coordenada
    
    # Extraer los números y las direcciones para la latitud
    partes_lat = re.split('[° ]+', lat_texto)
    lat_numero, lat_direccion = float(partes_lat[0]), partes_lat[1]
    
    # Extraer los números y las direcciones para la longitud
    partes_lon = re.split('[° ]+', lon_texto)
    lon_numero, lon_direccion = float(partes_lon[0]), partes_lon[1]
    
    # Ajusta el signo de la latitud basado en la dirección
    if lat_direccion.upper() == 'S':
        lat_numero = -lat_numero
        
    # Ajusta el signo de la longitud basado en la dirección
    if lon_direccion.upper() == 'W':
        lon_numero = -lon_numero
        
    return [lat_numero, lon_numero]

# Función para verificar la cercanía a la playa con coordenadas en el nuevo formato
def cerca_de_playa(df, puntos_playa):
    # Convertir puntos de playa a coordenadas decimales
    puntos_playa = [
        tuple(coordenadas) for coordenadas in puntos_playa.values()
    ]

    puntos_playa_decimal = [
        coordenadas_a_decimal(tupla) for tupla in puntos_playa
    ]
    
    # Función para calcular la distancia en metros entre dos puntos
    def calcular_distancia(lat1, lon1, lat2, lon2):
        # Suponiendo aproximadamente 111,139 metros por grado tanto para latitud como longitud
        distancia = ((lat2 - lat1) ** 2 + (lon2 - lon1) ** 2) ** 0.5 * 111139
        return distancia
    
    # Crear una nueva columna inicializada a 0 (no cerca de playa)
    df['cerca_de_playa'] = 0
    # Escanear cada fila del dataset
    for index, row in df.iterrows():
        # Coordenadas actuales de la fila
        lat_actual, lon_actual = row['latitud'], row['longitud']
        
        # Verificar si está cerca de alguna playa
        for lat_playa, lon_playa in puntos_playa_decimal:
            distancia = calcular_distancia(lon_actual, lat_actual, lat_playa, lon_playa)
            if distancia < 600:  # Si está a menos de 600 metros de alguna playa
                df.at[index, 'cerca_de_playa'] = 1
                break  # No es necesario buscar más playas si ya encontró una cercana
                
    return df

#Función para imputar valores en Población según Zona
def completar_poblacion(barrios_ciudad, df):
    # Verificar que las columnas necesarias estén presentes en el dataframe.
    columnas_requeridas = ['zona', 'municipio', "poblacion"]
    for col in columnas_requeridas:
        if col not in df.columns:
            raise ValueError(f"La columna '{col}' no se encuentra en el dataframe.")

    df.loc[(df['zona'] == 'Centro') & (df['municipio'] == 'Oviedo'), 'zona'] = 'Centro Oviedo'
    df.loc[(df['zona'] == 'Centro') & (df['municipio'] == 'Gijón'), 'zona'] = 'Centro Gijón'
    
    # Iterar sobre cada fila del dataframe.
    for index, row in df.iterrows():
        # Extraer la zona y el municipio de la fila actual.
        zona = row['zona']
        municipio = row['municipio']
        
        # Verificar si la zona está en el diccionario y si el municipio coincide.
        if zona in barrios_ciudad and barrios_ciudad[zona] == municipio:
            # Si es así, actualizar la columna "Población" con el municipio.
            df.at[index, 'poblacion'] = municipio
    
    return df

def eliminate_white_spaces(df):
    df.columns = [columna.replace(' ', '_') for columna in df.columns]
    return df

def add_index(df, start_index=0):
    """
    Añade una columna de índice a un archivo CSV.

    Parámetros:
    - df: el DataFrame a indexar
    - start_index: índice de comienzo

    Retorna:
    - df: devuelve el DataFrame modificado
    """

    df['index'] = range(start_index, start_index + len(df))
    cols = ['index'] + [col for col in df if col != 'index']
    df = df[cols]
    return df


def correct_characters_df(df):
    """
    Corrige malas codificaciones de caracteres en todos los valores de texto de un DataFrame

    Parámetros:
    - df: el DataFrame a corregir

    Retorna:
    - df: devuelve el DataFrame modificado
    """
    def correct_characters(text):
        if not isinstance(text, str):
            return text
        # Primero, usar ftfy para arreglar problemas de codificación
        text = ftfy.fix_text(text)
        # Luego, normalizar caracteres para descomponer los tildes y otras diacríticas correctamente
        text = unicodedata.normalize('NFKC', text)
        return text

    # Aplicar la corrección a todas las columnas de texto del DataFrame
    for col in df.select_dtypes(include=['object']):  # Selecciona solo columnas de tipo 'object' que generalmente son texto
        df[col] = df[col].apply(correct_characters)

    return df


def drop_columns(df, list_columns):
    """
    Elimina todas las columnas de un DataFrame que no están en list_columns.

    Parámetros:
        -df: DataFrame del cual eliminar columnas.
        -list_columns: lista de nombres de columnas a mantener en el DataFrame.

    Retorna:
        -df: DataFrame con solo las columnas especificadas en list_columns.
    """
    # Filtrar las columnas que existen en el DataFrame y están también en list_columns
    cols_to_keep = [col for col in list_columns if col in df.columns]
    
    # Usar .loc para seleccionar solo las columnas deseadas
    df = df.loc[:, cols_to_keep]
    
    return df


def columns_to_bool(df, list_bool_columns):
    """
    Transforma las columnas especificadas de un DataFrame a valores binarios.
    
    Parámetros:
        -df: DataFrame a modificar.
        -list_bool_columns: Lista de nombres de columnas a transformar en binarias.
    
    Retorna:
        - df: DataFrame con las columnas modificadas a valores binarios.
    """

    # Recorrer todas las columnas en el DataFrame
    for column in df.columns:
        # Verificar si la columna está en la lista de columnas a binarizar
        if column in list_bool_columns:
            # Verificar si la columna es de tipo numérico
            if pd.api.types.is_numeric_dtype(df[column]):
                # Transformar los valores de la columna a binario
                df[column] = (df[column] > 0).astype('Int64')
            else:
                print(f"Advertencia: La columna '{column}' no es de tipo numérico. No se convirtió a binario.")
    
    return df


def columns_to_int(df, list_int_columns):
    """
    Transforma las columnas especificadas de un DataFrame a valores enteros.
    
    Parámetros:
        -df: DataFrame a modificar.
        -list_int_columns: lista de nombres de columnas a transformar en enteros.
    
    Retorna:
        - df: DataFrame con las columnas modificadas a valores enteros.
    """

    # Recorrer todas las columnas en el DataFrame
    for column in df.columns:
        # Verificar si la columna está en la lista de columnas a convertir en enteros
        if column in list_int_columns:
            # Verificar si la columna es numérica
            if pd.api.types.is_numeric_dtype(df[column]):
                # Convertir los valores de la columna a enteros, usando fillna para manejar NaNs
                df[column] = df[column].fillna(0).astype(np.int64, errors='ignore')
            else:
                print(f"Advertencia: La columna '{column}' no es de tipo numérico. No se convirtió a int.")
    return df


def remove_accents_in_columns(df):
    """
    Elimina las letras acentuadas sustituyéndolas por letras sin acentuar

    Parámetros:
    - df: el DataFrame a corregir

    Retorna:
    - df: devuelve el DataFrame modificado
    """
    # Función auxiliar para eliminar tildes de una cadena de texto
    def remove_accents(input_str):
        # Normalizar la cadena a forma NFD para descomponer los caracteres con tildes
        nfkd_form = unicodedata.normalize('NFKD', input_str)
        # Filtrar para quedarse solo con los caracteres base (elimina los diacríticos)
        only_ascii = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
        return only_ascii
 
    new_columns = {col: remove_accents(col) for col in df.columns}
    df = df.rename(columns=new_columns)
    return df
