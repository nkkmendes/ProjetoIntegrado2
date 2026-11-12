"""Regras de negócio do Fluxa.

Ficam fora de views.py para que as telas (Perfil, Histórico, Fluxograma,
Simulador, Planejamento) usem exatamente os mesmos cálculos: um número só,
em todos os lugares.
"""
from collections import defaultdict
from decimal import Decimal

from django.db.models import Prefetch

from .models import (
    AreaNivelamento,
    Curso,
    HistoricoDisciplina,
    HorarioTurma,
    PerfilAluno,
    RequisitoNivelamento,
    Turma,
)


def obter_perfil(user):
    """Devolve o perfil do aluno, criando-o se ainda não existir
    (acontece, por exemplo, com usuários criados pelo createsuperuser)."""
    perfil, _ = PerfilAluno.objects.select_related('curso').get_or_create(
        user=user,
        defaults={'curso': Curso.objects.first()},
    )
    return perfil


def calcular_cr(registros):
    """CR = média das médias, ponderada pelos créditos, considerando as
    disciplinas concluídas ou reprovadas que têm média informada.
    Devolve None quando ainda não há nenhuma média."""
    soma = Decimal('0')
    creditos = 0
    for r in registros:
        if r.media is None or r.status == HistoricoDisciplina.EM_CURSO:
            continue
        soma += r.media * r.disciplina.creditos
        creditos += r.disciplina.creditos
    if creditos == 0:
        return None
    return (soma / creditos).quantize(Decimal('0.01'))


def resumo_creditos(perfil):
    """Contagem de créditos calculada a partir do histórico (nada é digitado)."""
    registros = list(perfil.historico.select_related('disciplina'))
    curso_codigos = set()
    total_curso = 0
    if perfil.curso:
        for d in perfil.curso.disciplinas.all():
            curso_codigos.add(d.codigo)
            total_curso += d.creditos

    cumpridos = cumpridos_no_curso = em_curso = concluidas = 0
    for r in registros:
        if r.status == HistoricoDisciplina.CONCLUIDA:
            concluidas += 1
            cumpridos += r.disciplina.creditos
            if r.disciplina.codigo in curso_codigos:
                cumpridos_no_curso += r.disciplina.creditos
        elif r.status == HistoricoDisciplina.EM_CURSO:
            em_curso += r.disciplina.creditos

    return {
        'cumpridos': cumpridos,
        'cumpridos_no_curso': cumpridos_no_curso,
        'fora_do_curso': cumpridos - cumpridos_no_curso,
        'em_curso': em_curso,
        'total_curso': total_curso,
        'pendentes': max(total_curso - cumpridos_no_curso, 0),
        'percentual': round(100 * cumpridos_no_curso / total_curso) if total_curso else 0,
        'disciplinas_concluidas': concluidas,
        'cr': calcular_cr(registros),
    }


def niveis_do_perfil(perfil):
    """{id da área: nível do aluno}. Área ausente = nível não informado."""
    return {n.area_id: n.nivel for n in perfil.niveis.all()}


def avisos_de_nivel(perfil, disciplinas):
    """Para cada disciplina com exigência de nivelamento, devolve a lista de
    avisos: {codigo_da_disciplina: [{'texto': ..., 'bloqueia': bool}, ...]}.

    - nível informado e abaixo do mínimo -> bloqueia;
    - nível não informado -> só um aviso neutro, não bloqueia;
    - nível suficiente -> nenhum aviso.
    """
    niveis = niveis_do_perfil(perfil)
    requisitos = (
        RequisitoNivelamento.objects
        .filter(disciplina__in=list(disciplinas))
        .select_related('area', 'disciplina')
    )
    avisos = {}
    for r in requisitos:
        nivel = niveis.get(r.area_id)
        if nivel is None:
            texto = (f'Exige nível {r.nivel_minimo} em {r.area.nome}; '
                     'seu nível: não informado.')
            bloqueia = False
        elif nivel < r.nivel_minimo:
            texto = (f'Exige nível {r.nivel_minimo} em {r.area.nome}; '
                     f'seu nível: {nivel}.')
            bloqueia = True
        else:
            continue
        avisos.setdefault(r.disciplina.codigo, []).append(
            {'texto': texto, 'bloqueia': bloqueia}
        )
    return avisos


def quadro_de_nivelamento(perfil):
    """Uma linha por área: nível do aluno e as disciplinas que exigem a área."""
    niveis = niveis_do_perfil(perfil)
    linhas = []
    areas = AreaNivelamento.objects.prefetch_related('requisitos__disciplina')
    for area in areas:
        nivel = niveis.get(area.id)
        exigencias = [
            {
                'codigo': r.disciplina.codigo,
                'minimo': r.nivel_minimo,
                'bloqueia': nivel is not None and nivel < r.nivel_minimo,
            }
            for r in area.requisitos.all()
        ]
        linhas.append({'area': area, 'nivel': nivel, 'exigencias': exigencias})
    return linhas


