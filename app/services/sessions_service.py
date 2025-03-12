import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from app.models.session import SessionModel
from app.services.redis_cache import RedisCache


class SessionService:
    """Clase instanciable de servicio de gestión de sesiones"""
        
    def __init__(self, redis_cache: RedisCache):
        self.redis_cache = redis_cache
        self.session_timeout = int(os.getenv("SESSION_EXPIRE_MINUTES", "30")) * 60
        self.limit_messages = 4

    # ----CREACIÓN DE SESIÓN
    async def create_session(self, **session_data) -> bool:
        """Crea una nueva sesión con el ID de sesión proporcionado."""
        
        session = SessionModel(**session_data)
        is_session = await self.save_session(session)
        return is_session

    # ----RECUPERACIÓN GENÉRICA DE SESIÓN
    async def get_session(self, id: str) -> SessionModel:
        """Recupera una sesión por su ID de sesión."""

        session_data = await self.redis_cache.get(id)

        if not session_data:
            return None

        return  SessionModel.deserialize(session_data)

    # ----ACTUALIZACIÓN GENÉRICA DE SESIÓN
    async def set_tools_data(self, id: str, updates: Dict[str, Any]) -> bool:
        """Actualiza una sesión existente con datos específicos."""
        
        session: SessionModel = await self.get_session(id)
        if not session:
            raise ValueError(f"Session not found at updating")
        
        session.tools_data = SessionModel.validate_tools_data(updates)
        session.last_activity = datetime.now(timezone.utc)

        is_session = await self.save_session(session)
        return is_session

    # ----ELIMINACIÓN DE SESIÓN
    async def delete_session(self, id: str) -> int:
        """Elimina una sesión por su session_id."""
        return await self.redis_cache.delete(id)

    # ----GUARDADO DE SESIÓN
    async def save_session(self, session: SessionModel) -> bool:
        """Guarda una sesión en Redis con un TTL dinámico."""
        new_expiry_date = datetime.now(timezone.utc) + timedelta(seconds=self.session_timeout)
        session.expiry_date = SessionModel.validate_expiry_date(new_expiry_date)

        ttl = self._calculate_ttl(session.expiry_date)
        if ttl <= 0:
            raise ValueError("TTL must be greater than zero")
        
        session_json = session.serialize()
        return await self.redis_cache.set(session.id, session_json, ttl)

    # ----CÁLCULO DE TTL
    @staticmethod
    def _calculate_ttl(expiry_date: datetime) -> int:
        """Calcula el TTL en segundos basado en la fecha de expiración."""
        now = datetime.now(timezone.utc)
        delta = (expiry_date - now).total_seconds()
        return max(0, int(delta))