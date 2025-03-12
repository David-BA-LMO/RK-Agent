from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    """Endpoint de verificación de estado del servicio"""
    return {"status": "ok", "version": "1.0.0"}