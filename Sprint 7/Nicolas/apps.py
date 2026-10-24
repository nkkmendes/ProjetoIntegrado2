# AppConfig e a classe que diz ao Django "este pacote Python e uma app".
# Sem registrar essa classe em INSTALLED_APPS (settings.py), o Django
# nunca procuraria models.py, admin.py, migrations/, etc. dentro de
# fluxa/ - ele trataria a pasta so como o pacote de configuracao do
# projeto (onde moram settings.py, urls.py...).
from django.apps import AppConfig


class FluxaConfig(AppConfig):
    # Tipo de campo usado automaticamente como "id" de cada model desta
    # app que nao declarar uma primary key explicita.
    default_auto_field = "django.db.models.AutoField"
    # Caminho Python de import desta app - tem que bater com o que vai
    # em INSTALLED_APPS ("fluxa.apps.FluxaConfig") e com o pacote onde
    # este arquivo esta (fluxa/).
    name = "fluxa"
    # Identificador curto usado internamente pelo Django (ex: nas
    # migrations, em "python manage.py migrate fluxa"). Por padrao seria
    # igual ao ultimo pedaco de 'name', mas deixamos explicito aqui.
    label = "fluxa"
