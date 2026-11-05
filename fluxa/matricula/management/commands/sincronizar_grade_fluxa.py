
from django.core.management.base import BaseCommand, CommandError
from matricula.importacao_engenharias import importar_engenharias


class Command(BaseCommand):
    help = "Sincronizar as grades curriculares do FLUXA"

    def handle(self, *args, **kwargs):
        try:
            resultado = importar_engenharias()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Sincronização concluída: {resultado}"
                )
            )

        except (OSError, ValueError, KeyError, ImportError) as erro:
            raise CommandError(str(erro))
