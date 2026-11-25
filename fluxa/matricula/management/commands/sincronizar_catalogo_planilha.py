from django.core.management.base import BaseCommand
from django.db import transaction

from matricula.catalogos_fluxograma import ABAS, relacoes_do_curso
from matricula.models import Curso, Disciplina
from matricula.regras_planilha import catalogo_regras


class Command(BaseCommand):
    help = 'Completa o catálogo usando a planilha A; as regras por curso são lidas dessa mesma fonte.'

    @transaction.atomic
    def handle(self, *args, **options):
        novas = 0
        for nome in ABAS:
            curso, _ = Curso.objects.get_or_create(nome=nome)
            curriculo = relacoes_do_curso(nome)
            regras, _ = catalogo_regras(nome)
            for codigo, dados in regras.items():
                d, criada = Disciplina.objects.get_or_create(codigo=codigo, defaults={
                    'nome': dados['nome'], 'creditos': dados['creditos'],
                })
                novas += int(criada)
                if codigo in curriculo:
                    d.cursos.add(curso)
        if options.get('verbosity', 1):
            self.stdout.write(self.style.SUCCESS(f'Catálogo atualizado: {novas} disciplinas novas. Históricos preservados.'))
