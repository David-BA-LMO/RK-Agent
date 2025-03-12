from typing import Optional, Union, List
from datetime import datetime, timezone

from app.models.messages import MessagesModel
from app.schemas.message import MessageModel
from app.services.mongo_db import MongoDatabase

class MessagesService:
    """Clase instanciable de servicio de gestión del historial de mensajes. Pensada para almacenamiento en MongoDB"""
    
    def __init__(self, mongo_database: MongoDatabase):
        self._mongo_database = mongo_database
        self._collection = self._mongo_database.get_collection("messages")

    # ----CREACIÓN DE MENSAJES
    async def create_messages(self, **msg_data) -> bool:
        """ Crea un nuevo documento desde la colección de mensajes."""

        messages = MessagesModel(**msg_data)
        messages_data = messages.serialize()
        result = await self._collection.insert_one(messages_data)
        return bool(result.inserted_id)
    
    # ----RECUPERACIÓN DE MENSAJES
    async def get_messages(self, id: str) -> Optional[MessagesModel]:
        """ Recupera un documento por su ID de sesión."""
        
        messages_data = await self._collection.find_one({"id": id})

        if not messages_data:
            return None
        
        return MessagesModel.deserialize(messages_data)
    
    # ----ACTUALIZACIÓN GENÉRICA DE MENSAJES
    async def update_messages(self, messages: MessagesModel) -> bool:
        """ Actualiza un documento existente en la base de datos."""

        messages.last_activity = datetime.now(timezone.utc)

        messages_data = messages.serialize()
        result = await self._collection.replace_one({"id": messages.id}, messages_data)
        return result.modified_count > 0
    
    # ----AGREGAR MENSAJES
    async def set_messages(self, messages: Union[str, MessagesModel], user_message: MessageModel, bot_message: MessageModel) -> bool:
        """ Agrega un mensaje a una documento existente."""

        if isinstance(messages, MessagesModel):
            message_inst = messages
        elif isinstance(messages, str):
            id = messages
            message_inst: MessagesModel = await self.get_messages(id)
        if not message_inst:
            raise ValueError("Messages not found at updating")
        
        if not message_inst:
            raise ValueError("A previous messages register is required for updating messages")

        message_inst.messages.append(user_message)
        message_inst.messages.append(bot_message)

        result = await self.update_messages(message_inst)

        return result
    
    # ---- RECUPERAR ULTIMOS MENSAJES
    async def get_last_messages(self, messages: Union[str, MessagesModel], k: int = None) -> Optional[List[MessagesModel]]:
        """Recupera los últimos k mensajes más recientes, ordenados de más antiguo a más reciente."""

        if isinstance(messages, MessagesModel):
            message_inst = messages
        elif isinstance(messages, str):
            id = messages
            message_inst: MessagesModel = await self.get_messages(id)
        if not message_inst:
            raise ValueError("Messages not found at last_messages")
        if k:
            return message_inst.messages[-k:]
        return message_inst.messages