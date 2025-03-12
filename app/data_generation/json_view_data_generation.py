import pandas as pd
from pprint import pprint
import json
import sys
import ast
import os
import random
from urllib.parse import urlparse
import requests
from typing import Dict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import clean_total_inm_csv_dir, json_view_data_dir, columns_dir

def is_url_valid(url: str) -> bool:
    """Valida si una URL es accesible y evita posibles problemas como CORS."""
    try:
        # Verificar que la URL tiene un esquema válido (http o https)
        parsed_url = urlparse(url)
        if parsed_url.scheme not in ["http", "https"]:
            return False

        # Realizar una solicitud GET con timeout
        response = requests.get(url, timeout=6, stream=True)
        
        # Verificar si la respuesta es válida (200 OK o 304 Not Modified)
        if response.status_code not in [200, 304]:
            return False

        # Verificar que el contenido sea una imagen
        content_type = response.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            return False

        # Verificar encabezados CORS (si permite acceso desde cualquier origen)
        cors_headers = response.headers.get("Access-Control-Allow-Origin")
        if cors_headers is None or cors_headers == "null":
            return False
        
        return True

    except requests.RequestException:
        return False

def create_view_json():
    try:
        # Leer la configuración de columnas desde el JSON
        with open(columns_dir, "r", encoding="utf-8") as columns_file:
            columns_config = json.load(columns_file)

        # Extraer los nombres de las columnas específicas para este JSON
        json_view_columns = [
            column["name"] for column in columns_config.get("api_columns", []) if column.get("view")
        ]

        df = pd.read_csv(clean_total_inm_csv_dir, index_col="Id")

        # Construir un diccionario donde la clave es el 'Id'
        data_dict = {}
        for idx, row in df.iterrows():
            row_data = {col: row.get(col, None) for col in json_view_columns}

            print(f"{idx}")

            # Observaciones publicas
            if "Observaciones_Publicas" in row_data:
                op_value = row_data["Observaciones_Publicas"]
                if not isinstance(op_value, str):
                    op_value = ""
                op_value = op_value.replace("&nbsp;", "")
                row_data["Observaciones_Publicas"] = op_value

            # Referencia catastral
            if "RC" in row_data:
                rc_value = row_data["RC"]
                if not isinstance(rc_value, str):
                    rc_value = ""
                row_data["RC"] = rc_value

            # URL
            if "URLExterna" in row_data:
                url_value = row_data["URLExterna"]
                if not isinstance(url_value, str):
                    url_value = ""
                if not url_value or "comprar.agenciaiglesias.com" not in url_value:
                    row_data["URLExterna"] = f"https://comprar.agenciaiglesias.com/inmueblemovil.php?Id={idx}"

            # URL de la imagen principal
            if "Foto" in row_data:
                foto_value = row_data["Foto"]
                print(f"FOTO DICT: {foto_value}")
                if isinstance(foto_value, str):
                    foto_value = foto_value.replace("'", '"')
                    foto_value = ast.literal_eval(foto_value) if not isinstance(foto_value, dict) else foto_value
                    if "URL" in foto_value:
                        row_data["Foto"] = foto_value["URL"]
                else:
                    row_data["Foto"] = ""
                print(f"URL IMAGEN: {row_data['Foto']}")

            # Validar URLs en la columna "array_url_fotos"
            if "array_url_fotos" in row_data and row_data["array_url_fotos"]:
                try:
                    # Convertir la lista de texto en una lista real
                    photo_urls = ast.literal_eval(row_data["array_url_fotos"])
                    num_elementos = min(15, len(photo_urls))
                    photo_urls = random.sample(photo_urls, num_elementos)
                    if isinstance(photo_urls, list):
                        valid_urls = [url for url in photo_urls if is_url_valid(url)]
                        row_data["array_url_fotos"] = valid_urls
                    else:
                        row_data["array_url_fotos"] = []  # Si no es una lista, se vacía
                except (ValueError, SyntaxError):
                    row_data["array_url_fotos"] = []  # Si ocurre un error en la conversión, se vacía

            data_dict[idx] = row_data

        # Escribir el diccionario en un archivo JSON
        with open(json_view_data_dir, "w", encoding="utf-8") as json_file:
            json.dump(data_dict, json_file, indent=4, ensure_ascii=False)

        print(f"Archivo de vistas JSON creado y guardado correctamente")

    except Exception as e:
        print("Error al crear el JSON:", e)


def search_in_json_by_id(search_id: int) -> Dict[str,str]:
    try:
        with open(json_view_data_dir, "r", encoding="utf-8") as json_file:
            data = json.load(json_file)

        result = data.get(str(search_id))  # IDs como strings por consistencia
        if result:
            return result
        else:
            print(f"No se encontró un elemento con ID: {search_id}")
            return None

    except Exception as e:
        print("Error al buscar en el JSON:", e)
        return None
    

        