import os
from typing import List
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.models.messages import MessagesModel
from app.models.user import UserModel

class MongoDatabase:

    # ------INICIALIZACIÓN DE MONGO------
    def __init__(self):
        """Inicializa la conexión a MongoDB"""
        self._client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
        self._db = self._client[os.getenv("MONGO_NAME")]
        self._collections: List[str] = ["messages", "users"]

    # ------INICIALIZACIÓN DE BEANIE------
    async def init_beanie(self):
        """Inicializa Beanie y registra los modelos"""
        await init_beanie(
            database=self._db,
            document_models=[MessagesModel, UserModel] # Registrar los modelos en Beanie
        )

    # ------ELIMINACIÓN DE TODAS LAS COLECCIONES------
    async def drop_all_collections(self):
        """Elimina todas las colecciones de la base de datos"""
        collections = await self._db.list_collection_names()
        for collection in collections:
            await self._db[collection].drop()

    # ------VERIFICACIÓN DE LA CONEXIÓN------
    async def ping(self) -> bool:
        """Verifica la conexión a MongoDB."""
        await self._client.admin.command("ping")

    # ------CIERRE DE LA CONEXIÓN------
    async def close(self):
        """Cierra la conexión a MongoDB"""
        if self._client:
            self._client.close()
            self._db = None

    # ------CREACIÓN DE ÍNDICES------
    async def create_indexes(self):
        await self._db["messages"].create_index([("id", 1)])
        await self._db["users"].create_index([("phone", 1)])
        await self._db["users"].create_index([("email", 1)])        

    # ------MANEJO DE COLECCIONES------
    def get_collection(self, collection_name: str):
        """Devuelve una colección específica"""
        if collection_name not in self._collections:
            raise ValueError(f"Collection {collection_name} is not defined.")
        return self._db[collection_name]