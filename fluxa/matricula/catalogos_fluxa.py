"""Dados de currículos específicos e consulta de optativas. Sem alterar models.py."""
import json
import re
from collections import OrderedDict
from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR) / 'matricula'
GRADE = BASE / 'dados' / 'FLUXA_grade_curricular_5_engenharias.xlsx'
OPTATIVAS = BASE / 'dados' / 'FLUXA_consulta_optativas_5_engenharias.xlsx'

ABAS = {
    'Engenharia de Computação': 'Computação',
    'Engenharia de Produção': 'Produção (FAR)',
    'Engenharia de Controle e Automação': 'Controle e Automação',
    'Engenharia Elétrica': 'Elétrica (ESC)',
    'Engenharia Química': 'Química',
}

NOVOS_CURSOS = (
    'Engenharia de Controle e Automação',
    'Engenharia Elétrica',
    'Engenharia Química',
)


def _texto(valor):
    return '' if valor is None else str(valor).strip()


def _linhas(planilha, aba):
    """Lê planilha em linhas com cabeçalhos; fecha o arquivo corretamente."""
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
    """A+B = duas exigências; A|B = alternativas. Não inventa pré-requisitos."""
    resultado = []
    for alternativa in _texto(texto).upper().split('|'):
        membros = [c.strip() for c in alternativa.split('+') if c.strip()]
        if membros:
            resultado.append(membros)
    return resultado


def relacoes_do_curso(nome):
    """Produção usa o JSON original. Cursos novos usam grade 2023.
    Computação continua usando a fixture e o banco originais.
    """
    if nome == 'Engenharia de Computação':
        return None

    if nome == 'Engenharia de Produção':
        registros = json.loads((BASE / 'grade_producao.json').read_text(encoding='utf-8'))
        mapa = {}
        for r in registros:
            # Regra específica do repositório: só códigos explícitos geram linhas.
            pre = _texto(r.get('pre', ''))
            co = _texto(r.get('co', ''))
            codigos_pre = re.findall(r'\b[A-Z]{2,4}\d{4}\b', pre.upper())
            codigos_co = re.findall(r'\b[A-Z]{2,4}\d{4}\b', co.upper())
            mapa[r['codigo']] = {
                'nome': r['nome'],
                'creditos': int(r['creditos']),
                'periodo': r.get('periodo'),
                'grupos': [codigos_pre] if codigos_pre else [],
                'co': codigos_co,
            }
        return mapa

    if nome not in NOVOS_CURSOS:
        return {}

    mapa = OrderedDict()
    for r in _linhas(GRADE, ABAS[nome]):
        codigo = _texto(r.get('codigo')).upper()
        if not codigo:
            continue
        if _texto(r.get('curso')) != nome:
            raise ValueError(f'Curso inesperado na grade: {codigo}')
        creditos = int(r['creditos'])
        periodo = r.get('periodo')
        if isinstance(periodo, (int, float)) and float(periodo).is_integer():
            periodo = int(periodo)
        else:
            periodo = None
        if codigo not in mapa:
            mapa[codigo] = {
                'nome': _texto(r.get('nome')),
                'creditos': creditos,
                'periodo': periodo,
                'grupos': _requisitos(r.get('pre_requisitos')),
                'co': [c for g in _requisitos(r.get('co_requisitos')) for c in g],
                'grupo_optativa': r.get('tipo') in ('Optativa (grupo)', 'Eletiva (grupo)'),
            }
        else:
            # Um grupo pode exigir créditos em mais de um período.
            atual = mapa[codigo]
            if atual['grupo_optativa']:
                atual['creditos'] += creditos
            if periodo is not None and atual['periodo'] is None:
                atual['periodo'] = periodo
    return mapa


def grupos_de_optativas(nome):
    """Códigos dos GRUPOS, que ficam representados no fluxograma."""
    if nome not in ABAS:
        return set()
    return {
        _texto(r.get('codigo')).upper()
        for r in _linhas(GRADE, ABAS[nome])
        if _texto(r.get('tipo')) in ('Optativa (grupo)', 'Eletiva (grupo)')
    }


def consultar_catalogo_optativas(nome):
    """A planilha de consulta NUNCA alimenta Disciplina ou o fluxograma."""
    grupos = []
    for r in _linhas(OPTATIVAS, 'GRUPOS POR CURSO'):
        if _texto(r.get('curso')) == nome:
            grupos.append({
                'codigo': _texto(r.get('codigo_grupo')),
                'nome': _texto(r.get('nome_grupo')),
                'periodo': r.get('periodo'),
                'creditos': r.get('creditos_no_periodo'),
                'situacao': _texto(r.get('situacao_das_opcoes')),
                'fonte': _texto(r.get('fonte_lista_opcoes')),
            })
    codigos = {g['codigo'] for g in grupos}
    opcoes = []
    for r in _linhas(OPTATIVAS, 'DISCIPLINAS CONFIRMADAS'):
        if _texto(r.get('codigo_grupo')) in codigos:
            opcoes.append({
                'grupo': _texto(r.get('codigo_grupo')),
                'codigo': _texto(r.get('codigo_opcao')),
                'nome': _texto(r.get('nome_opcao')),
                'fonte': _texto(r.get('fonte_oficial')),
            })
    return grupos, opcoes
