
"""Fluxograma das nove engenharias por periodo."""

import unicodedata

from collections import defaultdict
from types import SimpleNamespace
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from .catalogos_fluxograma import linhas_do_curso, relacoes_do_curso
from .models import Disciplina, HistoricoDisciplina
from .servicos import obter_perfil
from .regras_planilha import RegrasAluno


CARTA_L = 230
CARTA_A = 88
ESPACO_H = 110
ESPACO_V = 30
MARGEM_X = 20
TOPO = 78

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


def _relacoes_completas(nome):
    """O desenho contém somente a matriz curricular da engenharia escolhida.

    A avaliação do histórico usa RegrasAluno; alternativas de currículos antigos
    da ementa não criam cartões extras nesta matriz.
    """
    return relacoes_do_curso(nome)


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


def _setas_do_curso(cartas, relacoes, envolvidos):
    """Calcula SVG no servidor, usando as mesmas medidas dos cartões."""
    por_codigo = defaultdict(list)
    for carta in cartas:
        por_codigo[carta.codigo].append(carta)
    setas = []
    for destino in cartas:
        regra = relacoes[destino.codigo]
        requisitos = {(codigo, False) for grupo in regra['grupos'] for codigo in grupo}
        requisitos.update((codigo, True) for codigo in regra['co'])
        for codigo, co in sorted(requisitos):
            if codigo == destino.codigo or codigo not in por_codigo:
                continue
            # Para grupos que reaparecem, conecta a ocorrência anterior mais
            # próxima, mantendo cada posição da matriz no desenho.
            opcoes = por_codigo[codigo]
            anteriores = [c for c in opcoes if c.periodo <= destino.periodo]
            origem = max(anteriores or opcoes, key=lambda c: c.periodo)
            x1, y1 = origem.x + CARTA_L, origem.y + CARTA_A // 2
            x2, y2 = destino.x - 4, destino.y + CARTA_A // 2
            if x2 > x1 + 20:
                meio = (x1 + x2) // 2
                caminho = f'M{x1},{y1} C{meio},{y1} {meio},{y2} {x2},{y2}'
            else:
                x2 = destino.x + CARTA_L + 4
                desvio = max(x1, x2) + 55
                caminho = f'M{x1},{y1} C{desvio},{y1} {desvio},{y2} {x2},{y2}'
            setas.append({
                'caminho': caminho, 'co': co,
                'origem': codigo, 'destino': destino.codigo,
                'origem_chave': origem.chave, 'destino_chave': destino.chave,
                'destaque': codigo in envolvidos and destino.codigo in envolvidos,
            })
    return setas


def _texto_requisitos(grupos):
    """Mantém explícitas as alternativas e as exigências simultâneas."""
    return ' ou '.join(
        '(' + ' e '.join(grupo) + ')' if len(grupos) > 1 and len(grupo) > 1
        else ' e '.join(grupo)
        for grupo in grupos
    )


def _opcoes_do_grupo(codigo_grupo, regras_aluno):
    opcoes = regras_aluno.opcoes.get(codigo_grupo, {})
    sem_nome = [codigo for codigo in opcoes
                if not regras_aluno.regras.get(codigo, {}).get('nome')]
    nomes_banco = dict(Disciplina.objects.filter(codigo__in=sem_nome).values_list('codigo', 'nome')) if sem_nome else {}
    resultado = []
    for codigo, creditos in sorted(opcoes.items()):
        regra = regras_aluno.regras.get(codigo, {})
        pre = regra.get('grupos', [])
        co = regra.get('co_grupos', [])
        adicionais = regra.get('adicionais', '')
        nao_verificada = not regra or 'nao verificad' in _normalizar(regra.get('verificacao', ''))
        concluida = codigo in regras_aluno.concluidas
        em_curso = codigo in regras_aluno.em_curso
        pendente = nao_verificada or bool(regras_aluno.bloqueio(codigo) or regras_aluno.correquisitos(codigo))
        resultado.append({
            'codigo': codigo,
            'nome': regra.get('nome') or nomes_banco.get(codigo, codigo),
            'creditos': creditos,
            'concluida': concluida,
            'em_curso': em_curso,
            'tem_requisitos': bool(pre or co or adicionais),
            'bloqueada': not concluida and not em_curso and pendente,
            'nao_verificada': nao_verificada,
            'pre_requisitos': _texto_requisitos(pre),
            'co_requisitos': _texto_requisitos(co),
            'adicionais': adicionais,
        })
    return resultado


