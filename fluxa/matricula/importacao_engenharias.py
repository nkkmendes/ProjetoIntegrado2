"""Restaura o legado original e cadastra só os três cursos novos."""
import json

from django.db import transaction

from .catalogos_fluxa import BASE, NOVOS_CURSOS, relacoes_do_curso
from .models import Curso, Disciplina, GrupoPreRequisito


def restaurar_catalogos_legados():
    """Não apaga disciplinas nem históricos; restaura apenas vínculos da matriz.
    A origem para Computação é a fixture do próprio projeto; para Produção,
    grade_producao.json. Pré-requisitos compartilhados são os de Computação.
    """
    fixture = json.loads(
        (BASE / 'fixtures' / 'disciplinas_fluxograma.json').read_text(encoding='utf-8')
    )
    curso_comp, _ = Curso.objects.get_or_create(nome='Engenharia de Computação')
    codigos_comp = []
    comp_por_codigo = {}

    for item in fixture:
        if item['model'] != 'matricula.disciplina':
            continue
        f = item['fields']
        codigo = f['codigo']
        disciplina, _ = Disciplina.objects.update_or_create(
            codigo=codigo,
            defaults={
                'nome': f['nome'],
                'creditos': f['creditos'],
                'creditos_minimos': f.get('creditos_minimos', 0),
            },
        )
        codigos_comp.append(codigo)
        comp_por_codigo[codigo] = (disciplina, f)

    # .set() altera vínculos com cursos, não apaga alunos ou históricos.
    curso_comp.disciplinas.set(Disciplina.objects.filter(codigo__in=codigos_comp))

    for disciplina, f in comp_por_codigo.values():
        disciplina.co_requisitos.set(
            Disciplina.objects.filter(codigo__in=[c[0] for c in f.get('co_requisitos', [])])
        )
        disciplina.grupos_pre_requisito.all().delete()

    for item in fixture:
        if item['model'] != 'matricula.grupoprerequisito':
            continue
        f = item['fields']
        disciplina = Disciplina.objects.get(codigo=f['disciplina'][0])
        grupo = GrupoPreRequisito.objects.create(disciplina=disciplina)
        grupo.disciplinas.set(
            Disciplina.objects.filter(codigo__in=[c[0] for c in f['disciplinas']])
        )

    curso_prod, _ = Curso.objects.get_or_create(nome='Engenharia de Produção')
    origem_prod = json.loads((BASE / 'grade_producao.json').read_text(encoding='utf-8'))
    codigos_prod = []
    for item in origem_prod:
        codigo = item['codigo']
        codigos_prod.append(codigo)
        # Se a mesma disciplina existe em Computação, o nome/créditos de
        # Produção serão exibidos pelo helper relacoes_do_curso no views.py.
        if codigo in comp_por_codigo:
            continue
        Disciplina.objects.update_or_create(
            codigo=codigo,
            defaults={'nome': item['nome'], 'creditos': int(item['creditos'])},
        )
    curso_prod.disciplinas.set(Disciplina.objects.filter(codigo__in=codigos_prod))
    return {'computacao': len(set(codigos_comp)), 'producao': len(set(codigos_prod))}


@transaction.atomic
def importar_engenharias():
    """Importa grade principal. O segundo Excel de optativas é só consulta."""
    legado = restaurar_catalogos_legados()
    criadas = 0
    associacoes = 0
    for nome in NOVOS_CURSOS:
        curso, _ = Curso.objects.get_or_create(nome=nome)
        relacoes = relacoes_do_curso(nome)
        disciplinas_do_curso = []
        for codigo, dados in relacoes.items():
            disciplina, criada = Disciplina.objects.get_or_create(
                codigo=codigo,
                defaults={'nome': dados['nome'], 'creditos': dados['creditos']},
            )
            criadas += int(criada)
            disciplinas_do_curso.append(disciplina)
            if not disciplina.cursos.filter(pk=curso.pk).exists():
                associacoes += 1
        curso.disciplinas.set(disciplinas_do_curso)
    return {
        'linhas': sum(len(relacoes_do_curso(nome)) for nome in NOVOS_CURSOS),
        'novas': criadas,
        'associacoes': associacoes,
        'codigos_com_creditos_diferentes': [],
        'legado': legado,
    }

