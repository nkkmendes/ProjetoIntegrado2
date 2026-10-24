# Um "form" no Django nao e o HTML em si - e um objeto Python que sabe
# VALIDAR um conjunto de dados (um dict vindo de request.POST) e,
# opcionalmente, desenhar os campos HTML correspondentes.
from django import forms

from .models import Historico


class DisciplinaConcluidaForm(forms.ModelForm):
    """
    Formulario para registrar que um aluno concluiu uma disciplina
    (ou seja, um registro de Historico que nao esta mais em andamento).
    """

    class Meta:
        # ModelForm gera os campos do formulario a partir do model
        # Historico (tipo de cada campo, validacao basica, etc.) -
        # nao precisamos redeclarar que "nota" e decimal e "aprovado"
        # e booleano, isso ja esta no models.py.
        model = Historico
        # Quais colunas do Historico esse formulario expoe. "cursando"
        # fica de fora de proposito: quem usa esse form so registra
        # disciplina JA concluida (ver save() abaixo).
        fields = ["aluno", "materia", "turma", "periodo", "aprovado", "nota", "numero_de_oportunidades"]
        labels = {
            "aluno": "Aluno",
            "materia": "Materia",
            "turma": "Turma",
            "periodo": "Periodo",
            "aprovado": "Aprovado",
            "nota": "Nota",
            "numero_de_oportunidades": "Numero de oportunidades",
        }
        widgets = {
            "periodo": forms.NumberInput(),
            "nota": forms.NumberInput(attrs={"step": "0.1", "min": "0", "max": "10"}),
            "numero_de_oportunidades": forms.NumberInput(attrs={"min": "1"}),
        }

    def clean(self):
        # Hook chamado automaticamente dentro de form.is_valid(), depois
        # de cada campo ja ter sido validado individualmente. E o lugar
        # certo pra validacao que depende de MAIS DE UM campo ao mesmo
        # tempo (aqui, turma precisa pertencer a materia escolhida).
        cleaned_data = super().clean()
        materia = cleaned_data.get("materia")
        turma = cleaned_data.get("turma")
        if materia and turma and turma.materia_id != materia.id:
            # add_error liga o erro ao campo "turma" especificamente,
            # em vez de um erro generico do formulario.
            self.add_error("turma", "Essa turma nao pertence a materia selecionada.")
        return cleaned_data

    def save(self, commit=True):
        # commit=False monta o objeto Historico em memoria SEM gravar
        # no banco ainda, so pra podermos ajustar algo antes.
        instance = super().save(commit=False)
        # disciplina concluida nunca esta "cursando" - forcamos isso
        # aqui em vez de deixar o usuario escolher no formulario.
        instance.cursando = False
        if commit:
            instance.save()
        return instance
