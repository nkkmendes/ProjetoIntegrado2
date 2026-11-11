
"""Fluxograma das nove engenharias por periodo."""

import unicodedata

from collections import defaultdict
from types import SimpleNamespace
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from .catalogos_fluxa import linhas_do_curso, relacoes_do_curso
from .models import HistoricoDisciplina
from .servicos import avisos_de_nivel, obter_perfil


CARTA_L = 210
CARTA_A = 74
ESPACO_H = 90
ESPACO_V = 18
MARGEM_X = 24
TOPO = 52

CORES = [
    '#2563eb',
    '#059669',
    '#d97706',
    '#db2777',
    '#0891b2'
]


def _normalizar(texto):
    texto = unicodedata.normalize(
        'NFD',
        str(texto or '')
    )

    return ''.join(
        c for c in texto
        if not unicodedata.combining(c)
    ).lower().strip()


def _historico(perfil):
    return dict(
        perfil.historico.values_list(
            'disciplina__codigo',
            'status'
        )
    )


def _cadeia(codigo, grafo):
    """Busca os requisitos diretos e os requisitos dos requisitos."""

    visitados = {codigo}
    encontrados = set()
    fila = [codigo]

    while fila:
        atual = fila.pop()

        for grupo in grafo.get(atual, []):
            for requisito in grupo:

                if requisito not in grafo:
                    continue

                if requisito == codigo:
                    continue

                encontrados.add(requisito)

                if requisito not in visitados:
                    visitados.add(requisito)
                    fila.append(requisito)

    return encontrados


def _itens(codigos, historico, nomes):
    return [
        {
            'codigo': codigo,
            'nome': nomes.get(codigo, codigo),
            'concluida': (
                historico.get(codigo)
                == HistoricoDisciplina.CONCLUIDA
            )
        }
        for codigo in sorted(set(codigos))
    ]


@login_required
def grafo_fluxograma(request):
    """Envia os requisitos do curso selecionado ao JavaScript."""

    perfil = obter_perfil(request.user)

    if not perfil.curso:
        return JsonResponse({
            'grafo': {},
            'co_requisitos': {},
            'concluidas': [],
            'faltantes': {}
        })

    relacoes = relacoes_do_curso(perfil.curso.nome)
    codigos = set(relacoes)

    grafo = {}
    co = {}
    faltantes = {}

    for codigo, dados in relacoes.items():
        grupos = dados['grupos']

        grafo[codigo] = [
            [
                requisito
                for requisito in grupo
                if requisito in codigos
            ]
            for grupo in grupos
        ]

        grafo[codigo] = [
            grupo
            for grupo in grafo[codigo]
            if grupo
        ]

        co[codigo] = sorted(
            set(dados['co']) & codigos
        )

        ausentes = sorted({
            requisito
            for grupo in grupos
            for requisito in grupo
            if requisito not in codigos
        })

        if ausentes:
            faltantes[codigo] = ausentes

    historico = _historico(perfil)

    concluidas = sorted(
        codigo
        for codigo, status in historico.items()
        if (
            status == HistoricoDisciplina.CONCLUIDA
            and codigo in codigos
        )
    )

    return JsonResponse({
        'grafo': grafo,
        'co_requisitos': co,
        'concluidas': concluidas,
        'faltantes': faltantes
    })


