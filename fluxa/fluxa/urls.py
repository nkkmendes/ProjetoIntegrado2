from django.contrib import admin
from django.urls import path
from matricula import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('planejamento/', views.planejamento, name='planejamento'),
    path('simulacao/', views.simulacao, name='simulacao'),
    path('nivelamento/', views.nivelamento, name='nivelamento'),
    path('', views.telaInicio, name='telaInicio'),
    path('login/', views.login, name='login'),
    path('criarConta/', views.criarConta, name='criarConta'),
]
