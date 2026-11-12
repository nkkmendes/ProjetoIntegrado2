"""Importação das grades dos cursos para o banco de dados.

Regras (valem para qualquer execução, quantas vezes for):
  * nada é apagado e nenhum histórico de aluno é tocado;
  * pré-requisitos e co-requisitos são GLOBAIS: valem para todos os cursos.
    Quem já tem requisitos no banco (Computação, vinda da fixture) os mantém;
    a planilha só preenche disciplinas que ainda não têm nenhum;
  * nome e créditos de uma disciplina que já existe não são sobrescritos;
    diferenças aparecem no relatório;
  * só o que a planilha traz é importado: requisito em branco continua em
    branco (a própria planilha diz que célula vazia não significa "sem
    requisito"), nada é inventado.
"""
from django.core.management import call_command
from django.db import transaction

from .catalogos_fluxa import CURSOS_DA_PLANILHA, ler_grade
from .models import Curso, Disciplina, GrupoPreRequisito


def _normalizar_grupos(grupos):
    return sorted(sorted(set(g)) for g in grupos)


def _grupos_do_banco(disciplina):
    return _normalizar_grupos(
        [g.disciplinas.values_list('codigo', flat=True)
         for g in disciplina.grupos_pre_requisito.all()]
    )


def _preencher_requisitos(disciplina, grupos, co, existentes, relatorio, curso):
    """Cria os requisitos só se a disciplina ainda não tem nenhum."""
    desconhecidos = {c for g in grupos for c in g if c not in existentes} \
        | {c for c in co if c not in existentes}
    if desconhecidos:
        relatorio['requisitos_desconhecidos'].update(desconhecidos)

    grupos = [[c for c in g if c in existentes] for g in grupos]
    grupos = [g for g in grupos if g]
    co = [c for c in co if c in existentes]

    if grupos:
        atual = _grupos_do_banco(disciplina)
        if not atual:
            for membros in grupos:
                grupo = GrupoPreRequisito.objects.create(disciplina=disciplina)
                grupo.disciplinas.set([existentes[c] for c in membros])
            relatorio['pre_requisitos_novos'] += len(grupos)
        elif atual != _normalizar_grupos(grupos):
            relatorio['pre_requisitos_diferentes'].append(
                f'{disciplina.codigo} ({curso}): o banco já tem outros pré-requisitos; mantidos.'
            )

    if co and not disciplina.co_requisitos.exists():
        disciplina.co_requisitos.set([existentes[c] for c in co])
        relatorio['co_requisitos_novos'] += len(co)


@transaction.atomic
def importar_grades():
    """Importa os 8 cursos da planilha (Produção, Controle e Automação,
    Elétrica e Química). Devolve um relatório em dicionário."""
    relatorio = {
        'cursos': {},
        'disciplinas_novas': 0,
        'vinculos_novos': 0,
        'pre_requisitos_novos': 0,
        'co_requisitos_novos': 0,
        'pre_requisitos_diferentes': [],
        'dados_diferentes': [],
        'requisitos_desconhecidos': set(),
    }
    grades = {nome: ler_grade(nome) for nome in CURSOS_DA_PLANILHA}

    # 1) Disciplinas e vínculo com cada curso.
    for nome, mapa in grades.items():
        curso, _ = Curso.objects.get_or_create(nome=nome)
        for codigo, dados in mapa.items():
            disciplina, criada = Disciplina.objects.get_or_create(
                codigo=codigo,
                defaults={'nome': dados['nome'], 'creditos': dados['creditos']},
            )
            relatorio['disciplinas_novas'] += int(criada)
            if not criada and (disciplina.nome != dados['nome']
                               or disciplina.creditos != dados['creditos']):
                relatorio['dados_diferentes'].append(
                    f'{codigo}: banco "{disciplina.nome}" ({disciplina.creditos} cr.), '
                    f'planilha de {nome} "{dados["nome"]}" ({dados["creditos"]} cr.).'
                )
            if not disciplina.cursos.filter(pk=curso.pk).exists():
                disciplina.cursos.add(curso)
                relatorio['vinculos_novos'] += 1
        relatorio['cursos'][nome] = len(mapa)

    # 2) Requisitos (depois de todas as disciplinas existirem).
    existentes = Disciplina.objects.in_bulk(field_name='codigo')
    for nome, mapa in grades.items():
        for codigo, dados in mapa.items():
            _preencher_requisitos(
                existentes[codigo], dados['grupos'], dados['co'],
                existentes, relatorio, nome,
            )

    relatorio['requisitos_desconhecidos'] = sorted(relatorio['requisitos_desconhecidos'])
    return relatorio


def importar_tudo(com_horarios=True):
    """Passo único: Computação (fixture) + 8 cursos da planilha + micro-horário.

    A fixture só é carregada na primeira vez (quando Computação ainda não tem
    disciplinas): recarregá-la depois refaria os vínculos das disciplinas com
    os cursos e apagaria ajustes feitos no painel administrativo."""
    if not Disciplina.objects.filter(cursos__nome='Engenharia de Computação').exists():
        call_command('loaddata', 'disciplinas_fluxograma', verbosity=0)
    relatorio = importar_grades()
    if com_horarios:
        from .importar_microhorario import importar
        relatorio['horarios'] = importar()
    return relatorio
