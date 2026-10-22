from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import CalendarioMatricula, Disciplina
from django.db.models import F, Q

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
    disciplinas = Disciplina.objects.all().order_by(
        F('periodo').asc(nulls_last=True),
        'nome'
    )

    return render(request, 'fluxograma.html', {
        'disciplinas': disciplinas
    })

def filtrar_disciplinas(request):
    busca = request.GET.get('q', '').strip()

    disciplinas = Disciplina.objects.all()

    if busca:
        disciplinas = disciplinas.filter(
            Q(nome__icontains=busca) |
            Q(codigo__icontains=busca)
        )

    disciplinas = disciplinas.order_by(
        F('periodo').asc(nulls_last=True),
        'nome'
    )

    return render(request, 'fluxograma.html', {
        'disciplinas': disciplinas
    })

def detalhes_disciplina(request, codigo):
    disciplina = get_object_or_404(
        Disciplina,
        codigo=codigo
    )

    dados = {
        'codigo': disciplina.codigo,
        'nome': disciplina.nome,
        'periodo': disciplina.periodo,
        'creditos': disciplina.creditos,
        'pre_requisitos': [
            d.codigo for d in disciplina.pre_requisitos.all()
        ],
        'co_requisitos': [
            d.codigo for d in disciplina.co_requisitos.all()
        ],
        'creditos_minimos': disciplina.creditos_minimos
    }

    return JsonResponse(dados)
