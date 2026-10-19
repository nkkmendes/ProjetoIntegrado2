from django.shortcuts import render

from django.shortcuts import render, redirect
from .models import PlanejamentoSalvo, SimulacaoSalva, NivelamentoSalvo

def inicio(request):
    return render(request, 'index.html')


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





def planejamento_banco(request):
    if request.method == 'POST':
        PlanejamentoSalvo.objects.create(
            nome=request.POST['nome'],
            periodo=request.POST['periodo'],
            disciplinas=request.POST['disciplinas']
        )
        return redirect('planejamento_banco')

    dados = PlanejamentoSalvo.objects.all()
    return render(request, 'planejamento (1).html', {'dados': dados})


def simulador_banco(request):
    if request.method == 'POST':
        SimulacaoSalva.objects.create(
            nome=request.POST['nome'],
            disciplinas=request.POST['disciplinas']
        )
        return redirect('simulador_banco')

    dados = SimulacaoSalva.objects.all()
    return render(request, 'Simulador (1).html', {'dados': dados})


def nivelamento_banco(request):
    if request.method == 'POST':
        NivelamentoSalvo.objects.create(
            nome=request.POST['nome'],
            area=request.POST['area'],
            resultado=request.POST['resultado']
        )
        return redirect('nivelamento_banco')

    dados = NivelamentoSalvo.objects.all()
    return render(request, 'nivelamento.html', {'dados': dados})


def inicio(request):
    return render(request, 'index.html')


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





def planejamento_banco(request):
    if request.method == 'POST':
        PlanejamentoSalvo.objects.create(
            nome=request.POST['nome'],
            periodo=request.POST['periodo'],
            disciplinas=request.POST['disciplinas']
        )
        return redirect('planejamento_banco')

    dados = PlanejamentoSalvo.objects.all()
    return render(request, 'planejamento (1).html', {'dados': dados})


def simulador_banco(request):
    if request.method == 'POST':
        SimulacaoSalva.objects.create(
            nome=request.POST['nome'],
            disciplinas=request.POST['disciplinas']
        )
        return redirect('simulador_banco')

    dados = SimulacaoSalva.objects.all()
    return render(request, 'Simulador (1).html', {'dados': dados})


def nivelamento_banco(request):
    if request.method == 'POST':
        NivelamentoSalvo.objects.create(
            nome=request.POST['nome'],
            area=request.POST['area'],
            resultado=request.POST['resultado']
        )
        return redirect('nivelamento_banco')

    dados = NivelamentoSalvo.objects.all()
    return render(request, 'nivelamento.html', {'dados': dados})
