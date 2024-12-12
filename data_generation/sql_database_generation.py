"""

#CREACIÓN DE BASE DE DATOS SQL
def create_ddbb_path(csv_dict):
    ""
    Función para crear la base de datos SQLite a partir de csv

    Parámetros: 
        -csv_dict: dict. Diccionario con el nombre del archivo como clave y el archivo csv como valor.

    Devuelve_ 
        -None.
    ""
    db_dict = {}

    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
    
    for name_db, csv_path in csv_dict.items():
        # Construir la ruta de la base de datos
        database_path = os.path.join(DB_DIR, f"{name_db}.db")
        db_dict[name_db] = f"sqlite:///{database_path}"  # SQLite no requiere autenticación
        
        # Leer el archivo CSV en un DataFrame de pandas
        df = pd.read_csv(csv_path)
        
        # Conectar a la base de datos SQLite (se crea si no existe)
        conn = sqlite3.connect(database_path)
        
        # Guardar el DataFrame en la base de datos como una tabla
        df.to_sql(name_db, conn, if_exists='replace', index=False)
        
        # Optimización: Compactar la base de datos
        conn.execute("VACUUM;")
        
        # Deshabilitar journaling si la base de datos será solo lectura
        conn.execute("PRAGMA journal_mode = OFF;")
        
        # Cerrar la conexión
        conn.close()
        print(f"El archivo CSV {csv_path} ha generado una base de datos en {database_path}")
    
    return db_dict


csv_dict = get_csv_dict(EXCEL_dir)
clean_csv(csv_dict, clean_df_functions, CSV_dir)
db_dict = create_ddbb_path(csv_dict)

"""