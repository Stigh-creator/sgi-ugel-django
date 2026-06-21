# --- Etapa 1: Compilación de dependencias (Builder) ---
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias necesarias para compilar librerías de Python (como psycopg2, Pillow, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libcairo2-dev \
    libpq-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt

# --- Etapa 2: Imagen final de producción (Runner) ---
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar únicamente las dependencias de sistema necesarias en tiempo de ejecución
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copiar paquetes instalados desde la etapa builder
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# Copiar el código del proyecto y scripts
COPY . .

# Asegurar permisos de ejecución para los scripts
RUN chmod +x /app/run_web.sh /app/run_scheduler.sh

EXPOSE 8000

# Por defecto, si no se especifica comando en docker-compose, arranca el servidor web
CMD ["/app/run_web.sh"]
