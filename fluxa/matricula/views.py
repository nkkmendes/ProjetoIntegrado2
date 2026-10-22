from django.shortcuts import render

from django.shortcuts import render, redirect
from .models import PlanejamentoSalvo, SimulacaoSalva, NivelamentoSalvo
from .forms import PlanejamentoForm, SimulacaoForm, NivelamentoForm

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
    form = PlanejamentoForm()

    if request.method == 'POST':
        dados_form = request.POST.copy()
        dados_form['disciplinas'] = ', '.join(
            request.POST.getlist('disciplina')
        )

        form = PlanejamentoForm(dados_form)

        if form.is_valid():
            form.save()
            return redirect('planejamento')

    dados = PlanejamentoSalvo.objects.all()

    return render(request, 'planejamento (1).html', {
        'form': form,
        'dados': dados
    })



def simulador_banco(request):
    form = SimulacaoForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('simulacao')

    dados = SimulacaoSalva.objects.all()

    return render(request, 'Simulador (1).html', {
        'form': form,
        'dados': dados
    })



def nivelamento_banco(request):
    form = NivelamentoForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('nivelamento')

    dados = NivelamentoSalvo.objects.all()

    return render(request, 'nivelamento.html', {
        'form': form,
        'dados': dados
    })
