import logging
import os
import json
from twilio.rest import Client
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

from app.core.middleware import SessionMiddleware
from app.services.mongo_db import MongoDatabase
from app.services.redis_cache import RedisCache
from app.services.sessions_service import SessionService
from app.services.messages_service import MessagesService
from app.services.user_service import UserService
from app.utils.logger_config import configure_logging
from app.routers.base import main_router
from app.data_generation.load_app_data import load_app_data

# Configurar logging
configure_logging()
logger = logging.getLogger(__name__)

# ------ CICLO DE VIDA DE LA APLICACIÓN ------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación."""

    #------INSTANCIAS DE SERVICIOS Y BASE DE DATOS
    try:
        redis_cache_instance = RedisCache()  # Instancia de Redis        
        await redis_cache_instance.flush_all()
        logger.warning("ATENTION: REMOVED PREVIOUS REDIS CACHE. ONLY FOR DEVELOPMENT ")
        mongo_db_instance = MongoDatabase()  # Instancia de MongoDB
        await mongo_db_instance.drop_all_collections()
        logger.warning("ATENTION: REMOVED PREVIOUS MONGO DATABASE. ONLY FOR DEVELOPMENT ")
        await mongo_db_instance.init_beanie()   # Iniciación de Beanie        

        sessions_service_instance = SessionService(redis_cache_instance) # Instancia de SessionService
        messages_service_instance = MessagesService(mongo_db_instance) # Instancia de MessagesService 
        users_service_instance = UserService(mongo_db_instance) # Instancia de UserService 

        app.state.redis_cache = redis_cache_instance
        app.state.mongodb = mongo_db_instance
        app.state.sessions_service = sessions_service_instance
        app.state.messages_service = messages_service_instance
        app.state.users_service = users_service_instance

        logger.info("Session service saved in app.state...")
    except Exception as e:
        logger.critical(f"Error initializing service instances: {e}")
        raise RuntimeError("Failed to initialize services instances") from e
    
    #------CONEXIÓN A REDIS
    try:
        await redis_cache_instance.ping()   # Verificar conexión Redis
        logger.info("Connected to Redis successfully.")
    except Exception as e:
        logger.critical(f"Error connecting to Redis: {e}")
        raise RuntimeError(f"Error connecting to Redis: {e}")
    
    #------CONEXIÓN A MONGO
    try:    
        await mongo_db_instance.ping()  # Verificar conexión MongoDB
        logger.info("Connected to Mongo successfully.")
        await mongo_db_instance.create_indexes()
    except Exception as e:
        logger.critical(f"Error connecting to MongoDB: {e}")
        raise RuntimeError(f"Error connecting to MongoDB: {e}")
    
    #------CONFIGURAR TWILIO
    try:
        account_sid = os.environ["TWILIO_ACCOUNT_SID"]
        auth_token = os.environ["TWILIO_AUTH_TOKEN"]
        client = Client(account_sid, auth_token)
        app.state.twilio_client = client

    except Exception as e:
        pass

    #------CEDER CONTROL A LA APLICACIÓN
    yield
    
    #------CIERRE DE CONEXIONES
    try:
        logger.info("Closing MongoDB connection...")
        await mongo_db_instance.close()
        logger.info("Resources released successfully.")
    except Exception as e:
        logging.critical(f"Error closing MongoDB: {e}")
        raise RuntimeError(f"Error closing MongoDB: {e}")
    
    try:
        logger.info("Closing Redis connection...")
        await redis_cache_instance.close()
        logger.info("Resources released successfully.")
    except Exception as e:
        logging.critical(f"Error closing Redis: {e}")
        raise RuntimeError(f"Error closing Redis: {e}")
    


#------ARRANQUE DE LA APP------
def start_app() -> FastAPI:
    """Factory de la aplicación FastAPI"""    

    load_dotenv()
    
    #------INICIALIZAR LA APLICACIÓN
    app = FastAPI(
        title="RK Chatbot",
        description="API chatbot para agencia comercial",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan
    )

    #------ SCHEDULER PARA CARGA DE DATOS
    try:
        scheduler = BackgroundScheduler()
        scheduler.add_job(load_app_data, 'cron', hour=4, minute=0)
        scheduler.start()

    except Exception as e:
        logger.critical(f"Error configuring Cscheduler for update app data: {e}")
        raise RuntimeError(f"Error configuring Cscheduler for update app data: {e}")

    #------MIDDLEWARE CORS
    try:
        cors_origins = os.getenv("CORS_ORIGINS", "[*]")
        CORS_ORIGINS = json.loads(cors_origins)

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        logger.info("CORS middleware running successfully...")
    except json.JSONDecodeError as json_error:
        logger.critical(f"Invalid JSON format in CORS_ORIGINS environment variable: {json_error}")
        raise ValueError("Failed to parse CORS_ORIGINS. Ensure it is a valid JSON array.") from json_error
    except Exception as e:
        logger.critical(f"Error configuring CORS middleware: {e}")
        raise RuntimeError("Failed to configure CORS middleware") from e

    #------MIDDLEWARE DE SESIONES
    try:
        app.add_middleware(SessionMiddleware, secret_key=os.getenv("MIDDLEWARE_SECRET_KEY"))
        logger.info("Sessions middleware configured...")
    except Exception as e:
        logger.critical(f"Error initializing Sessions Middleware: {e}")
        raise
    
    #------ARCHIVOS ESTÁTCOS
    try:
        static_dir = Path("static")
        static_dir.mkdir(exist_ok=True)
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
        logger.info("Static files mounted successfully...")
    except Exception as e:
        logger.critical(f"Error mounting static files: {e}")
        raise RuntimeError("Failed to mount static files") from e
    
    #------INCLUIR RUTAS
    try:
        app.include_router(main_router())
        logger.info("Routes established successfully...")
    except Exception as e:
        logger.critical(f"Error including routers: {e}")
        raise RuntimeError("Failed to include routers") from e
    
    logger.info("App running succesfully.")
    
    return app

app = start_app()