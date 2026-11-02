from django.contrib import admin
from django.urls import path
from matricula import views

from matricula import views as matricula_views




urlpatterns = [
    path('admin/', admin.site.urls),
    path('planejamento/', views.planejamento, name='planejamento'),
    path('simulacao/', views.simulacao, name='simulacao'),
    path('nivelamento/', views.nivelamento, name='nivelamento'),
    path('', views.telaInicio, name='telaInicio'),
    path('login/', views.login, name='login'),
    path('criarConta/', views.criarConta, name='criarConta'),
    path('logout/', views.logout_view, name='logout'),
    path('recuperar-senha/', views.recuperar_senha, name='recuperar_senha'),
    path(
        'redefinir-senha/<uidb64>/<token>/',
        views.RedefinirSenhaView.as_view(),
        name='password_reset_confirm',
    ),
    path('creditos/', views.contagem_creditos, name='creditos'),
    path('notas-periodo/', views.notas_periodo, name='notas_periodo'),
    path('fluxograma/', views.fluxograma, name='fluxograma'),
    path('fluxograma/filtrar/', views.filtrar_disciplinas, name='filtrar_disciplinas'),
    path('fluxograma/disciplina/<str:codigo>/', views.detalhes_disciplina, name='detalhes_disciplina'),
    path('fluxograma/concluir/<str:codigo>/', views.marcar_concluida, name='marcar_concluida'),
    path('perfil/', views.perfil, name='perfil'),
]

handler404 = views.erro_404
handler500 = views.erro_500