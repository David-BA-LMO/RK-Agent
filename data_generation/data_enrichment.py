import math
#-------------------------------------------------------------------------------------------------------------------
#------CONFIGURATION------

#------FUNCTIONS------
def check_proximity(df, locations_dict, distance):
    """
    Revisa fila a fila si la ubicación de las filas del DataFrame está dentro del radio de 
    cada localización en el diccionario.
    :param df (pd.DataFrame): DataFrame con columnas 'Latitud' y 'Longitud'.
    :param locations_dict (dict): Diccionario con nombres como claves y coordenadas (lat, lon) como valores.
    :param distance (float): Radio en metros para considerar proximidad.
    :returna (pd.DataFrame): DataFrame original con columnas adicionales indicando si está cerca de cada localización.
    """
    # Crear columnas en el DataFrame para cada localización del diccionario
    for location_name, coords in locations_dict.items():
        lat_loc, lon_loc = coords
        # Crear una nueva columna indicando si la fila está cerca de la localización
        df[location_name] = df.apply(
            lambda row: is_within_distance(row['Latitud'], row['Longitud'], lat_loc, lon_loc, distance),
            axis=1
        )
    return df

def is_within_distance(lat1: float, lon1: float, lat2: float, lon2: float, max_distance: float) -> bool:
    """
    Comprueba si la distancia entre dos puntos (lat1, lon1) y (lat2, lon2) es menor o igual al max_distance.
    :params lat1, lon1, lat2, lon2 (float): Coordenadas de los dos puntos en formato decimal.
    :param max_distance (float): Distancia máxima en metros.
    : return bool: True si los puntos están dentro de la distancia, False en caso contrario.
    """
    # Convertir grados a radianes
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    # Diferencia de coordenadas
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    # Aproximación plana usando fórmula de distancia en el plano
    a = delta_lat * 111139  # Conversión de grados a metros
    b = delta_lon * 111139 * math.cos(lat1)  # Escala longitudinal
    distance = math.sqrt(a**2 + b**2)
    return distance <= max_distance