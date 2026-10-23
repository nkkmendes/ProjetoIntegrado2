from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.views.decorators.http import require_POST
from .models import CalendarioMatricula, Disciplina
from .forms import LoginForm, CadastroForm, RecuperarSenhaForm

from .models import PlanejamentoSalvo, SimulacaoSalva, NivelamentoSalvo
from .forms import PlanejamentoForm, SimulacaoForm, NivelamentoForm

from django.db.models import F, Q

def inicio(request):
    return render(request, 'index.html')

def telaInicio(request):
    calendario = CalendarioMatricula.objects.first()

    return render(request, 'inicio_html.html', {
        'calendario': calendario
    })

def login(request):
    if request.user.is_authenticated:
        return redirect('telaInicio')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            auth_login(request, form.usuario)
            return redirect('telaInicio')
    else:
        form = LoginForm()

    return render(request, 'login.html', {'form': form})

def criarConta(request):
    if request.method == 'POST':
        form = CadastroForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            auth_login(request, usuario)
            return redirect('telaInicio')
    else:
        form = CadastroForm()

    return render(request, 'criarConta.html', {'form': form})

def recuperar_senha(request):
    if request.method == 'POST':
        form = RecuperarSenhaForm(request.POST)
        if form.is_valid():
            form.save(request=request, use_https=request.is_secure())
            messages.success(
                request,
                'Se o e-mail estiver cadastrado, enviamos um link para redefinir a senha.'
            )
            return redirect('login')
    else:
        form = RecuperarSenhaForm()

    return render(request, 'recuperar_senha.html', {'form': form})

@require_POST
def logout_view(request):
    auth_logout(request)
    return redirect('login')

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
