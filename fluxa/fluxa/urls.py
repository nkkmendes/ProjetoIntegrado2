from django.contrib import admin
from django.urls import path
from matricula import views

from matricula import views as matricula_views




urlpatterns = [
    path('admin/', admin.site.urls),
    path('planejamento/', views.planejamento, name='planejamento'),
    path('simulacao/', views.simulacao, name='simulacao'),
    path('nivelamento/', views.nivelamento, name='nivelamento'), 
    path('creditos/', views.contagem_creditos, name='creditos'),
    path('notas-periodo/', views.notas_periodo, name='notas_periodo'),
    
    path('planejamento-banco/', views.planejamento_banco, name='planejamento_banco'),
    path('simulador-banco/', views.simulador_banco, name='simulador_banco'),
    path('nivelamento-banco/', views.nivelamento_banco, name='nivelamento_banco'),
]




