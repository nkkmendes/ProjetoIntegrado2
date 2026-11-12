"""Leitura da planilha da grade curricular.

Este módulo só é usado pela importação (importacao_engenharias.py): as telas
do site nunca leem Excel nem JSON, só o banco de dados.
"""
from collections import OrderedDict
from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR) / 'matricula'
GRADE = BASE / 'dados' / 'FLUXA_grade_curricular_9_engenharias.xlsx'

# Nome do curso no Fluxa -> aba da planilha.
ABAS = {
    'Engenharia de Produção': 'Produção (FAR)',
    'Engenharia de Controle e Automação': 'Controle e Automação',
    'Engenharia Elétrica': 'Elétrica (ESC)',
    'Engenharia Química': 'Química',
    'Engenharia Civil': 'Civil',
    'Engenharia Mecânica': 'Mecânica',
    'Engenharia de Materiais e Nanotecnologia': 'Materiais e Nanotecnologia',
    'Engenharia Ambiental': 'Ambiental',
}

# Engenharia de Computação não está aqui de propósito: o seu currículo e os
# seus pré-requisitos vêm da fixture disciplinas_fluxograma.json.
CURSOS_DA_PLANILHA = tuple(ABAS)

TIPOS_DE_GRUPO = ('Optativa (grupo)', 'Eletiva (grupo)')


def _texto(valor):
    return '' if valor is None else str(valor).strip()


def _linhas(planilha, aba):
    """Lê uma aba em linhas com cabeçalhos e fecha o arquivo corretamente."""
    from openpyxl import load_workbook

    livro = load_workbook(planilha, read_only=True, data_only=True)
    try:
        if aba not in livro.sheetnames:
            raise ValueError(f'Aba não encontrada no Excel: {aba}')
        linhas = livro[aba].iter_rows(values_only=True)
        cabecalho = next(linhas, None)
        if cabecalho is None:
            return []
        chaves = [_texto(c).lower() for c in cabecalho]
        return [dict(zip(chaves, linha)) for linha in linhas]
    finally:
        livro.close()


def _requisitos(texto):
    """A+B = as duas exigências (grupo); A|B = alternativas (grupos diferentes).
    Não inventa pré-requisitos: célula vazia devolve lista vazia."""
    resultado = []
    for alternativa in _texto(texto).upper().split('|'):
        membros = [c.strip() for c in alternativa.split('+') if c.strip()]
        if membros:
            resultado.append(membros)
    return resultado


def ler_grade(nome_curso):
    """Devolve {código: {nome, creditos, grupos, co, grupo_optativa}} do curso.

    Um grupo de optativas pode aparecer em mais de um período: os créditos
    somam, pois o aluno cumpre o total do grupo.
    """
    if nome_curso not in ABAS:
        raise ValueError(f'Curso sem aba na planilha: {nome_curso}')

    mapa = OrderedDict()
    for r in _linhas(GRADE, ABAS[nome_curso]):
        codigo = _texto(r.get('codigo')).upper()
        if not codigo:
            continue
        if _texto(r.get('curso')) != nome_curso:
            raise ValueError(f'Curso inesperado na grade: {codigo}')
        creditos = int(r['creditos'])
        grupo = _texto(r.get('tipo')) in TIPOS_DE_GRUPO
        if codigo not in mapa:
            mapa[codigo] = {
                'nome': _texto(r.get('nome')),
                'creditos': creditos,
                'grupos': _requisitos(r.get('pre_requisitos')),
                'co': [c for g in _requisitos(r.get('co_requisitos')) for c in g],
                'grupo_optativa': grupo,
            }
        elif mapa[codigo]['grupo_optativa']:
            mapa[codigo]['creditos'] += creditos
    return mapa
