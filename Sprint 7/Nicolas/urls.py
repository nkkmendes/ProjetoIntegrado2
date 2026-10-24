"""
URL configuration for fluxa project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from fluxa import views

# urlpatterns e so uma lista. O Django percorre de cima pra baixo e usa
# a primeira entrada cujo caminho combine com a URL pedida - e uma
# cadeia de "if path == ...:" sobre a URL, só que declarativa.
urlpatterns = [
    # Delega TUDO que comece com "admin/" pras rotas que o proprio
    # django.contrib.admin ja define internamente (configuradas pelo
    # admin.py). Nunca passa por uma funcao nossa em views.py.
    path('admin/', admin.site.urls),
    path(
        'disciplinas/concluidas/nova/',
        # view = a funcao a chamar quando a URL bate (esta em views.py).
        views.registrar_disciplina_concluida,
        # name = um alias estavel pra essa rota. Em outros lugares do
        # codigo (ex: redirect() no views.py) usamos esse nome em vez
        # de repetir a string da URL - se a URL mudar, so muda aqui.
        name='registrar_disciplina_concluida',
    ),
]
