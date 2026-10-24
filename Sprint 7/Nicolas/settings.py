"""
Django settings for fluxa project.

Gerado para Django 6.1 — https://docs.djangoproject.com/en/6.1/ref/settings/
"""

from pathlib import Path

# BASE_DIR = .../django  (pasta que contem o manage.py). Usado abaixo
# pra montar o caminho do banco sem precisar de caminho absoluto fixo.
BASE_DIR = Path(__file__).resolve().parent.parent

# Chave usada pelo Django pra assinar cookies de sessao, tokens de CSRF,
# etc. O prefixo "django-insecure-" e o proprio Django avisando que essa
# chave e de DESENVOLVIMENTO - pra producao, deveria vir de variavel de
# ambiente, nunca hardcoded no codigo.
SECRET_KEY = "django-insecure-4*vb%jr9t1m3$7!wj($kwwwrwmdopir^0@p%3v%ui5(c!bdsb+"

# DEBUG=True mostra a pagina de erro detalhada (traceback, variaveis,
# etc.) quando algo quebra - essencial em desenvolvimento, mas nunca
# deixar True em producao (exporia informacao sensivel pra qualquer
# visitante).
DEBUG = True

# Lista de hosts/dominios que podem servir esse projeto. Vazio + DEBUG=True
# deixa o Django aceitar localhost/127.0.0.1 automaticamente; em producao
# (DEBUG=False) seria obrigatorio listar o dominio real aqui.
ALLOWED_HOSTS = []


# Toda app usada no projeto precisa estar nessa lista - e o que faz o
# Django "ver" os models, templates, management commands, etc. de cada
# uma. Sem "fluxa.apps.FluxaConfig" aqui, os models do projeto nem
# apareceriam pro makemigrations.
INSTALLED_APPS = [
    # Aplicacoes padrao do Django
    "django.contrib.admin",        # a interface administrativa (admin.py)
    "django.contrib.auth",         # sistema de usuarios/login (createsuperuser)
    "django.contrib.contenttypes", # suporte generico a tipos de model (usado pelo admin/auth)
    "django.contrib.sessions",     # sessoes (cookies) - necessario pro login do admin
    "django.contrib.messages",     # framework de mensagens (usado em views.py: messages.success(...))
    "django.contrib.staticfiles",  # serve CSS/JS/imagens estaticas (inclusive as do admin)
    # Aplicacoes do projeto
    "fluxa.apps.FluxaConfig",
]

# Pipeline de processamento de toda requisicao/resposta, em ordem. Cada
# middleware pode inspecionar/alterar a requisicao antes da view rodar,
# e a resposta depois.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",      # disponibiliza request.session
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",                  # protecao contra CSRF (exige {% csrf_token %} nos forms)
    "django.contrib.auth.middleware.AuthenticationMiddleware",   # disponibiliza request.user
    "django.contrib.messages.middleware.MessageMiddleware",      # necessario pra messages.success() funcionar
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Qual arquivo de urls.py e a "porta de entrada" das rotas do projeto.
ROOT_URLCONF = "fluxa.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],        # pastas extras de template fora das apps (nao usamos)
        # APP_DIRS=True faz o Django procurar automaticamente dentro de
        # "<app>/templates/" de cada app instalada - e por isso que
        # fluxa/templates/fluxa/registrar_disciplina_concluida.html e
        # encontrado sem precisar listar o caminho aqui.
        "APP_DIRS": True,
        "OPTIONS": {
            # Context processors injetam variaveis automaticamente em
            # TODO template renderizado (sem o view precisar passar
            # elas no dicionario de contexto).
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",        # disponibiliza {{ user }} no template
                "django.contrib.messages.context_processors.messages",  # disponibiliza {{ messages }} no template
            ],
        },
    },
]

WSGI_APPLICATION = "fluxa.wsgi.application"
ASGI_APPLICATION = "fluxa.asgi.application"


# Qual banco de dados usar. SQLite = um unico arquivo (db.sqlite3) na
# raiz do projeto, sem precisar instalar/configurar um servidor de banco
# separado - ideal pra desenvolvimento/trabalho de escola.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Regras aplicadas quando um usuario (ex: via createsuperuser ou um
# formulario de cadastro) define uma senha - nao usado diretamente pelo
# nosso formulario de Historico, mas faz parte do django.contrib.auth.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Idioma e fuso horario usados pra traduzir textos padrao do Django
# (ex: labels do admin) e formatar/interpretar datas.
LANGUAGE_CODE = "pt-br"

TIME_ZONE = "America/Sao_Paulo"

USE_I18N = True

# USE_TZ=True guarda datas/horas no banco em UTC e converte pra
# TIME_ZONE na hora de exibir - evita bug de fuso horario quando o
# servidor muda de lugar.
USE_TZ = True


# Prefixo de URL pra arquivos estaticos (CSS/JS/imagens), incluindo os
# que o proprio admin usa pra se estilizar.
STATIC_URL = "static/"

# Tipo de campo usado automaticamente como "id" de cada model que nao
# declara uma primary key explicita (todos os nossos usam o padrao).
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
