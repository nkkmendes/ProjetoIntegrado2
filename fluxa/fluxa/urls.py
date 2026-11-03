from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView
from matricula import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('planejamento/', views.planejamento, name='planejamento'),
    path('simulacao/', views.simulacao, name='simulacao'),
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
    path('historico/', views.historico, name='historico'),
    path('historico/remover/<str:codigo>/', views.historico_remover, name='historico_remover'),
    path('historico/nivel/remover/<int:area_id>/', views.nivelamento_remover, name='nivelamento_remover'),
    # As três telas antigas foram unidas no Histórico; os endereços antigos continuam funcionando.
    path('nivelamento/', RedirectView.as_view(pattern_name='historico'), name='nivelamento'),
    path('creditos/', RedirectView.as_view(pattern_name='historico'), name='creditos'),
    path('notas-periodo/', RedirectView.as_view(pattern_name='historico'), name='notas_periodo'),
    path('fluxograma/', views.fluxograma, name='fluxograma'),
    path('fluxograma/disciplina/<str:codigo>/', views.detalhes_disciplina, name='detalhes_disciplina'),
    path('fluxograma/concluir/<str:codigo>/', views.marcar_concluida, name='marcar_concluida'),
    path('perfil/', views.perfil, name='perfil'),
]

handler404 = views.erro_404
handler500 = views.erro_500