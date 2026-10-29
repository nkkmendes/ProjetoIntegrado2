
from django import forms

from .models import (
    PlanejamentoSalvo,
    SimulacaoSalva,
    NivelamentoSalvo,
    CreditosAluno,
    GrauAluno
)

from django.contrib.auth import authenticate
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User

class LoginForm(forms.Form):
    email = forms.EmailField(
        label='E-mail',
        widget=forms.EmailInput(attrs={'placeholder': 'seu.email@exemplo.com'}),
    )
    senha = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={'placeholder': 'Pelo menos 6 caracteres'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = None

    def clean(self):
        dados = super().clean()
        email = dados.get('email')
        senha = dados.get('senha')
        if email and senha:
            self.usuario = authenticate(username=email.lower(), password=senha)
            if self.usuario is None:
                raise forms.ValidationError('E-mail ou senha incorretos.')
        return dados

class CadastroForm(forms.Form):
    nome = forms.CharField(
        label='Nome completo',
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'Ex: Ana Souza'}),
    )
    email = forms.EmailField(
        label='E-mail institucional',
        max_length=150,
        widget=forms.EmailInput(attrs={'placeholder': 'usuario@aluno.puc-rio.br'}),
    )
    senha = forms.CharField(
        label='Senha',
        min_length=6,
        widget=forms.PasswordInput(attrs={'placeholder': 'Pelo menos 6 caracteres'}),
    )
    confirmar_senha = forms.CharField(
        label='Confirmar senha',
        widget=forms.PasswordInput(),
    )

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError('Já existe uma conta com este e-mail.')
        return email

    def clean(self):
        dados = super().clean()
        senha = dados.get('senha')
        confirmar = dados.get('confirmar_senha')
        if senha and confirmar and senha != confirmar:
            self.add_error('confirmar_senha', 'As senhas não conferem.')
        return dados

    def save(self):
        primeiro_nome, _, sobrenome = self.cleaned_data['nome'].strip().partition(' ')
        return User.objects.create_user(
            username=self.cleaned_data['email'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['senha'],
            first_name=primeiro_nome,
            last_name=sobrenome,
        )

class RecuperarSenhaForm(PasswordResetForm):
    email = forms.EmailField(
        label='E-mail',
        max_length=150,
        widget=forms.EmailInput(attrs={'placeholder': 'seu.email@exemplo.com'}),
    )

class PlanejamentoForm(forms.ModelForm):
    class Meta:
        model = PlanejamentoSalvo
        fields = ['nome', 'periodo', 'disciplinas']
        
        widgets = {
        'periodo': forms.NumberInput(attrs={'min': 1, 'max': 10})
    }


class SimulacaoForm(forms.ModelForm):
    class Meta:
        model = SimulacaoSalva
        fields = ['nome', 'disciplinas']

class CreditosAlunoForm(forms.ModelForm):
    class Meta:
        model = CreditosAluno
        fields = ['disciplina', 'concluida']

        labels = {
            'disciplina': 'Disciplina',
            'concluida': 'Disciplina concluída'
        }

        widgets = {
            'disciplina': forms.Select(
                attrs={'class': 'campo-form'}
            )
        }


# Formulario de Consulta de Graus

class GrauAlunoForm(forms.ModelForm):
    class Meta:
        model = GrauAluno

        fields = [
            'disciplina',
            'turma',
            'periodo_letivo',
            'g1',
            'g2',
            'g3',
            'media',
            'situacao'
        ]

        labels = {
            'disciplina': 'Disciplina',
            'turma': 'Turma',
            'periodo_letivo': 'Período letivo',
            'g1': 'G1',
            'g2': 'G2',
            'g3': 'G3',
            'media': 'Média',
            'situacao': 'Situação'
        }

        widgets = {
            'disciplina': forms.Select(
                attrs={'class': 'campo-form'}
            ),
            'turma': forms.TextInput(
                attrs={'class': 'campo-form'}
            ),
            'periodo_letivo': forms.TextInput(
                attrs={'class': 'campo-form'}
            ),
            'g1': forms.NumberInput(
                attrs={
                    'class': 'campo-form',
                    'min': 0,
                    'max': 10,
                    'step': '0.01'
                }
            ),
            'g2': forms.NumberInput(
                attrs={
                    'class': 'campo-form',
                    'min': 0,
                    'max': 10,
                    'step': '0.01'
                }
            ),
            'g3': forms.NumberInput(
                attrs={
                    'class': 'campo-form',
                    'min': 0,
                    'max': 10,
                    'step': '0.01'
                }
            ),
            'media': forms.NumberInput(
                attrs={
                    'class': 'campo-form',
                    'min': 0,
                    'max': 10,
                    'step': '0.01'
                }
            ),
            'situacao': forms.Select(
                choices=[
                    ('Em curso', 'Em curso'),
                    ('Aprovado', 'Aprovado'),
                    ('Reprovado', 'Reprovado')
                ],
                attrs={'class': 'campo-form'}
            )
        }

    def clean(self):
        dados = super().clean()

        for campo in ['g1', 'g2', 'g3', 'media']:
            nota = dados.get(campo)

            if nota is not None:
                if nota < 0 or nota > 10:
                    self.add_error(
                        campo,
                        'A nota deve estar entre 0 e 10.'
                    )

        return dados

class NivelamentoForm(forms.ModelForm):
    class Meta:
        model = NivelamentoSalvo
        fields = ['nome', 'area', 'resultado']