# --------------------------------------------------------------------------
# Simulador e Planejamento
# --------------------------------------------------------------------------
QTD_CORES = 7


def periodo_de_oferta():
    """Período do micro-horário importado (o mais recente que houver)."""
    return (
        Turma.objects.order_by('-periodo_letivo')
        .values_list('periodo_letivo', flat=True)
        .first()
    ) or ''


def cor_da_disciplina(codigo):
    """Mesmo cálculo do simulador.js: a cor de uma disciplina é a mesma em
    todas as telas."""
    return sum(ord(c) for c in codigo) % QTD_CORES


def _minutos(hora):
    return hora.hour * 60 + hora.minute


def intervalos_da_turma(turma):
    """[(dia, início em minutos, fim em minutos, sala)] da turma."""
    return [
        (h.dia_semana, _minutos(h.hora_inicio), _minutos(h.hora_fim), h.sala)
        for h in turma.horarios.all()
    ]


def encontrar_conflitos(turmas):
    """Lista de textos descrevendo cada choque de horário entre as turmas."""
    dias = dict(HorarioTurma.DIAS)
    por_dia = defaultdict(list)
    for turma in turmas:
        for dia, ini, fim, _sala in intervalos_da_turma(turma):
            por_dia[dia].append((ini, fim, turma))
    conflitos = []
    for dia, itens in por_dia.items():
        itens.sort(key=lambda x: (x[0], x[1]))
        for i, (ini_a, fim_a, a) in enumerate(itens):
            for ini_b, fim_b, b in itens[i + 1:]:
                if ini_b >= fim_a:
                    break
                if a.pk != b.pk:
                    conflitos.append(
                        f'{a.disciplina.codigo} e {b.disciplina.codigo} '
                        f'({dias[dia]}, {ini_b // 60:02d}:{ini_b % 60:02d})'
                    )
    return conflitos


def pre_requisitos_cumpridos(disciplina, concluidas):
    """Pré-requisito global: vale se algum grupo estiver completo (OU entre
    grupos; E dentro de cada grupo). Sem grupos = nada a exigir."""
    grupos = [
        {d.codigo for d in g.disciplinas.all()}
        for g in disciplina.grupos_pre_requisito.all()
    ]
    grupos = [g for g in grupos if g]
    if not grupos:
        return True
    return any(g <= concluidas for g in grupos)


def disciplinas_disponiveis(perfil, periodo):
    """O que o aluno pode cursar no período de oferta, a partir do histórico.

    Aparecem as disciplinas do curso do perfil que:
      * ainda não foram concluídas nem estão em curso (reprovada pode refazer);
      * têm os pré-requisitos concluídos;
      * não estão bloqueadas pelo nivelamento (nível informado abaixo do mínimo);
      * têm turma no período;
      * têm os co-requisitos atendidos: cada co-requisito precisa estar concluído,
        em curso ou também disponível agora (para cursar junto). Quem depende de
        um co-requisito que não pode ser cursado fica de fora.

    Cada disciplina devolvida ganha `coreqs_juntos`: os co-requisitos que o aluno
    ainda precisa escolher na mesma grade. Devolve {'disciplinas', 'ocultas'}.
    """
    chaves = ('pre_requisito', 'nivelamento', 'co_requisito', 'sem_turma')
    vazio = {'disciplinas': [], 'ocultas': dict.fromkeys(chaves, 0)}
    if not perfil.curso or not periodo:
        return vazio

    situacoes = dict(perfil.historico.values_list('disciplina__codigo', 'status'))
    concluidas = {
        c for c, s in situacoes.items() if s == HistoricoDisciplina.CONCLUIDA
    }
    em_curso = {
        c for c, s in situacoes.items() if s == HistoricoDisciplina.EM_CURSO
    }
    ja_tem = concluidas | em_curso

    candidatas = list(
        perfil.curso.disciplinas
        .exclude(codigo__in=ja_tem)
        .prefetch_related(
            'grupos_pre_requisito__disciplinas',
            'co_requisitos',
            Prefetch(
                'turmas',
                queryset=Turma.objects.filter(periodo_letivo=periodo)
                .prefetch_related('horarios')
                .order_by('codigo'),
                to_attr='turmas_periodo',
            ),
        )
        .order_by('codigo')
    )
    avisos = avisos_de_nivel(perfil, candidatas)

    ocultas = dict.fromkeys(chaves, 0)
    base = []
    for d in candidatas:
        if not pre_requisitos_cumpridos(d, concluidas):
            ocultas['pre_requisito'] += 1
        elif any(a['bloqueia'] for a in avisos.get(d.codigo, [])):
            ocultas['nivelamento'] += 1
        elif not d.turmas_periodo:
            ocultas['sem_turma'] += 1
        else:
            base.append(d)

    # Co-requisitos: tira quem depende de um co-requisito que não dá para cursar.
    # Remover uma disciplina pode derrubar outra que dependia dela, então repete.
    atuais = {d.codigo for d in base}
    mudou = True
    while mudou:
        mudou = False
        for d in list(base):
            faltam = [
                c.codigo for c in d.co_requisitos.all()
                if c.codigo not in ja_tem and c.codigo not in atuais
            ]
            if faltam:
                base.remove(d)
                atuais.discard(d.codigo)
                ocultas['co_requisito'] += 1
                mudou = True
    for d in base:
        d.coreqs_juntos = sorted(
            c.codigo for c in d.co_requisitos.all() if c.codigo not in ja_tem
        )
    return {'disciplinas': base, 'ocultas': ocultas}


