from django import forms

from .models import Equipo, EstadoEquipo
from tickets.models import Area

IMAGE_INPUT_ACCEPT = "image/jpeg,image/png,image/webp"


class EquipoForm(forms.ModelForm):
    class Meta:
        model = Equipo
        fields = [
            'codigo_equipo', 'nombre_equipo', 'tipo_equipo', 
            'marca', 'modelo', 'numero_serie', 'area', 'estado',
            'disponibilidad', 'observaciones', 'foto_estado'
        ]
        widgets = {
            'codigo_equipo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: PC-001'}),
            'nombre_equipo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre descriptivo'}),
            'tipo_equipo': forms.Select(attrs={'class': 'form-select'}),
            'marca': forms.Select(attrs={'class': 'form-select'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_serie': forms.TextInput(attrs={'class': 'form-control'}),
            'area': forms.Select(attrs={'class': 'form-select'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'disponibilidad': forms.Select(attrs={'class': 'form-select'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ej: Color negro, tapa lateral con rayón leve, base genérica del monitor, etiquetas institucionales visibles.'}),
            'foto_estado': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': IMAGE_INPUT_ACCEPT, 'capture': 'camera'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_equipo'].empty_label = "-- Seleccione Tipo --"
        self.fields['marca'].empty_label = "-- Seleccione Marca --"
        self.fields['area'].empty_label = "-- Seleccione Área --"
        self.fields['estado'].empty_label = "-- Seleccione Estado --"
        self.fields['disponibilidad'].label = "Disponibilidad"
        self.fields['observaciones'].label = "Descripción física / estado estético"
        self.fields['observaciones'].help_text = "Usa este campo solo para rasgos físicos, cosméticos o accesorios del equipo."

    def clean_codigo_equipo(self):
        codigo = self.cleaned_data.get('codigo_equipo')
        if Equipo.objects.filter(codigo_equipo=codigo).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Este código de equipo ya existe.")
        return codigo

    def clean_nombre_equipo(self):
        nombre = self.cleaned_data.get('nombre_equipo')
        if not nombre:
            raise forms.ValidationError("Este campo es obligatorio.")
        return nombre

    def clean(self):
        cleaned_data = super().clean()
        disponibilidad = cleaned_data.get("disponibilidad") or getattr(self.instance, "disponibilidad", None)
        if disponibilidad != Equipo.DISPONIBILIDAD_LIBRE and not getattr(self.instance, "origen_ocupacion", None):
            self.instance.origen_ocupacion = Equipo.ORIGEN_OCUPACION_ASIGNACION_DIRECTA
        return cleaned_data

    def save(self, commit=True):
        equipo = super().save(commit=False)
        if equipo.disponibilidad != Equipo.DISPONIBILIDAD_LIBRE and not equipo.origen_ocupacion:
            equipo.origen_ocupacion = Equipo.ORIGEN_OCUPACION_ASIGNACION_DIRECTA
        if commit:
            equipo.save()
            self.save_m2m()
        return equipo


class EquipoEstadoUpdateForm(forms.Form):
    estado = forms.ModelChoiceField(
        queryset=EstadoEquipo.objects.all(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Nuevo estado operativo",
    )
    observacion = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Justifique el cambio de estado: mantenimiento externo, reparación concluida, baja administrativa, etc.",
            }
        ),
        min_length=10,
        label="Observación obligatoria",
    )

    def __init__(self, *args, **kwargs):
        current_estado = kwargs.pop("current_estado", None)
        super().__init__(*args, **kwargs)
        if current_estado:
            self.fields["estado"].initial = current_estado

    def clean_observacion(self):
        observacion = (self.cleaned_data.get("observacion") or "").strip()
        if len(observacion) < 10:
            raise forms.ValidationError("Debe registrar una observación clara para justificar el cambio.")
        return observacion
