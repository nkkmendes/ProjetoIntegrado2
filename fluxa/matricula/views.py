from django.shortcuts import render


def inicio(request):
    return render(request, 'index.html')

def telaInicio(request):
    return render(request, 'inicio_html.html')

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
