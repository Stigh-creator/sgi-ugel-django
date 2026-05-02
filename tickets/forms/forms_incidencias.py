from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from ..models import CustomUser, Incidencia, Comentario, Area
from ..services import validate_tecnico_capacity

class IncidenciaForm(forms.ModelForm):
    equipo = forms.ModelChoiceField(
        queryset=Incidencia.objects.none(), 
        required=False,
        label="Equipo Afectado",
        empty_label="-- Seleccione Equipo --",
        widget=forms.Select(attrs={"class": "form-select live-search", "onchange": "toggleEquipoOtro(this)"})
    )

    class Meta:
        model = Incidencia
        fields = [
            "categoria", "prioridad", "area", "equipo", 
            "otro_tipo", "otro_marca", "otro_modelo", "otro_serie",
            "descripcion", "imagen_adjunta"
        ]
        widgets = {
            "categoria": forms.Select(attrs={"class": "form-select", "onchange": "toggleEquipoSection(this)"}),
            "prioridad": forms.Select(attrs={"class": "form-select"}),
            "area": forms.Select(attrs={"class": "form-select live-search", "hx-get": "/incidencias/get-equipos/", "hx-target": "#id_equipo", "hx-include": "[name='categoria']"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control w-100", "rows": 4, "placeholder": "Describe detalladamente el problema..."}),
            "otro_tipo": forms.TextInput(attrs={"placeholder": "Ej: Monitor, Teclado, etc."}),
            "otro_marca": forms.TextInput(attrs={"placeholder": "Ej: Dell, HP, Samsung"}),
            "otro_modelo": forms.TextInput(attrs={"placeholder": "Ej: UltraSharp 24"}),
            "otro_serie": forms.TextInput(attrs={"placeholder": "Nro. de Serie (Opcional)"}),
        }

    imagen_adjunta = forms.ImageField(
        required=True,
        label="Evidencia Principal",
        widget=forms.FileInput(attrs={"class": "form-control", "accept": "image/*", "capture": "camera"})
    )
    imagen_2 = forms.ImageField(
        required=False,
        label="Imagen Adicional 1",
        widget=forms.FileInput(attrs={"class": "form-control", "accept": "image/*", "capture": "camera"})
    )
    imagen_3 = forms.ImageField(
        required=False,
        label="Imagen Adicional 2",
        widget=forms.FileInput(attrs={"class": "form-control", "accept": "image/*", "capture": "camera"})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        
        from inventario.models import Equipo, EstadoEquipo

        estado_operativo = EstadoEquipo.objects.filter(nombre="Operativo").first()
        equipos_operativos = Equipo.objects.filter(activo=True, estado=estado_operativo)

        if user:
            if user.es_usuario:
                self.fields["area"].initial = user.area
                self.fields["area"].disabled = True
                self.fields["equipo"].queryset = equipos_operativos.filter(area=user.area)
                if "prioridad" in self.fields:
                    self.fields.pop("prioridad")
            else:
                self.fields["area"].queryset = Area.objects.all().order_by('sede_principal', 'name')
                self.fields["area"].empty_label = "-- Seleccione Área --"
                
                area_id = self.data.get('area') or (self.instance.area.id if self.instance.pk and self.instance.area else None)
                if area_id:
                    self.fields["equipo"].queryset = equipos_operativos.filter(area_id=area_id)
                else:
                    self.fields["equipo"].queryset = equipos_operativos

        choices = list(self.fields["equipo"].choices)
        choices.append(('otro', '--- OTRO (No está en la lista) ---'))
        self.fields["equipo"].choices = choices

    def clean(self):
        cleaned_data = super().clean()
        categoria = cleaned_data.get("categoria")
        equipo_val = self.data.get("equipo")
        equipo = cleaned_data.get("equipo")

        if categoria == "hardware":
            if not equipo_val:
                self.add_error("equipo", "Para fallas de Hardware debe seleccionar un equipo o la opción 'OTRO'.")
            elif equipo_val == "otro":
                if not cleaned_data.get("otro_tipo") or not cleaned_data.get("otro_marca") or not cleaned_data.get("otro_modelo"):
                    raise ValidationError("Si el equipo no está en la lista, debe completar Tipo, Marca y Modelo.")
            elif equipo and equipo.estado.nombre != "Operativo":
                self.add_error("equipo", "Solo puede reportar incidencias sobre equipos en estado Operativo.")
        return cleaned_data

    def clean_imagen_adjunta(self):
        file = self.cleaned_data.get("imagen_adjunta")
        if not file:
            raise ValidationError("La foto de la falla es obligatoria.")
        if file.size > 2 * 1024 * 1024:
            raise ValidationError("La imagen no debe superar los 2MB.")
        return file


class IncidenciaCierreForm(forms.ModelForm):
    class Meta:
        model = Incidencia
        fields = ["solucion_aplicada", "evidencia_solucion"]
        widgets = {
            "solucion_aplicada": forms.Textarea(attrs={"rows": 4, "placeholder": "Describe detalladamente la solución..."}),
        }

    evidencia_solucion = forms.ImageField(
        required=True,
        label="Evidencia de Solución 1",
        widget=forms.FileInput(attrs={"class": "form-control", "accept": "image/*", "capture": "camera"})
    )
    evidencia_solucion_2 = forms.ImageField(
        required=False,
        label="Evidencia de Solución 2",
        widget=forms.FileInput(attrs={"class": "form-control", "accept": "image/*", "capture": "camera"})
    )
    evidencia_solucion_3 = forms.ImageField(
        required=False,
        label="Evidencia de Solución 3",
        widget=forms.FileInput(attrs={"class": "form-control", "accept": "image/*", "capture": "camera"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["solucion_aplicada"].widget.attrs["class"] = "form-control"
        self.fields["solucion_aplicada"].required = True
        self.fields["solucion_aplicada"].min_length = 20

    def clean_solucion_aplicada(self):
        solucion = self.cleaned_data.get("solucion_aplicada")
        if not solucion or len(solucion) < 20:
            raise ValidationError("La descripción de la solución debe tener al menos 20 caracteres.")
        return solucion


class IncidenciaAdminForm(forms.ModelForm):
    equipo = forms.ModelChoiceField(
        queryset=None, 
        required=False,
        label="Equipo Afectado",
        empty_label="-- Seleccione Equipo --",
        widget=forms.Select(attrs={"class": "form-select", "onchange": "toggleEquipoOtro(this)"})
    )
    imagen_adjunta = forms.ImageField(
        required=True,
        label="Evidencia Principal",
        widget=forms.FileInput(attrs={"class": "form-control", "accept": "image/*", "capture": "camera"})
    )
    imagen_2 = forms.ImageField(
        required=False,
        label="Imagen Adicional 1",
        widget=forms.FileInput(attrs={"class": "form-control", "accept": "image/*", "capture": "camera"})
    )
    imagen_3 = forms.ImageField(
        required=False,
        label="Imagen Adicional 2",
        widget=forms.FileInput(attrs={"class": "form-control", "accept": "image/*", "capture": "camera"})
    )

    class Meta:
        model = Incidencia
        fields = [
            "categoria", "prioridad", "area", "equipo",
            "otro_tipo", "otro_marca", "otro_modelo", "otro_serie",
            "descripcion", "imagen_adjunta", "tecnico_asignado",
            "fecha_programada_atencion", "hora_programada_atencion",
            "observaciones_internas",
        ]
        widgets = {
            "categoria": forms.Select(attrs={"class": "form-select", "onchange": "toggleEquipoSection(this)"}),
            "descripcion": forms.Textarea(attrs={"rows": 3, "placeholder": "Descripción..."}),
            "observaciones_internas": forms.Textarea(attrs={"rows": 3, "placeholder": "Notas..."}),
            "fecha_programada_atencion": forms.DateInput(attrs={"type": "date"}),
            "hora_programada_atencion": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "otro_tipo": forms.TextInput(attrs={"placeholder": "Tipo"}),
            "otro_marca": forms.TextInput(attrs={"placeholder": "Marca"}),
            "otro_modelo": forms.TextInput(attrs={"placeholder": "Modelo"}),
            "otro_serie": forms.TextInput(attrs={"placeholder": "Serie"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from inventario.models import Equipo, EstadoEquipo

        estado_operativo = EstadoEquipo.objects.filter(nombre="Operativo").first()
        self.fields["equipo"].queryset = Equipo.objects.filter(activo=True, estado=estado_operativo)
        
        choices = list(self.fields["equipo"].choices)
        choices.append(('otro', '--- OTRO (No está en la lista) ---'))
        self.fields["equipo"].choices = choices

        for field in self.fields.values():
            if not isinstance(field.widget, forms.FileInput):
                field.widget.attrs["class"] = "form-control"

        self.fields["area"].empty_label = "-- Seleccione Área --"
        self.fields["tecnico_asignado"].empty_label = "-- Seleccione Técnico --"
        self.fields["tecnico_asignado"].queryset = CustomUser.objects.filter(
            role__in=[CustomUser.ROL_TECNICO, CustomUser.ROL_ADMIN],
            is_active=True,
        )
        self.fields["tecnico_asignado"].required = True
        self.fields["tecnico_asignado"].widget.attrs["class"] = "form-control live-search"
        self.fields["fecha_programada_atencion"].required = False
        self.fields["hora_programada_atencion"].required = False
        self.fields['tecnico_asignado'].label_from_instance = lambda obj: (
            f"{obj.first_name} {obj.last_name}".strip() or obj.username
        ) + f" ({obj.get_role_display()})"

        today = timezone.localtime(timezone.now()).date().isoformat()
        self.fields['fecha_programada_atencion'].widget.attrs['min'] = today
        self.fields['hora_programada_atencion'].widget.attrs.pop('readonly', None)
        self.fields['hora_programada_atencion'].widget.attrs.pop('disabled', None)

        if self.instance and self.instance.pk:
            self.fields["imagen_adjunta"].required = False
            if self.instance.estado and self.instance.estado.name in ["Resuelto", "Cerrado"]:
                for field_name in ["tecnico_asignado", "fecha_programada_atencion"]:
                    self.fields[field_name].disabled = True
            for field_name in ["categoria", "area", "descripcion", "equipo"]:
                if field_name in self.fields:
                    self.fields[field_name].disabled = True
            if not self.instance.prioridad_editable and "prioridad" in self.fields:
                self.fields["prioridad"].disabled = True

    def clean(self):
        cleaned_data = super().clean()
        categoria = cleaned_data.get("categoria")
        tecnico_asignado = cleaned_data.get("tecnico_asignado")
        is_equipo_disabled = self.fields['equipo'].disabled if 'equipo' in self.fields else False

        if not is_equipo_disabled and categoria == "hardware":
            equipo_val = self.data.get("equipo")
            equipo = cleaned_data.get("equipo")
            if not equipo_val:
                self.add_error("equipo", "Para fallas de Hardware debe seleccionar un equipo o 'OTRO'.")
            elif equipo_val == "otro":
                if not cleaned_data.get("otro_tipo") or not cleaned_data.get("otro_marca") or not cleaned_data.get("otro_modelo"):
                    raise ValidationError("Complete los datos del equipo no listado.")
            elif equipo and equipo.estado.nombre != "Operativo":
                self.add_error("equipo", "Solo puede asociar incidencias a equipos en estado Operativo.")

        if not tecnico_asignado:
            self.add_error("tecnico_asignado", "Debe asignar un técnico responsable.")
        elif tecnico_asignado:
            try:
                validate_tecnico_capacity(tecnico_asignado, exclude_incidencia_id=self.instance.pk)
            except ValidationError as exc:
                self.add_error("tecnico_asignado", exc.message)
        
        fecha = cleaned_data.get("fecha_programada_atencion")
        if fecha and fecha < timezone.localtime(timezone.now()).date():
            self.add_error("fecha_programada_atencion", "No se permiten fechas pasadas.")
            
        return cleaned_data

    def clean_imagen_adjunta(self):
        file = self.cleaned_data.get("imagen_adjunta")
        if self.instance and self.instance.pk and self.instance.imagen_adjunta:
            if not file or getattr(file, "name", None) == self.instance.imagen_adjunta.name:
                return self.instance.imagen_adjunta
        if not file:
            raise ValidationError("La foto de la incidencia es obligatoria.")
        if file.size > 2 * 1024 * 1024:
            raise ValidationError("La imagen no debe superar los 2MB.")
        return file


class ComentarioForm(forms.ModelForm):
    class Meta:
        model = Comentario
        fields = ("texto", "evidencia_adjunta")
        widgets = {
            "texto": forms.Textarea(attrs={"rows": 2, "class": "form-control input-custom", "placeholder": "Escribe un mensaje o añade evidencias..."}),
            "evidencia_adjunta": forms.FileInput(attrs={"class": "form-control form-control-sm input-custom", "accept": "image/*", "capture": "camera"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["texto"].label = ""
        self.fields["evidencia_adjunta"].label = ""

    def clean_evidencia_adjunta(self):
        file = self.cleaned_data.get("evidencia_adjunta")
        if file and file.size > 2 * 1024 * 1024:
            raise ValidationError("La evidencia no debe superar los 2MB.")
        return file


class ReabrirIncidenciaForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo de reapertura",
        min_length=10,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "class": "form-control",
                "placeholder": "Explica por qué la solución no resolvió el problema...",
            }
        ),
    )
    imagen_1 = forms.ImageField(
        required=False,
        label="Foto 1",
        widget=forms.FileInput(attrs={"class": "form-control", "accept": "image/*", "capture": "camera"}),
    )
    imagen_2 = forms.ImageField(
        required=False,
        label="Foto 2",
        widget=forms.FileInput(attrs={"class": "form-control", "accept": "image/*", "capture": "camera"}),
    )
    imagen_3 = forms.ImageField(
        required=False,
        label="Foto 3",
        widget=forms.FileInput(attrs={"class": "form-control", "accept": "image/*", "capture": "camera"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        for field_name in ("imagen_1", "imagen_2", "imagen_3"):
            file = cleaned_data.get(field_name)
            if file and file.size > 2 * 1024 * 1024:
                self.add_error(field_name, "Cada imagen debe pesar como máximo 2 MB.")
        return cleaned_data
