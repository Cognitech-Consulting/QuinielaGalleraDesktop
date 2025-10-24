# forms.py
from django import forms
from .models import Evento, Ronda, Pelea, NombreEquipo
from django.forms import inlineformset_factory

class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = ['nombre', 'fecha', 'ubicacion']

class RondaForm(forms.ModelForm):
    class Meta:
        model = Ronda
        fields = ['numero']

class PeleaForm(forms.ModelForm):
    class Meta:
        model = Pelea
        fields = ['equipo1', 'equipo2']

# Inline formset for Ronda and Pelea within Evento
RondaFormSet = inlineformset_factory(Evento, Ronda, form=RondaForm, extra=5)  # 5 rounds by default
PeleaFormSet = inlineformset_factory(Ronda, Pelea, form=PeleaForm, extra=5)   # 5 matches by default


class NombreEquipoForm(forms.ModelForm):
    class Meta:
        model = NombreEquipo
        fields = ['nombre', 'valor']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del equipo'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Valor único'}),
        }
