from django.shortcuts import render
from .models import CalendarioMatricula, Disciplina

def inicio(request):
    return render(request, 'index.html')

def telaInicio(request):
    calendario = CalendarioMatricula.objects.first()

    return render(request, 'inicio_html.html', {
        'calendario': calendario
    })

def login(request):
    return render(request, 'login.html')

def criarConta(request):
    return render(request, 'criarConta.html')

def planejamento(request):
    return render(request, 'planejamento (1).html')

def simulacao(request):
    return render(request, 'Simulador (1).html')

def nivelamento(request):
    return render(request, 'nivelamento.html')

def contagem_creditos(request):
    return render(request, 'contagem-creditos.html')

def notas_periodo(request):
    return render(request, 'notas-periodo.html')

def telaErro(request):
    return render(request, 'erro.html')

def fluxograma(request):
    disciplinas = Disciplina.objects.all().order_by('periodo', 'nome')

    return render(request, 'fluxograma.html', {
        'disciplinas': disciplinas
    })