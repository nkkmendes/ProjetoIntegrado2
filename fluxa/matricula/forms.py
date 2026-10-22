
from django import forms
from .models import PlanejamentoSalvo, SimulacaoSalva, NivelamentoSalvo


class PlanejamentoForm(forms.ModelForm):
    class Meta:
        model = PlanejamentoSalvo
        fields = ['nome', 'periodo', 'disciplinas']
        widgets = {
            'periodo': forms.DateInput(attrs={'type': 'date'})
        }


class SimulacaoForm(forms.ModelForm):
    class Meta:
        model = SimulacaoSalva
        fields = ['nome', 'disciplinas']


class NivelamentoForm(forms.ModelForm):
    class Meta:
        model = NivelamentoSalvo
        fields = ['nome', 'area', 'resultado']
