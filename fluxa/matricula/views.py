from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.views.decorators.http import require_POST
from .models import CalendarioMatricula, Disciplina
from .forms import LoginForm, CadastroForm, RecuperarSenhaForm
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
    form = PlanejamentoForm(request.POST or None)

    if request.method == 'POST':
        dados = request.POST.copy()
        dados['disciplinas'] = ', '.join(
            request.POST.getlist('disciplina')
        )
        form = PlanejamentoForm(dados)

        if form.is_valid():
            form.save()
            return redirect('planejamento')

    registros = PlanejamentoSalvo.objects.all()

    return render(request, 'planejamento (1).html', {
        'form': form,
        'dados': registros
    })


def simulacao(request):
    form = SimulacaoForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('simulacao')

    registros = SimulacaoSalva.objects.all()

    return render(request, 'Simulador (1).html', {
        'form': form,
        'dados': registros
    })


def nivelamento(request):
    form = NivelamentoForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('nivelamento')

    registros = NivelamentoSalvo.objects.all()

    return render(request, 'nivelamento.html', {
        'form': form,
        'dados': registros
    })


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
