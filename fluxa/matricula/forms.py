
from django import forms
from .models import (
    Curso,
    Disciplina,
    PerfilAluno,
    HistoricoDisciplina,
    NivelamentoAluno,
    AreaNivelamento,
)
from django.contrib.auth import authenticate
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm
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
        label='E-mail',
        max_length=150,
        widget=forms.EmailInput(attrs={'placeholder': 'seu.email@exemplo.com'}),
    )
    curso = forms.ModelChoiceField(
        label='Curso',
        queryset=Curso.objects.order_by('nome'),
        empty_label='Escolha seu curso',
        error_messages={'required': 'Escolha o seu curso.'},
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
        usuario = User.objects.create_user(
            username=self.cleaned_data['email'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['senha'],
            first_name=primeiro_nome,
            last_name=sobrenome,
        )
        PerfilAluno.objects.create(user=usuario, curso=self.cleaned_data['curso'])
        return usuario

class RecuperarSenhaForm(PasswordResetForm):
    email = forms.EmailField(
        label='E-mail',
        max_length=150,
        widget=forms.EmailInput(attrs={'placeholder': 'seu.email@exemplo.com'}),
    )

class PerfilNomeForm(forms.Form):
    nome = forms.CharField(
        label='Nome completo',
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'Ex: Ana Souza'}),
    )

    def save(self, usuario):
        primeiro_nome, _, sobrenome = self.cleaned_data['nome'].partition(' ')
        usuario.first_name = primeiro_nome
        usuario.last_name = sobrenome.strip()
        usuario.save(update_fields=['first_name', 'last_name'])
        return usuario

class TrocarSenhaForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'Senha atual'
        self.fields['new_password1'].label = 'Nova senha'
        self.fields['new_password1'].help_text = ''
        self.fields['new_password2'].label = 'Confirmar nova senha'

class PerfilCursoForm(forms.ModelForm):
    """Deixa o aluno escolher (ou trocar) o curso do perfil.
    É o curso do perfil que decide o que o Fluxograma mostra."""

    class Meta:
        model = PerfilAluno
        fields = ['curso']
        labels = {'curso': 'Curso'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['curso'].required = True
        self.fields['curso'].empty_label = 'Escolha seu curso'
        self.fields['curso'].queryset = Curso.objects.order_by('nome')


class DisciplinaChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, disciplina):
        return f'{disciplina.codigo} — {disciplina.nome}'


class HistoricoForm(forms.ModelForm):
    """Registra uma disciplina no histórico do aluno, com notas (opcionais).
    Registrar de novo a mesma disciplina atualiza o registro que já existe."""

    disciplina = DisciplinaChoiceField(
        queryset=Disciplina.objects.none(),
        empty_label='Escolha a disciplina',
        label='Disciplina',
    )

    def __init__(self, *args, perfil=None, **kwargs):
        super().__init__(*args, **kwargs)
        if perfil and perfil.curso_id:
            self.fields['disciplina'].queryset = perfil.curso.disciplinas.order_by('codigo')
        else:
            self.fields['disciplina'].empty_label = 'Escolha sua engenharia no perfil primeiro'

    class Meta:
        model = HistoricoDisciplina
        fields = ['disciplina', 'status', 'periodo_letivo', 'turma', 'g1', 'g2', 'g3', 'media']
        labels = {
            'status': 'Situação',
            'periodo_letivo': 'Período letivo',
            'turma': 'Turma',
            'g1': 'G1',
            'g2': 'G2',
            'g3': 'G3',
            'media': 'Nota final (para o CR)',
        }
        widgets = {
            'periodo_letivo': forms.TextInput(attrs={'placeholder': 'Ex: 2025.1', 'maxlength': 10}),
            'turma': forms.TextInput(attrs={'placeholder': 'Ex: 3WA', 'maxlength': 10}),
            'g1': forms.NumberInput(attrs={'min': 0, 'max': 10, 'step': '0.01'}),
            'g2': forms.NumberInput(attrs={'min': 0, 'max': 10, 'step': '0.01'}),
            'g3': forms.NumberInput(attrs={'min': 0, 'max': 10, 'step': '0.01'}),
            'media': forms.NumberInput(attrs={'min': 0, 'max': 10, 'step': '0.01'}),
        }

    def clean(self):
        dados = super().clean()
        for campo in ['g1', 'g2', 'g3', 'media']:
            nota = dados.get(campo)
            if nota is not None and (nota < 0 or nota > 10):
                self.add_error(campo, 'A nota deve estar entre 0 e 10.')
        return dados

    def save(self, perfil):
        dados = self.cleaned_data
        registro, _ = HistoricoDisciplina.objects.update_or_create(
            perfil=perfil,
            disciplina=dados['disciplina'],
            defaults={
                'status': dados['status'],
                'periodo_letivo': dados['periodo_letivo'].strip(),
                'turma': dados['turma'].strip(),
                'g1': dados['g1'],
                'g2': dados['g2'],
                'g3': dados['g3'],
                'media': dados['media'],
            },
        )
        return registro


class NivelamentoAlunoForm(forms.Form):
    CAMPOS = {
        'matematica': 'Matem\u00e1tica',
        'compreensao_textual': 'Compreens\u00e3o textual',
        'interpretacao_textual': 'Interpreta\u00e7\u00e3o textual',
    }

    def __init__(self, *args, perfil=None, **kwargs):
        super().__init__(*args, **kwargs)
        existentes = {
            n.area.nome.casefold(): n.nivel
            for n in perfil.niveis.select_related('area')
        } if perfil else {}
        for campo, nome in self.CAMPOS.items():
            self.fields[campo] = forms.TypedChoiceField(
                label=nome, required=False, coerce=int, empty_value=None,
                choices=[('', 'N\u00e3o informado')] + [(n, f'N\u00edvel {n}') for n in range(1, 6)],
                initial=existentes.get(nome.casefold()),
                error_messages={'invalid_choice': 'Escolha um n\u00edvel de 1 a 5.'},
            )

    def save(self, perfil):
        from django.db import transaction
        with transaction.atomic():
            for campo, nome in self.CAMPOS.items():
                nivel = self.cleaned_data[campo]
                area = AreaNivelamento.objects.filter(nome__iexact=nome).first()
                if nivel is None:
                    if area:
                        NivelamentoAluno.objects.filter(perfil=perfil, area=area).delete()
                    continue
                if area is None:
                    area, _ = AreaNivelamento.objects.get_or_create(nome=nome)
                NivelamentoAluno.objects.update_or_create(
                    perfil=perfil, area=area, defaults={'nivel': nivel},
                )
