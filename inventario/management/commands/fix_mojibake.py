from django.core.management.base import BaseCommand
from django.db import transaction

from inventario.models import Equipo, Marca, TipoEquipo
from tickets.models import Area, CustomUser, Incidencia


COMMON_REPLACEMENTS = {
    "Ã¡": "á",
    "Ã©": "é",
    "Ã­": "í",
    "Ã³": "ó",
    "Ãº": "ú",
    "Ã": "Á",
    "Ã‰": "É",
    "Ã": "Í",
    "Ã“": "Ó",
    "Ãš": "Ú",
    "Ã±": "ñ",
    "Ã‘": "Ñ",
    "Â": "",
}


def normalize_mojibake(value):
    if not value or not isinstance(value, str):
        return value

    fixed = value
    for _ in range(2):
        try:
            if any(token in fixed for token in ("Ã", "Â", "â")):
                candidate = fixed.encode("latin-1").decode("utf-8")
                fixed = candidate
        except (UnicodeEncodeError, UnicodeDecodeError):
            break

    for bad, good in COMMON_REPLACEMENTS.items():
        fixed = fixed.replace(bad, good)

    return fixed


class Command(BaseCommand):
    help = "Corrige textos con mojibake Latin-1/UTF-8 en áreas, tipos, marcas y equipos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra los cambios detectados sin guardar en la base de datos.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        total_changes = 0

        with transaction.atomic():
            total_changes += self.fix_areas(dry_run)
            total_changes += self.fix_named_catalog(
                label="Marca",
                model=Marca,
                field="nombre",
                dry_run=dry_run,
                reassign=lambda source, target: Equipo.objects.filter(marca=source).update(marca=target),
            )
            total_changes += self.fix_named_catalog(
                label="TipoEquipo",
                model=TipoEquipo,
                field="nombre",
                dry_run=dry_run,
                reassign=lambda source, target: Equipo.objects.filter(tipo_equipo=source).update(tipo_equipo=target),
            )
            total_changes += self.fix_plain_model(
                label="Equipo",
                model=Equipo,
                fields=("nombre_equipo", "modelo", "numero_serie", "estado", "observaciones"),
                dry_run=dry_run,
            )

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run completado. No se guardaron cambios."))
            else:
                self.stdout.write(self.style.SUCCESS(f"Limpieza completada. Total corregidos: {total_changes}"))

    def fix_areas(self, dry_run):
        changes = 0
        for area in Area.objects.all():
            normalized_name = normalize_mojibake(area.name)
            normalized_sede = normalize_mojibake(area.sede_principal)
            if normalized_name == area.name and normalized_sede == area.sede_principal:
                continue

            self.stdout.write(self.style.WARNING(f"[Area] {area.pk}"))
            self.stdout.write(f"  - name: {area.name!r} -> {normalized_name!r}")
            self.stdout.write(f"  - sede_principal: {area.sede_principal!r} -> {normalized_sede!r}")
            changes += 1

            existing = Area.objects.filter(name=normalized_name, sede_principal=normalized_sede).exclude(pk=area.pk).first()
            if dry_run:
                continue

            if existing:
                CustomUser.objects.filter(area=area).update(area=existing)
                Incidencia.objects.filter(area=area).update(area=existing)
                Equipo.objects.filter(area=area).update(area=existing)
                area.delete()
            else:
                area.name = normalized_name
                area.sede_principal = normalized_sede
                area.save(update_fields=["name", "sede_principal"])

        self.stdout.write(self.style.SUCCESS(f"Area: {changes} registro(s) corregido(s)."))
        return changes

    def fix_named_catalog(self, *, label, model, field, dry_run, reassign):
        changes = 0
        for obj in model.objects.all():
            original = getattr(obj, field, None)
            normalized = normalize_mojibake(original)
            if normalized == original:
                continue

            self.stdout.write(self.style.WARNING(f"[{label}] {obj.pk}"))
            self.stdout.write(f"  - {field}: {original!r} -> {normalized!r}")
            changes += 1

            existing = model.objects.filter(**{field: normalized}).exclude(pk=obj.pk).first()
            if dry_run:
                continue

            if existing:
                reassign(obj, existing)
                obj.delete()
            else:
                setattr(obj, field, normalized)
                obj.save(update_fields=[field])

        self.stdout.write(self.style.SUCCESS(f"{label}: {changes} registro(s) corregido(s)."))
        return changes

    def fix_plain_model(self, *, label, model, fields, dry_run):
        changes = 0
        for obj in model.objects.all():
            changed_fields = []
            for field in fields:
                original = getattr(obj, field, None)
                normalized = normalize_mojibake(original)
                if normalized != original:
                    setattr(obj, field, normalized)
                    changed_fields.append((field, original, normalized))

            if not changed_fields:
                continue

            changes += 1
            identifier = getattr(obj, "codigo_equipo", None) or getattr(obj, "pk", None)
            self.stdout.write(self.style.WARNING(f"[{label}] {identifier}"))
            for field, original, normalized in changed_fields:
                self.stdout.write(f"  - {field}: {original!r} -> {normalized!r}")
            if not dry_run:
                obj.save(update_fields=[field for field, _, _ in changed_fields])

        self.stdout.write(self.style.SUCCESS(f"{label}: {changes} registro(s) corregido(s)."))
        return changes
