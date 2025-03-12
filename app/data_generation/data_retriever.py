import os
import sys
from pprint import pprint
import csv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.utils.general_utilities import *
from app.config import raw_total_inm_csv_dir, raw_total_inm_json_dir, columns_dir
from app.utils.api_calls import fetch_page, fetch_all_pages

# SCRIPT DE EJECUCIÓN: "python -m app.data_generation.data_retriever"

"""
Este script se encarga de consultar a la API desde la cual recuperar la información de los inmuebles.
Las consultas a la API suceden de la siguiente manera:
    - Se recuperan todos los ids y algunas columnas más de los inmuebles actuales, para lo cual es necesario iterar varias solicitudes dado que son varias páginas.
    - Una vez recuperados los ids, para cada uno de ellos se consulta de nuevo a la API para extraer la totalidad de la información, inmueble a inmueble.
Esto debe realizarse así porque al consultar el conjunto de inmuebles no aparecen todas los campos de interés.
"""

#------DATA RETRIEVING------
def data_retriving():

    # Campos requeridos en el schema. Todas las columnas en la lista api_columns del JSON.
    data_columns = {}
    with open(columns_dir, 'r') as file:
        data_columns = json.load(file)
    required_fields = [item.get("api_name", item["name"]) for item in data_columns["api_columns"]]
    print("En total es necesario recuperar", len(required_fields), "columnas")

    # Recuperación de los inmuebles a partir del conjunto total
    print("Comenzando la recuperación de inmuebles...")
    json_result = fetch_all_pages()

    # Añadimos más columnas consultando la API inmueble a inmueble.
    print("Enriqueciendo el resultado con más campos para cada inmueble...")
    for id in json_result.keys():
        print(id)
        enrich_dict = fetch_page(id)
        json_result[id].update(enrich_dict)
    
    # Guardamos el JSON
    directory = os.path.dirname(raw_total_inm_json_dir)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

    with open(raw_total_inm_json_dir, "w", encoding="utf-8") as file:
        json.dump(json_result, file, ensure_ascii=False, indent=4)
    print(f"Archivo JSON generado desde la API guardado correctamente")
    

    # Convertimos el diccionario en CSV y lo guardamos
    directory = os.path.dirname(raw_total_inm_csv_dir)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

    with open(raw_total_inm_csv_dir, mode="w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        # Cabecera con los campos
        writer.writerow(["Id"] + required_fields)
        # Datos
        for key, fields in json_result.items():
            row = [key] + [fields.get(field, "") for field in required_fields]
            writer.writerow(row)
    print(f"Archivo CSV de inmuebles generado desde la API guardado correctamente")
        
# Recoge el valor de un piso aleatorio
#pprint(fetch_page(page_url, page_body, id=1639096))


