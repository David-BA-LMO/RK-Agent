import json
import pandas as pd
import logging

from app.config import localizations_dir, clean_total_inm_csv_dir
from app.data_generation.column_functions import add_localizations
# EXECUTION SCRIPT: "python -m data_generation.data_enrichment"


#-------------------------------------------------------------------------------------------------------------------
#------CONFIGURATION------
logger = logging.getLogger(__name__)

#------FUNCTIONS------

def data_enrichment():
    """
    Esta funciona está pensada para enriquecer la base de datos de inmuebles añadiendo nuevas columnas y valores.
    """
    df = pd.read_csv(clean_total_inm_csv_dir, index_col='Id')

    locations = None
    try:
        with open(localizations_dir, 'r') as file:
            locations = json.load(file)
        locations = locations["localizations"]
    except Exception as e:
        logger.error(f"Error al leer el archivo JSON para enriquecimiento de datos: {e}")

    # Añadimos las localizaciones del JSON
    df = add_localizations(df, locations)

    try:
        df.to_csv(clean_total_inm_csv_dir, encoding="utf-8")
        logger.info(f"El archivo CSV de inmuebles se ha enriquecido y se ha guardado correctamente")
    except Exception as e:
        logger.error(f"Error al guardar el archivo CSV con los datos enriquecidos: {e}")