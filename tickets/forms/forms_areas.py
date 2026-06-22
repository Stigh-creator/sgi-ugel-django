from django import forms
from ..models import Area

class AreaForm(forms.ModelForm):
    class Meta:
        model = Area
        fields = ['name', 'sede_principal']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej. Contabilidad',
                'required': 'required'
            }),
            'sede_principal': forms.Select(attrs={
                'class': 'form-select',
                'required': 'required'
            })
        }
        labels = {
            'name': 'Nombre del Área',
            'sede_principal': 'Sede Principal'
        }

    def clean_name(self):
        return self.cleaned_data.get('name', '').strip()

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        sede_principal = cleaned_data.get('sede_principal')

        if name and sede_principal:
            # Validación de unicidad de nombre de área en la misma sede
            existing = Area.objects.filter(name__iexact=name, sede_principal=sede_principal)
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError("Ya existe un área registrada con ese nombre en la sede elegida.")
        
        return cleaned_data
