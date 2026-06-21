#!/bin/sh
# Esperar a que el servicio web aplique las migraciones inicialmente
echo "Esperando a que la base de datos y migraciones estén listas..."
sleep 10

echo "Iniciando el planificador de tareas (scheduler)..."
while true; do
  echo "Ejecutando tareas programadas..."
  python manage.py procesar_sla_incidencias
  python manage.py autocerrar_incidencias_resueltas
  python manage.py metricas_operativas_sgi
  
  INTERVALO=${SGI_SCHEDULER_INTERVAL:-900}
  echo "Esperando ${INTERVALO} segundos para el siguiente ciclo..."
  sleep ${INTERVALO}
done
