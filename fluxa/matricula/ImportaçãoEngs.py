
from pathlib import Path

from django.conf import settings
from django.db import transaction

from .models import Curso, Disciplina, GrupoPreRequisito


NOME_ARQUIVO = 'FLUXA_5_engenharias_com_optativas.xlsx'

ABAS = {
    'Computação': 'Engenharia de Computação',
    'Produção (FAR)': 'Engenharia de Produção',
    'Controle e Automação': 'Engenharia de Controle e Automação',
    'Elétrica (ESC)': 'Engenharia Elétrica',
    'Química': 'Engenharia Química',
}


def _texto(valor):
    return str(valor).strip() if valor is not None else ''


def _grupos(texto):
    # A+B: duas disciplinas obrigatórias
    # A|B: alternativas de pré-requisito
    return [
        [
            codigo.strip().upper()
            for codigo in parte.split('+')
            if codigo.strip()
        ]
        for parte in texto.split('|')
        if parte.strip()
    ]


def importar_engenharias():
    from openpyxl import load_workbook

    caminho = (
        Path(settings.BASE_DIR)
        / 'matricula'
        / 'dados'
        / NOME_ARQUIVO
    )

    if not caminho.is_file():
        raise FileNotFoundError(
            f'Planilha não encontrada: {caminho}'
        )

    livro = load_workbook(
        caminho,
        read_only=True,
        data_only=True
    )

    registros = []
    requisitos = {}

    try:
        for aba, curso_esperado in ABAS.items():

            if aba not in livro.sheetnames:
                raise ValueError(
                    f'Falta a aba {aba} no Excel.'
                )

            linhas = livro[aba].iter_rows(
                values_only=True
            )

            cabecalho = next(linhas, None)

            if not cabecalho:
                raise ValueError(
                    f'Aba vazia: {aba}'
                )

            colunas = {
                _texto(c).lower(): indice
                for indice, c in enumerate(cabecalho)
            }

            obrigatorias = {
                'curso',
                'codigo',
                'nome',
                'creditos'
            }

            if not obrigatorias.issubset(colunas):
                raise ValueError(
                    f'Colunas obrigatórias ausentes: {aba}'
                )

            def ler(linha, campo):
                indice = colunas.get(campo)

                if indice is None or indice >= len(linha):
                    return ''

                return _texto(linha[indice])

            for numero, linha in enumerate(
                linhas, start=2
            ):
                codigo = ler(
                    linha, 'codigo'
                ).upper()

                if not codigo:
                    continue

                nome_curso = ler(linha, 'curso')
                nome = ler(linha, 'nome')

                if nome_curso != curso_esperado or not nome:
                    raise ValueError(
                        f'Dados inválidos em {aba}, '
                        f'linha {numero}'
                    )

                try:
                    numero_creditos = float(
                        ler(linha, 'creditos')
                    )

                    creditos = int(numero_creditos)

                    if (
                        creditos < 0
                        or numero_creditos != creditos
                    ):
                        raise ValueError()

                except ValueError:
                    raise ValueError(
                        f'Créditos inválidos em {aba}, '
                        f'linha {numero}'
                    )

                registros.append((
                    nome_curso,
                    codigo,
                    nome,
                    creditos
                ))

                pre = ler(
                    linha, 'pre_requisitos'
                ).upper()

                co = ler(
                    linha, 'co_requisitos'
                ).upper()

                atual = requisitos.setdefault(
                    codigo,
                    {'pre': '', 'co': ''}
                )

                for tipo, novo in [
                    ('pre', pre),
                    ('co', co)
                ]:
                    if novo:
                        if (
                            atual[tipo]
                            and atual[tipo] != novo
                        ):
                            raise ValueError(
                                f'Requisitos divergentes: {codigo}'
                            )

                        atual[tipo] = novo

    finally:
        livro.close()

    novos = 0
    associacoes = 0
    avisos = set()

    with transaction.atomic():

        # Cadastrar as disciplinas
        for nome_curso, codigo, nome, creditos in registros:

            curso, _ = Curso.objects.get_or_create(
                nome=nome_curso
            )

            disciplina, criada = Disciplina.objects.get_or_create(
                codigo=codigo,
                defaults={
                    'nome': nome,
                    'creditos': creditos
                }
            )

            if criada:
                novos += 1

            elif disciplina.creditos != creditos:
                avisos.add(codigo)

            if not disciplina.cursos.filter(
                pk=curso.pk
            ).exists():
                disciplina.cursos.add(curso)
                associacoes += 1

        # Cadastrar os pré-requisitos
        for codigo, requisitos_disciplina in requisitos.items():

            disciplina = Disciplina.objects.get(
                codigo=codigo
            )

            pre = requisitos_disciplina['pre']
            co = requisitos_disciplina['co']

            # Preservar os requisitos já cadastrados
            if (
                pre
                and not disciplina.grupos_pre_requisito.exists()
            ):
                for grupo_codigos in _grupos(pre):

                    materias = list(
                        Disciplina.objects.filter(
                            codigo__in=grupo_codigos
                        )
                    )

                    if len(materias) != len(set(grupo_codigos)):
                        raise ValueError(
                            f'Pré-requisito não cadastrado: '
                            f'{codigo}'
                        )

                    grupo = GrupoPreRequisito.objects.create(
                        disciplina=disciplina
                    )

                    grupo.disciplinas.set(materias)

            # Cadastrar os co-requisitos
            if co:
                codigos_co = [
                    c
                    for grupo in _grupos(co)
                    for c in grupo
                ]

                materias = list(
                    Disciplina.objects.filter(
                        codigo__in=codigos_co
                    )
                )

                if len(materias) != len(set(codigos_co)):
                    raise ValueError(
                        f'Co-requisito não cadastrado: '
                        f'{codigo}'
                    )

                disciplina.co_requisitos.add(
                    *materias
                )

    return {
        'linhas': len(registros),
        'novas': novos,
        'associacoes': associacoes,
        'codigos_com_creditos_diferentes': sorted(avisos)
    }
