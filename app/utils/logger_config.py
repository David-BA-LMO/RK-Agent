
import logging
from logging.handlers import RotatingFileHandler

#------CONFIGURACIÓN DEL LOGGING------
def configure_logging():
    """Configuración el sistema de logging"""

    # Formato del log
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Handler para archivos con rotación
    file_handler = RotatingFileHandler(
        'logs/app.log',
        maxBytes=10_000_000,  # Máximo 10MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO) # Nivel INFO
    file_handler.setFormatter(logging.Formatter(log_format))
    
    # Handler de consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)  # Nivel DEBUG
    console_handler.setFormatter(logging.Formatter(log_format))
    
    # Configuración principal con los dos handlers
    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, console_handler],
        format=log_format
    )
    
    # Silenciar loggers de librerías
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.ERROR)