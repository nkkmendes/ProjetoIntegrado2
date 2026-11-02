from pathlib import Path
import json
from django.core.management.base import BaseCommand
from django.db import transaction
from matricula.models import DisciplinaProducao


class Command(BaseCommand):
    help = 'Importa a grade de Engenharia de Produção a partir da planilha fornecida.'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        arquivo = Path(__file__).resolve().parents[2] / 'grade_producao.json'
        registros = json.loads(arquivo.read_text(encoding='utf-8'))
        codigos = {item['codigo'] for item in registros}
        observacoes = []

        for item in registros:
            DisciplinaProducao.objects.update_or_create(
                codigo=item['codigo'],
                defaults={
                    'nome': item['nome'],
                    'periodo': item['periodo'],
                    'creditos': item['creditos'],
                }
            )

        materias = DisciplinaProducao.objects.in_bulk(field_name='codigo')
        for item in registros:
            atual = materias[item['codigo']]
            for campo, chave in (('pre_requisitos', 'pre'), ('co_requisitos', 'co')):
                entrada = item[chave].strip()
                requisitos = []
                if entrada and entrada.casefold() != 'nenhum':
                    for codigo in (c.strip() for c in entrada.split(',')):
                        if codigo in codigos and codigo != item['codigo']:
                            requisitos.append(materias[codigo])
                        else:
                            observacoes.append(f"{item['codigo']} — {campo}: {codigo} (sem ligação)")
                getattr(atual, campo).set(requisitos)

        self.stdout.write(self.style.SUCCESS(f'{len(registros)} disciplinas de Produção importadas.'))
        if observacoes:
            self.stdout.write('Requisitos textuais ou não resolvidos (não foram inventados):')
            for aviso in observacoes:
                self.stdout.write('  ' + aviso)
