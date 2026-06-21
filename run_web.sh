#!/bin/sh
echo "Aplicando migraciones de base de datos..."
python manage.py migrate

echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

echo "Iniciando servidor web Daphne..."
exec daphne -b 0.0.0.0 -p ${PORT:-8000} gestion_incidencias.asgi:application