def dados_do_simulador(disciplinas):
    """Estrutura entregue ao simulador.js (via json_script)."""
    resultado = []
    for d in disciplinas:
        resultado.append({
            'codigo': d.codigo,
            'nome': d.nome,
            'creditos': d.creditos,
            'cor': cor_da_disciplina(d.codigo),
            'juntos': list(getattr(d, 'coreqs_juntos', [])),
            'turmas': [
                {
                    'id': t.pk,
                    'codigo': t.codigo,
                    'professor': t.professor,
                    'vagas': t.vagas,
                    'horarios': [
                        {'dia': dia, 'inicio': ini, 'fim': fim, 'sala': sala}
                        for dia, ini, fim, sala in intervalos_da_turma(t)
                    ],
                }
                for t in d.turmas_periodo
            ],
        })
    return resultado


def validar_selecao(perfil, periodo, ids):
    """Confere no servidor o que o navegador enviou. Devolve (turmas, erro)."""
    try:
        ids = {int(i) for i in ids}
    except (TypeError, ValueError):
        return [], 'Seleção inválida.'
    if not ids:
        return [], 'Escolha ao menos uma turma antes de salvar.'

    disponiveis = disciplinas_disponiveis(perfil, periodo)['disciplinas']
    por_id = {t.pk: t for d in disponiveis for t in d.turmas_periodo}
    if not ids <= set(por_id):
        return [], 'Há turmas que não estão disponíveis para você neste período.'

    turmas = [por_id[i] for i in sorted(ids)]
    codigos = [t.disciplina.codigo for t in turmas]
    if len(codigos) != len(set(codigos)):
        return [], 'Escolha no máximo uma turma por disciplina.'

    escolhidas = set(codigos)
    faltando = []
    nomes = {d.codigo: d for d in disponiveis}
    for t in turmas:
        for c in nomes[t.disciplina.codigo].coreqs_juntos:
            if c not in escolhidas:
                faltando.append(f'{t.disciplina.codigo} exige cursar junto {c}')
    if faltando:
        return [], 'Co-requisito faltando na grade: ' + '; '.join(faltando) + '.'

    conflitos = encontrar_conflitos(turmas)
    if conflitos:
        return [], 'Conflito de horário: ' + '; '.join(conflitos) + '.'
    return turmas, ''


def resumo_da_grade(turmas):
    """Dados prontos para mostrar uma grade salva (créditos, blocos, chips)."""
    turmas = sorted(turmas, key=lambda t: t.disciplina.codigo)
    inicio_h, fim_h = 7, 19
    for t in turmas:
        for _dia, ini, fim, _sala in intervalos_da_turma(t):
            inicio_h = min(inicio_h, ini // 60)
            fim_h = max(fim_h, -(-fim // 60))
    total_min = (fim_h - inicio_h) * 60

    blocos, chips = [], []
    for t in turmas:
        cor = cor_da_disciplina(t.disciplina.codigo)
        chips.append({'texto': f'{t.disciplina.codigo} · {t.codigo}', 'cor': cor})
        for dia, ini, fim, _sala in intervalos_da_turma(t):
            blocos.append({
                'cor': cor,
                'esquerda': round(dia * 100 / 6, 3),
                'topo': round((ini - inicio_h * 60) * 100 / total_min, 3),
                'altura': round((fim - ini) * 100 / total_min, 3),
            })
    return {
        'creditos': sum(t.disciplina.creditos for t in turmas),
        'n_disciplinas': len(turmas),
        'blocos': blocos,
        'chips': chips,
    }