@login_required
def fluxograma(request):
    """Mostra as disciplinas organizadas do primeiro ao decimo periodo."""

    perfil = obter_perfil(request.user)
    curso = perfil.curso

    if not curso:
        return render(request, 'fluxograma.html', {
            'curso': None,
            'cabecalhos': [],
            'cartas': [],
            'isoladas': [],
            'largura': 0,
            'altura': 0,
            'painel': None,
            'foco': '',
            'busca': '',
            'aviso': '',
            'resultados': [],
            'concluidas': [],
            'total_disciplinas': 0,
            'creditos_total': 0,
        })

    # Ler o Excel da engenharia escolhida
    linhas = linhas_do_curso(curso.nome)
    relacoes = relacoes_do_curso(curso.nome)

    historico = _historico(perfil)

    concluidas = {
        codigo
        for codigo, status in historico.items()
        if status == HistoricoDisciplina.CONCLUIDA
    }

    em_curso = {
        codigo
        for codigo, status in historico.items()
        if status == HistoricoDisciplina.EM_CURSO
    }

    # Nivelamento do aluno
    disciplinas_bd = {
        d.codigo: d
        for d in curso.disciplinas.all()
    }

    avisos = avisos_de_nivel(
        perfil,
        list(disciplinas_bd.values())
    )

    # Disciplina selecionada
    foco = request.GET.get('foco', '').strip().upper()

    if foco not in relacoes:
        foco = ''

    # Buscar pelo nome ou codigo
    busca = request.GET.get('q', '').strip()

    aviso = ''
    resultados = []

    if busca:
        termo = _normalizar(busca)
        encontrados = set()

        for item in linhas:
            codigo = item['codigo']

            if codigo in encontrados:
                continue

            if (
                termo in _normalizar(codigo)
                or termo in _normalizar(item['nome'])
            ):
                resultados.append(
                    SimpleNamespace(
                        codigo=codigo,
                        nome=item['nome'],
                        concluida=codigo in concluidas
                    )
                )

                encontrados.add(codigo)

        if not resultados:
            aviso = (
                f'Nenhuma matéria encontrada para "{busca}".'
            )

        elif len(resultados) == 1:
            codigo = resultados[0].codigo

            periodo = relacoes[codigo]['periodo']

            return redirect(
                reverse('fluxograma')
                + '?'
                + urlencode({'foco': codigo})
                + '#c-'
                + codigo
                + '-P'
                + str(periodo)
                + '-1'
            )

        else:
            aviso = (
                f'{len(resultados)} matérias encontradas. Escolha uma:'
            )

    # Construir toda a cadeia dos requisitos
    grafo = {
        codigo: dados['grupos']
        for codigo, dados in relacoes.items()
    }

    cadeia = _cadeia(foco, grafo) if foco else set()

    co_foco = (
        set(relacoes[foco]['co']) - cadeia - {foco}
        if foco else set()
    )

    # Criar sempre os 10 periodos
    colunas = {
        periodo: []
        for periodo in range(1, 11)
    }

    contagem = defaultdict(int)
    linhas_indeterminadas = []

    # Criar cartoes das disciplinas
    for item in linhas:
        codigo = item['codigo']
        periodo = item['periodo']

        contagem[(codigo, periodo)] += 1

        chave = (
            f'{codigo}-P{periodo}-'
            f'{contagem[(codigo, periodo)]}'
        )

        if codigo == foco:
            classe = 'alvo'
        elif codigo in cadeia:
            classe = 'cadeia'
        elif codigo in co_foco:
            classe = 'co'
        else:
            classe = ''

        caixa = SimpleNamespace(
            codigo=codigo,
            chave=chave,
            periodo=periodo,
            nome=item['nome'],
            creditos=item['creditos'],
            concluida=codigo in concluidas,
            classe=classe,
            bloqueada=any(
                a.get('bloqueia')
                for a in avisos.get(codigo, [])
            ),
            x=0,
            y=0,
        )

        if periodo == 0:
            linhas_indeterminadas.append(caixa)
        else:
            colunas[periodo].append(caixa)

    # Materias sem periodo definido ficam separadas
    if linhas_indeterminadas:
        colunas[0] = linhas_indeterminadas

    cabecalhos = []
    cartas = []

    # Posicionar caixas por periodo
    for indice, periodo in enumerate(colunas):
        x = MARGEM_X + indice * (CARTA_L + ESPACO_H)

        if periodo:
            titulo = f'{periodo}º período'
        else:
            titulo = 'Período indeterminado'

        cabecalhos.append({
            'x': x,
            'titulo': titulo
        })

        for i, d in enumerate(colunas[periodo]):
            d.x = x
            d.y = TOPO + i * (CARTA_A + ESPACO_V)

            cartas.append(d)

    # Largura e altura do desenho
    largura = (
        2 * MARGEM_X
        + len(colunas) * CARTA_L
        + (len(colunas) - 1) * ESPACO_H
    )

    altura = (
        TOPO
        + max(
            (len(coluna) for coluna in colunas.values()),
            default=0
        ) * (CARTA_A + ESPACO_V)
        + 20
    )

    # Descobrir quais materias dependem de cada requisito
    dependentes = defaultdict(set)

    for codigo, dados in relacoes.items():
        for grupo in dados['grupos']:
            for requisito in grupo:
                if requisito in relacoes:
                    dependentes[requisito].add(codigo)

    # Painel de detalhes
    painel = None

    if foco:
        dados = relacoes[foco]
        total_grupos = len(dados['grupos'])

        faltantes = sorted({
            requisito
            for grupo in dados['grupos']
            for requisito in grupo
            if requisito not in relacoes
        })

        nomes = {
            codigo: item['nome']
            for codigo, item in relacoes.items()
        }

        painel = {
            'codigo': foco,
            'nome': dados['nome'],
            'creditos': dados['creditos'],
            'creditos_minimos': getattr(
                disciplinas_bd.get(foco),
                'creditos_minimos',
                0
            ),
            'grupos': [
                {
                    'cor': (
                        CORES[i % len(CORES)]
                        if total_grupos > 1
                        else '#6b86a8'
                    ),
                    'itens': _itens(
                        grupo,
                        historico,
                        nomes
                    )
                }
                for i, grupo in enumerate(dados['grupos'])
            ],
            'co': _itens(
                dados['co'],
                historico,
                nomes
            ),
            'dependentes': _itens(
                dependentes.get(foco, set()),
                historico,
                nomes
            ),
            'sem_relacoes': (
                not dados['grupos']
                and not dados['co']
                and not dependentes.get(foco)
            ),
            'avisos_nivel': avisos.get(foco, []),
            'em_curso': foco in em_curso,
            'faltantes': faltantes,
        }

    feitas = [
        SimpleNamespace(
            codigo=codigo,
            nome=relacoes[codigo]['nome']
        )
        for codigo in sorted(concluidas)
        if codigo in relacoes
    ]

    return render(request, 'fluxograma.html', {
        'curso': curso,
        'cabecalhos': cabecalhos,
        'cartas': cartas,
        'isoladas': [],
        'largura': largura,
        'altura': altura,
        'painel': painel,
        'foco': foco,
        'busca': busca,
        'aviso': aviso,
        'resultados': resultados,
        'concluidas': feitas,
        'total_disciplinas': len(linhas),
        'creditos_total': sum(
            item['creditos']
            for item in linhas
        ),
    })
