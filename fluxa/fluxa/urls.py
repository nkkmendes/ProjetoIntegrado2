from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from matricula import views

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
        auth_views.PasswordResetConfirmView.as_view(
            template_name='redefinir_senha.html',
            success_url=reverse_lazy('login'),
        ),
        name='password_reset_confirm',
    ),
    path('creditos/', views.contagem_creditos, name='creditos'),
    path('notas-periodo/', views.notas_periodo, name='notas_periodo'),
    path('erro/', views.telaErro, name='erro'),
    path('fluxograma/', views.fluxograma, name='fluxograma'),
    path('fluxograma/filtrar/', views.filtrar_disciplinas, name='filtrar_disciplinas'),
    path('fluxograma/disciplina/<str:codigo>/', views.detalhes_disciplina, name='detalhes_disciplina'),
]
