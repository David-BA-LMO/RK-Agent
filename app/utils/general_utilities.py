import json
import requests
from typing import Type, Dict, Any
import json
from typing import Any


def open_txt(file_path: str) -> str:
    """Abre un archivo de texto y devuelve su contenido como una cadena"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"File in path '{file_path}' not found.")
    except PermissionError:
        raise PermissionError(f"You do not have permissions to read the file in '{file_path}'.")
    except UnicodeDecodeError:
        raise UnicodeDecodeError(f"Error decoding file in '{file_path}'. Must be UTF-8.")
    except OSError as e:
        raise OSError(f"Error at open file in '{file_path}': {e}")


def open_json(file_path: str) -> Any:
    """Abre un archivo JSON y devuelve su contenido"""

    if not isinstance(file_path, str):
        raise TypeError(f"Path {file_path} must be a string, but instead {type(file_path).__name__}")

    if not file_path.endswith('.json'):
        raise ValueError(f"File in {file_path} must have a .json extension")

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

    except FileNotFoundError:
        raise FileNotFoundError(f"File {file_path} not found. Please check the path.")
    
    except PermissionError:
        raise PermissionError(f"Permission denied when trying to read {file_path}.")
    
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in {file_path}: {e}")
    
    except OSError as e:
        raise OSError(f"Error accessing file {file_path}: {e}")

    if not isinstance(data, (dict, list)):
        raise ValueError(f"JSON file in {file_path} must be a list or dictionary, but instead {type(data).__name__}")

    return data


def is_valid_twilio_media(url: str, timeout: int = 5) -> bool:
    """
    Verifica si una URL es una imagen pública y válida para usar como media en Twilio.
    """
    if not url:
        return False
    try:
        response = requests.head(url, allow_redirects=True, timeout=timeout)

        if response.status_code != 200:
            return False

        content_type = response.headers.get("Content-Type", "").lower()
        content_length = response.headers.get("Content-Length", None)

        valid_mime_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}

        if content_type not in valid_mime_types:
            return False

        # Verificar tamaño de imagen (Twilio permite hasta 5MB)
        if content_length is not None and int(content_length) > 5 * 1024 * 1024:
            return False

        return True

    except requests.RequestException:
        return False







