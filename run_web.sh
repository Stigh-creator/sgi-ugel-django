#!/bin/sh
echo "Aplicando migraciones de base de datos..."
python manage.py migrate

echo "Asegurando usuario administrador y datos maestros obligatorios..."
python manage.py asegurar_base_sgi

if [ "$SGI_LOAD_DEMO_DATA" = "true" ]; then
  echo "Cargando datos demostrativos para presentacion..."
  python manage.py cargar_demo_presentacion_sgi
else
  echo "Carga demo omitida. Defina SGI_LOAD_DEMO_DATA=true para activarla."
fi

echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

echo "Iniciando servidor web Daphne..."
exec daphne -b 0.0.0.0 -p ${PORT:-8000} gestion_incidencias.asgi:application
