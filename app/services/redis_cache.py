import os
from typing import Optional
import redis

class RedisCache:

    # ------INICIALIZACIÓN------
    def __init__(self):
        """Inicializa la conexión a Redis"""
        self._client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                password=os.getenv("REDIS_PASSWORD"),
                db=int(os.getenv("REDIS_DB", 0)),
                decode_responses=True,
                ssl=True
            )
    
    # ------VERIFICACIÓN DE LA CONEXIÓN------
    async def ping(self) -> bool:
        """Comprueba la conexión a Redis"""
        pong = self._client.ping()
        return pong
    
    # ------CIERRE DE LA CONEXIÓN------
    async def close(self):
        """Cierra la conexión a Redis"""
        if self._client:
            self._client.close()

    async def get(self, key: str) -> Optional[str]:
        """Obtiene un valor de Redis"""
        if self._client is None:
            raise Exception("Trying to get an item but Redis has not been initialized.")
        return self._client.get(key)

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Almacena un valor en Redis con TTL opcional"""
        if self._client is None:
            raise Exception("Trying to set an item but Redis has not been initialized.")
        if ttl is not None and ttl > 0:
            return self._client.setex(key, ttl, value)
        return self._client.set(key, value)

    async def delete(self, key: str) -> int:
        """Elimina una clave de Redis"""
        if self._client is None:
            raise Exception("Trying to delete an item but Redis has not been initialized.")
        return self._client.delete(key)

    async def exists(self, key: str) -> bool:
        """Verifica si una clave existe"""
        if self._client is None:
            raise Exception("Trying to check an item but Redis has not been initialized.")
        return bool(self._client.exists(key))

    async def expire(self, key: str, ttl: int) -> bool:
        """Establece un TTL para una clave existente"""
        if self._client is None:
            raise Exception("RedisCache has not been initialized.")
        return bool(self._client.expire(key, ttl))
    
    # ------BORRADO COMPLETO DE TODAS LAS BASES DE DATOS------
    async def flush_all(self):
        """Elimina todas las bases de datos de Redis."""
        if self._client is None:
            raise Exception("RedisCache has not been initialized.")
        return self._client.flushall()