# Seeders y datos demostrativos del SGI

Este proyecto separa los datos obligatorios del sistema de los datos demostrativos usados para presentacion o validacion funcional.

## 1. Datos obligatorios

Se cargan con:

```bash
python manage.py asegurar_base_sgi
```

Este comando asegura:

- Superusuario principal: `00000000`
- Nombre visible: `Admin Maestro`
- Contrasena: `P@ssword`
- Areas institucionales base
- Estados de incidencia
- Marcas de inventario
- Tipos de equipo
- Estados de equipo
- Configuracion SLA base

Este comando es idempotente: puede ejecutarse varias veces sin duplicar registros.

## 2. Datos demostrativos

Se cargan con:

```bash
python manage.py cargar_demo_presentacion_sgi
```

Incluye datos de prueba para:

- Usuarios demo por rol
- Equipos de inventario
- Repuestos y stock
- Incidencias en distintos estados
- Comentarios de seguimiento
- Metricas diarias para graficas

Los registros demostrativos usan prefijos como `DEMO-` para diferenciarlos de datos reales.

## 3. Carga automatica al levantar produccion

El archivo `run_web.sh` siempre ejecuta:

```bash
python manage.py asegurar_base_sgi
```

Para cargar tambien datos demostrativos al levantar el servidor, agregar esta variable en el entorno de produccion:

```bash
SGI_LOAD_DEMO_DATA=true
```

Si la variable no existe o tiene otro valor, la carga demo se omite.

## 4. Fallback manual en Docker

Si el servidor ya esta levantado, ejecutar manualmente:

```bash
docker compose exec sgi-web python manage.py asegurar_base_sgi
```

Para cargar datos demo:

```bash
docker compose exec sgi-web python manage.py cargar_demo_presentacion_sgi
```

Para limpiar solo los datos demo y volverlos a cargar:

```bash
docker compose exec sgi-web python manage.py cargar_demo_presentacion_sgi --reset-demo
```

## 5. Recomendacion para produccion real

Para una base limpia institucional, no activar `SGI_LOAD_DEMO_DATA`. Solo se deben ejecutar migraciones y datos obligatorios. Los datos demostrativos son utiles para exposicion, pruebas, capacitacion y validacion de reportes, pero no representan informacion oficial de la UGEL.
