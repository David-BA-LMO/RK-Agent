FROM python:3.9-slim

WORKDIR /app

# Instalar dependencias del sistema (incluye SpatiaLite)
RUN apt-get update && apt-get install -y \
    libsqlite3-mod-spatialite \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Especificar variable de entorno para que SQLite encuentre SpatiaLite
ENV SPATIALITE_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu/mod_spatialite.so"

# Comando para ejecutar la aplicación
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "debug", "--reload"]