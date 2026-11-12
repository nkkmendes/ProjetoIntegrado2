"""Nome antigo do comando; use importar_dados."""
from matricula.management.commands.importar_dados import Command as ImportarDados


class Command(ImportarDados):
    help = 'Mesmo que importar_dados (nome antigo mantido por compatibilidade).'
