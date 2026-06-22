#!/bin/sh
echo "Aplicando migraciones de base de datos..."
python manage.py migrate

echo "Creando usuario administrador por defecto si no existe..."
python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='00000000').exists() or User.objects.create_superuser('00000000', 'admin@example.com', 'P@ssword', first_name='Admin', last_name='SGI', telefono='999999999')"

echo "Cargando datos maestros iniciales..."
python cargar_maestros.py


echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

echo "Iniciando servidor web Daphne..."
exec daphne -b 0.0.0.0 -p ${PORT:-8000} gestion_incidencias.asgi:application

