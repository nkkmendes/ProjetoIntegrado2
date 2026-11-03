"""Regras de negócio do histórico do aluno.

Ficam fora de views.py para que as telas (Perfil, Histórico, Fluxograma) usem
exatamente os mesmos cálculos: um número só, em todos os lugares.
"""
from decimal import Decimal

from .models import (
    AreaNivelamento,
    Curso,
    HistoricoDisciplina,
    PerfilAluno,
    RequisitoNivelamento,
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