@login_required
def grafo_fluxograma(request):
    """Disponibiliza as relações curriculares da engenharia selecionada."""

    perfil = obter_perfil(request.user)

    if not perfil.curso:
        return JsonResponse({
            'grafo': {},
            'co_requisitos': {},
            'concluidas': [],
            'faltantes': {}
        })

    relacoes = _relacoes_completas(perfil.curso.nome)
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
            'setas': [],
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
            'progresso': None,
        })

    # Ler o Excel da engenharia escolhida
    linhas = linhas_do_curso(curso.nome)
    codigos_curriculo = {item['codigo'] for item in linhas}
    total_disciplinas = len(linhas)
    creditos_total = sum(item['creditos'] for item in linhas)
    relacoes = _relacoes_completas(curso.nome)
    regras_aluno = RegrasAluno(perfil)

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
    # Correquisitos e seus próprios requisitos também fazem parte da cadeia.
    envolvidos = cadeia | ({foco} if foco else set())
    co_cadeia = set()
    pendentes = list(envolvidos)
    vistos = set()
    while pendentes:
        codigo = pendentes.pop()
        if codigo in vistos:
            continue
        vistos.add(codigo)
        for co in relacoes[codigo]['co']:
            if co not in relacoes:
                continue
            co_cadeia.add(co)
            novos = {co} | _cadeia(co, grafo)
            pendentes.extend(novos - vistos)
            envolvidos.update(novos)
    cadeia = envolvidos - {foco} - co_cadeia

    co_foco = (
        co_cadeia - cadeia - {foco}
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

        concluida = codigo in concluidas
        cursando = codigo in em_curso
        if codigo in regras_aluno.regras:
            bloqueio_regra = regras_aluno.bloqueio(codigo)
            co_pendentes = bool(regras_aluno.correquisitos(codigo))
        else:
            bloqueio_regra = 'Requisitos ainda não verificados.'
            co_pendentes = False
        requisitos_pendentes = bool(bloqueio_regra or co_pendentes)

        caixa = SimpleNamespace(
            codigo=codigo,
            chave=chave,
            periodo=periodo,
            nome=item['nome'],
            creditos=item['creditos'],
            grupo_optativa=relacoes[codigo].get('grupo_optativa', False),
            concluida=concluida,
            em_curso=cursando,
            # Correquisitos ainda não cursados também impedem sinalizar
            # liberação incondicional no fluxograma.
            liberada=(
                not concluida
                and not cursando
                and not requisitos_pendentes
            ),
            classe=classe,
            bloqueada=not concluida and not cursando and requisitos_pendentes,
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
        + 80  # Espaço para correquisitos na última coluna.
    )

    altura = (
        TOPO
        + max(
            (len(coluna) for coluna in colunas.values()),
            default=0
        ) * (CARTA_A + ESPACO_V)
        + 20
    )

    # Identificação e ações da disciplina; os requisitos ficam nas setas.
    painel = None
    if foco:
        dados = relacoes[foco]
        painel = {
            'codigo': foco,
            'nome': dados['nome'],
            'creditos': dados['creditos'],
            'em_curso': foco in em_curso,
            'concluida': foco in concluidas,
            'grupo_optativa': dados.get('grupo_optativa', False),
            'opcoes': _opcoes_do_grupo(foco, regras_aluno) if dados.get('grupo_optativa') else [],
        }

    feitas = [
        SimpleNamespace(
            codigo=codigo,
            nome=relacoes[codigo]['nome']
        )
        for codigo in sorted(concluidas)
        if codigo in codigos_curriculo
    ]

    # Progresso do aluno no curso (cada código conta uma vez, mesmo que
    # apareça em mais de um período)
    por_codigo = {d.codigo: d for d in cartas if d.codigo in codigos_curriculo}
    total = len(por_codigo)

    progresso = {
        'concluidas': len(feitas),
        'total': total,
        'percentual': (
            round(100 * len(feitas) / total)
            if total else 0
        ),
        'em_curso': sum(1 for d in por_codigo.values() if d.em_curso),
        'liberadas': sum(1 for d in por_codigo.values() if d.liberada),
    }

    return render(request, 'fluxograma.html', {
        'curso': curso,
        'cabecalhos': cabecalhos,
        'cartas': cartas,
        'setas': _setas_do_curso(cartas, relacoes, envolvidos),
        'disciplinas_curso': [d for d in cartas if d.codigo in codigos_curriculo],
        'isoladas': [],
        'largura': largura,
        'altura': altura,
        'painel': painel,
        'foco': foco,
        'busca': busca,
        'aviso': aviso,
        'resultados': resultados,
        'concluidas': feitas,
        'total_disciplinas': total_disciplinas,
        'creditos_total': creditos_total,
        'progresso': progresso,
    })
