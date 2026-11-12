"""Sincroniza as nove engenharias com o banco de dados."""

from django.db import transaction

from .catalogos_fluxa import ABAS, relacoes_do_curso
from .models import Curso, Disciplina



@transaction.atomic
def importar_engenharias():
    """Cadastra as nove engenharias sem apagar historicos."""

    from .catalogos_fluxa import ABAS, relacoes_do_curso

    criadas = 0
    vinculos = 0
    cursos = {}

    for nome in ABAS:
        relacoes = relacoes_do_curso(nome)

        if not relacoes:
            raise ValueError(
                f'A grade de {nome} esta vazia.'
            )

        curso, _ = Curso.objects.get_or_create(
            nome=nome
        )

        disciplinas = []

        for codigo, dados in relacoes.items():
            disciplina, criada = Disciplina.objects.get_or_create(
                codigo=codigo,
                defaults={
                    'nome': dados['nome'],
                    'creditos': dados['creditos'],
                }
            )

            criadas += int(criada)
            disciplinas.append(disciplina)

        curso.disciplinas.set(disciplinas)

        cursos[nome] = len(disciplinas)
        vinculos += len(disciplinas)

    return {
        'cursos': cursos,
        'novas_disciplinas': criadas,
        'novos_vinculos': vinculos,
        'novas': criadas,
        'associacoes': vinculos,
    }
