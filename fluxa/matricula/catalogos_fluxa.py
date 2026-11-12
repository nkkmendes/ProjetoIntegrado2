
"""Grades curriculares das nove engenharias do Fluxa."""

from collections import OrderedDict
from pathlib import Path

from django.conf import settings


BASE = Path(settings.BASE_DIR) / 'matricula'


OPTATIVAS = BASE / 'dados' / 'FLUXA_consulta_optativas_5_engenharias.xlsx'

GRADE = BASE / 'dados' / 'FLUXA_grade_curricular_9_engenharias.xlsx'

ABAS = {
    'Engenharia de Computação': 'Computação',
    'Engenharia de Produção': 'Produção (FAR)',
    'Engenharia de Controle e Automação': 'Controle e Automação',
    'Engenharia Elétrica': 'Elétrica (ESC)',
    'Engenharia Química': 'Química',
    'Engenharia Civil': 'Civil',
    'Engenharia Mecânica': 'Mecânica',
    'Engenharia de Materiais e Nanotecnologia': 'Materiais e Nanotecnologia',
    'Engenharia Ambiental': 'Ambiental',
}

NOVOS_CURSOS = tuple(ABAS)

def _texto(valor):
    if valor is None:
        return ''

    return str(valor).strip()


def _linhas(planilha, aba):
    """Lê as linhas do Excel."""

    from openpyxl import load_workbook

    livro = load_workbook(
        planilha,
        read_only=True,
        data_only=True
    )

    try:
        if aba not in livro.sheetnames:
            raise ValueError(
                f'Aba não encontrada no Excel: {aba}'
            )

        linhas = livro[aba].iter_rows(
            values_only=True
        )

        cabecalho = next(linhas, None)

        if cabecalho is None:
            return []

        chaves = [
            _texto(coluna).lower()
            for coluna in cabecalho
        ]

        return [
            dict(zip(chaves, linha))
            for linha in linhas
        ]

    finally:
        livro.close()


def _requisitos(texto):
    """A+B = duas exigências; A|B = alternativas."""

    grupos = []

    for alternativa in _texto(texto).upper().split('|'):

        codigos = [
            codigo.strip()
            for codigo in alternativa.split('+')
            if codigo.strip()
        ]

        if codigos:
            grupos.append(codigos)

    return grupos


def linhas_do_curso(nome):
    """Retorna todas as disciplinas e seus períodos."""

    if nome not in ABAS:
        return []

    resultado = []

    for registro in _linhas(GRADE, ABAS[nome]):

        codigo = _texto(
            registro.get('codigo')
        ).upper()

        if not codigo:
            continue

        if _texto(registro.get('curso')) != nome:
            raise ValueError(
                f'Curso inesperado na grade: {codigo}'
            )

        periodo = registro.get('periodo')

        if isinstance(periodo, (int, float)):
            if int(periodo) == periodo:
                periodo = int(periodo)
            else:
                periodo = 0

        elif _texto(periodo).isdigit():
            periodo = int(_texto(periodo))

        else:
            periodo = 0

        if not 0 <= periodo <= 10:
            raise ValueError(
                f'Período inválido: {codigo}'
            )

        creditos = int(
            registro['creditos']
        )

        if creditos < 0:
            raise ValueError(
                f'Créditos negativos: {codigo}'
            )

        resultado.append({
            'codigo': codigo,
            'nome': _texto(
                registro.get('nome')
            ),
            'creditos': creditos,
            'periodo': periodo,
            'grupos': _requisitos(
                registro.get('pre_requisitos')
            ),
            'co': [
                c
                for grupo in _requisitos(
                    registro.get('co_requisitos')
                )
                for c in grupo
            ],
            'tipo': _texto(
                registro.get('tipo')
            ),
            'verificacao': _texto(
                registro.get('verificacao')
            )
        })

    return resultado


def relacoes_do_curso(nome):
    """Organiza as relações de disciplinas por curso."""

    mapa = OrderedDict()

    for item in linhas_do_curso(nome):

        codigo = item['codigo']

        if codigo not in mapa:

            mapa[codigo] = {
                'nome': item['nome'],
                'creditos': item['creditos'],
                'periodo': item['periodo'],
                'grupos': item['grupos'],
                'co': item['co'],
                'grupo_optativa': (
                    'grupo' in item['tipo'].lower()
                    or codigo.startswith(
                        ('ELL', 'ELU', 'ELO', 'ACP')
                    )
                )
            }

        else:
            anterior = mapa[codigo]

            # Grupos podem aparecer em vários períodos
            anterior['creditos'] += item['creditos']

            if not anterior['grupos'] and item['grupos']:
                anterior['grupos'] = item['grupos']

            if not anterior['co'] and item['co']:
                anterior['co'] = item['co']

    return mapa


def grupos_de_optativas(nome):
    """Identifica os grupos de optativas do curso."""

    if nome not in ABAS:
        return set()

    return {
        item['codigo']
        for item in linhas_do_curso(nome)
        if 'grupo' in item['tipo'].lower()
    }


def consultar_catalogo_optativas(nome):
    """Consulta a planilha informativa de optativas."""

    grupos = []

    for registro in _linhas(
        OPTATIVAS,
        'GRUPOS POR CURSO'
    ):

        if _texto(registro.get('curso')) == nome:

            grupos.append({
                'codigo': _texto(
                    registro.get('codigo_grupo')
                ),
                'nome': _texto(
                    registro.get('nome_grupo')
                ),
                'periodo': registro.get('periodo'),
                'creditos': registro.get(
                    'creditos_no_periodo'
                ),
                'situacao': _texto(
                    registro.get('situacao_das_opcoes')
                ),
                'fonte': _texto(
                    registro.get('fonte_lista_opcoes')
                )
            })

    codigos = {
        grupo['codigo']
        for grupo in grupos
    }

    opcoes = []

    for registro in _linhas(
        OPTATIVAS,
        'DISCIPLINAS CONFIRMADAS'
    ):

        if _texto(
            registro.get('codigo_grupo')
        ) in codigos:

            opcoes.append({
                'grupo': _texto(
                    registro.get('codigo_grupo')
                ),
                'codigo': _texto(
                    registro.get('codigo_opcao')
                ),
                'nome': _texto(
                    registro.get('nome_opcao')
                ),
                'fonte': _texto(
                    registro.get('fonte_oficial')
                )
            })

    return grupos, opcoes
