from django.core.management.base import BaseCommand, CommandError

from matricula.importacao_engenharias import importar_tudo


class Command(BaseCommand):
    help = (
        'Carrega no banco os cursos, disciplinas, pré-requisitos e (opcionalmente) '
        'as turmas do micro-horário. Pode ser executado várias vezes: não apaga nada.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--sem-horarios', action='store_true',
            help='Não importa o micro-horário (turmas e horários).',
        )

    def handle(self, *args, **opcoes):
        try:
            r = importar_tudo(com_horarios=not opcoes['sem_horarios'])
        except (OSError, ValueError, KeyError, ImportError, RuntimeError) as erro:
            raise CommandError(str(erro))

        self.stdout.write(self.style.SUCCESS('Importação concluída.'))
        for curso, n in r['cursos'].items():
            self.stdout.write(f'  {curso}: {n} disciplinas na grade')
        self.stdout.write(
            f"  Disciplinas novas: {r['disciplinas_novas']} | vínculos curso-disciplina novos: "
            f"{r['vinculos_novos']} | pré-requisitos novos: {r['pre_requisitos_novos']} | "
            f"co-requisitos novos: {r['co_requisitos_novos']}"
        )
        if 'horarios' in r:
            h = r['horarios']
            self.stdout.write(
                f"  Micro-horário {h['periodo']}: {h['turmas_criadas']} turmas novas, "
                f"{h['turmas_atualizadas']} atualizadas, {h['horarios']} horários."
            )
        for titulo, chave in (
            ('Pré-requisitos que o banco já tinha de outra forma (mantidos)', 'pre_requisitos_diferentes'),
            ('Nomes/créditos diferentes entre o banco e a planilha (mantidos)', 'dados_diferentes'),
        ):
            if r[chave]:
                self.stdout.write(self.style.WARNING(f'{titulo}: {len(r[chave])}'))
                for linha in r[chave][:10]:
                    self.stdout.write(f'    - {linha}')
        if r['requisitos_desconhecidos']:
            self.stdout.write(self.style.WARNING(
                'Códigos de requisito que não existem no banco (ignorados): '
                + ', '.join(r['requisitos_desconhecidos'])
            ))
