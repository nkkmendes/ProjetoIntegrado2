from django.shortcuts import render


def inicio(request):
    return render(request, 'index.html')


def planejamento(request):
    return render(request, 'planejamento (1).html')

def simulacao(request):
    return render(request, 'Simulador (1).html')