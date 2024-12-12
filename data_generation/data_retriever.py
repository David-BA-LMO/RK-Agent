import os
import sys
from pprint import pprint
import csv
from collections import OrderedDict
from dotenv import load_dotenv
from typing import List
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utilities import *
from api_request import generate_api_request
from src.directories import raw_total_inm_csv_dir, raw_total_inm_json_dir, columns_dir
# SCRIPT DE EJECUCIÓN: "python -m data_generation.data_retriever"

"""
Este script se encarga de consultar a la API desde la cual recuperar la información de los inmuebles.
Las consultas a la API suceden de la siguiente manera:
    - Se recuperan todos los ids y algunas columnas más de los inmuebles actuales, para lo cual es necesario iterar varias solicitudes dado que son varias páginas.
    - Una vez recuperados los ids, para cada uno de ellos se consulta de nuevo a la API para extraer la totalidad de la información.
Esto debe realizarse así porque al consutar el conjunto de inmuebles no aparecen todas los campos de interés.
"""

#-------------------------------------------------------------------------------------------------------------------
#------CONFIGURATION------
load_dotenv()

page_url = os.getenv("CRM_API_URL_INMUEBLE") # URL de la API para obtener información de un inmueble
all_pages_url = os.getenv("CRM_API_URL_INMUEBLES") # URL de la API para obtener la totalidad de inmuebles
page_key = os.getenv("PAGE_KEY") # clave a buscar en la respuesta de la API para un solo inmueble
all_pages_key = os.getenv("ALL_PAGES_KEY") # clave a buscar en la respuesta de la API para la totalidad de inmuebles

# Cuerpo de solicitud a la API para obtener información de un inmueble
page_body = {
    'usuario': os.getenv("CRM_API_USERNAME"),
    'password': os.getenv("CRM_API_PASSWORD"),
    'Id' : 0,
}
# Cuerpo de solicitud a la API para obtener información de la totalidad de inmuebles
all_pages_body = {
    'usuario': os.getenv("CRM_API_USERNAME"),
    'password': os.getenv("CRM_API_PASSWORD"),
    'orden' : 'Id',
    'ascdesc': 'ASC',
    'numXpagina': 30,
    'pagina': 0
}


#------CONSULTA A LA API------

def fetch_page(page_url: str, page_body: Dict[str,str], id: str, fields = []) -> Dict[str, str]:
    """
    Realiza una llamada a la API y devuelve el resultado. Pensado para obtener información de un solo inmueble
    :parama page_url (str): URL donde se localiza el recurso
    :parama page_body (Dict[str,str]): cuerpo de solicitud a la API para obtener información de un inmueble
    :param requiered_fields (List[str]): campos de interés a recuperar.
    :param id (str): identificador del inmueble a localizar.
    :returns: devuelve un diccionario con los campos de un inmueble.
    """

    # Copia del cuerpo de solicitud
    body = page_body.copy()
    body["Id"] = id

    # Llamada a la API
    try:
        api_response = generate_api_request(page_url, body) 
    except Exception as e:
            print(f"Error al realizar la solicitud a la API: {e}")

    # La respuesta de la API es un diccionario. Filtramos por la clave "inmueble" lo cual devuelve un diccionario.
    dict_inm = {}
    try:
        #print(list(dict_inm.keys()))
        dict_inm = api_response.get("inmueble")
    except: 
        print(f"La clave no se ha encontrado en la respuesta")

    if fields:
        return {key: value for key, value in dict_inm.items() if key in fields}
    else: 
        return {key: value for key, value in dict_inm.items()}
     

def fetch_all_pages(all_pages_url: str, all_pages_body: Dict[str,str], fields = []) -> Dict[str,Dict[str,str]]:
    """
    Hace llamadas iterativas a una API y devuelve una lista con los resultados. Pensado para obtener información de todos los inmuebles.
    :param all_pages_url (str): URL del API con varias páginas
    :param all_pages_body (str): cuerpo inicial para las solicitudes a la API.
    :param fields (List[str]): parámetro opcional para extraer subcampos específicos.
    :return (Dict[str,Dict[str,str]]): diccionario con con todos los resultados como diccionarios combinados
    """

    all_results = {}
    current_page = 0
    
    while True:
        # Copia del cuerpo de solicitud
        body = all_pages_body.copy()
        body['pagina'] = current_page

        # Llamada a la API
        try:
            api_response = generate_api_request(all_pages_url, body)
        except Exception as e:
            print(f"Error al realizar la solicitud a la API: {e}")
            break
        
        # La respuesta de la API es un diccionario. Filtramos por la clave "inmuebles" lo cual devuelve una lista de diccionarios
        list_inm = api_response.get(all_pages_key)
        if list_inm is None:
            break
        
        # Por cada diccionario de la lista creamos un nuevo par clave-valor en "all_results", con clave el campo 
        # "Id" del diccionario y valor un diccionario con el resto de campos que esten en requiered_fields 
        for item in list_inm:
            if fields:
                # print(list(item.keys()))
                all_results[item["Id"]] = {key: value for key, value in item.items() if key in fields}
            else:
                all_results[item["Id"]] = {key: value for key, value in item.items()}
        
        current_page += 1

    print(f"Se han recuperado de la API un total de {len(all_results)}")
    #pprint.pprint(all_results)
    
    return all_results


#------EJECUCIÓN------
def data_retriving(raw_total_inm_json_dir: str, raw_total_inm_csv_dir: str):

    # Campos requeridos en el schema
    data_columns = {}
    with open(columns_dir, 'r') as file:
        data_columns = json.load(file)
    required_fields = [item["name"] for item in data_columns["api_columns"]]
    print("En total es necesario recuperar", len(required_fields), "columnas")

    print("Comenzando la recuperación de inmuebles...")
    json_result = fetch_all_pages(all_pages_url, all_pages_body, fields = required_fields)

    print("Enriqueciendo el resultado con más campos para cada inmueble...")
    for key in json_result.keys():
        print(key)
        enrich_dict = fetch_page(page_url, page_body, key, fields = required_fields)
        json_result[key].update(enrich_dict)
    
    # Guardamos el JSON
    directory = os.path.dirname(raw_total_inm_json_dir)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

    with open(raw_total_inm_json_dir, "w", encoding="utf-8") as file:
        json.dump(json_result, file, ensure_ascii=False, indent=4)
    print(f"\nArchivo JSON guardado como: {raw_total_inm_json_dir}")
    

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
    print(f"\nArchivo CSV generado como: {raw_total_inm_csv_dir}")
        

data_retriving(raw_total_inm_json_dir, raw_total_inm_csv_dir)


