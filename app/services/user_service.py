from datetime import datetime, timezone
from typing import Optional

from app.models.user import UserModel
from app.services.mongo_db import MongoDatabase

class UserService:
    """Clase instanciable de servicio de gestión del datos de usuario. Pensada para almacenamiento en MongoDB"""

    def __init__(self, mongo_database: MongoDatabase):
        self._mongo_database = mongo_database
        self._collection = self._mongo_database.get_collection("users")

    # ----CREACIÓN DE USUARIO
    async def create_user(self, **user_data) -> UserModel:
        """ Crea un nuevo documento desde la colección de usuarios."""

        user = UserModel(**user_data)
        user_data = user.serialize()
        await self._collection.insert_one(user_data)
        return user
    
    # ----RECUPERACIÓN DE USUARIO
    async def get_user(self, phone: str = None, email: str = None) -> Optional[UserModel]:
        """ Recupera un documento por su ID de sesión."""

        if email:
            user_data = await self._collection.find_one({"email": email})
            return UserModel.deserialize(user_data) if user_data else None
        
        elif phone:
            user_data = await self._collection.find_one({"phone": phone})
            return UserModel.deserialize(user_data) if user_data else None  
        
        else:
            raise AttributeError("Attach an email or a phone to search document")
        
    # ----ACTUALIZACIÓN GENÉRICA DE USUARIO
    async def update_user(self, user: UserModel, id: str) -> bool:
        """ Actualiza un documento existente en la base de datos."""
        print(f"TELEFONO: {user.phone}")

        previous_user: UserModel = await self.get_user(phone = str(user.phone))
        if not previous_user:
            raise ValueError("A previous user is required for updating user")

        # Añadimos la sesion del usuario al usuario previo
        user.session_ids = previous_user.session_ids
        if id not in previous_user.session_ids:
            user.session_ids.append(id)

        user.last_activity = datetime.now(timezone.utc)

        user_data = user.serialize()
        result = await self._collection.replace_one({"phone": str(user.phone)}, user_data)
        return result.modified_count > 0
        
    
