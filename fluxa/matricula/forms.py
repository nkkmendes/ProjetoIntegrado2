
from django import forms
from .models import PlanejamentoSalvo, SimulacaoSalva, NivelamentoSalvo
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
