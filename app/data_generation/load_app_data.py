import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.data_generation.data_retriever import data_retriving
from app.data_generation.data_cleaner import data_cleaning, data_viewing
from app.data_generation.data_enrichment import data_enrichment
from app.data_generation.sql_search_generation import sql_search_generating
from app.data_generation.json_view_data_generation import create_view_json

# EXECUTION SCRIPT: "python -m app.data_generation.data_generation"

def load_app_data():
    data_retriving()
    data_cleaning()
    data_enrichment()
    sql_search_generating()
    create_view_json()