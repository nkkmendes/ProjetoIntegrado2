
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Sum, F, Q

from .models import (
    CalendarioMatricula,
    Disciplina,
    PlanejamentoSalvo,
    SimulacaoSalva,
    NivelamentoSalvo,
    CreditosAluno,
    GrauAluno
)

from .forms import (
    LoginForm,
    CadastroForm,
    RecuperarSenhaForm,
    PlanejamentoForm,
    SimulacaoForm,
    NivelamentoForm,
    CreditosAlunoForm,
    GrauAlunoForm
)


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
            form.save(
                request=request,
                use_https=request.is_secure()
            )

            messages.success(
                request,
                'Se o e-mail estiver cadastrado, enviamos um link para redefinir a senha.'
            )

            return redirect('login')
    else:
        form = RecuperarSenhaForm()

    return render(request, 'recuperar_senha.html', {
        'form': form
    })


@require_POST
def logout_view(request):
    auth_logout(request)
    return redirect('login')


@login_required(login_url='login')
def planejamento(request):
    form = PlanejamentoForm()

    if request.method == 'POST':
        dados = request.POST.copy()

        dados['disciplinas'] = ', '.join(
            request.POST.getlist('disciplina')
        )

        form = PlanejamentoForm(dados)

        if form.is_valid():
            planejamento_salvo = form.save(commit=False)

            planejamento_salvo.usuario = request.user
            planejamento_salvo.save()

            return redirect('planejamento')

    registros = PlanejamentoSalvo.objects.filter(
        usuario=request.user
    ).order_by('-id')

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


@login_required(login_url='login')
def contagem_creditos(request):
    form = CreditosAlunoForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        credito = form.save(commit=False)

        CreditosAluno.objects.update_or_create(
            aluno=request.user,
            disciplina=credito.disciplina,
            defaults={
                'concluida': credito.concluida
            }
        )

        return redirect('creditos')

    registros = CreditosAluno.objects.filter(
        aluno=request.user
    ).select_related('disciplina').order_by(
        'disciplina__nome'
    )

    total_cumprido = registros.filter(
        concluida=True
    ).aggregate(
        total=Sum('disciplina__creditos')
    )['total'] or 0

    total_curriculo = Disciplina.objects.aggregate(
        total=Sum('creditos')
    )['total'] or 0

    total_pendente = max(
        total_curriculo - total_cumprido, 0
    )

    return render(request, 'contagem-creditos.html', {
        'form': form,
        'registros': registros,
        'total_curriculo': total_curriculo,
        'total_cumprido': total_cumprido,
        'total_pendente': total_pendente
    })


@login_required(login_url='login')
def notas_periodo(request):
    form = GrauAlunoForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        grau = form.save(commit=False)
        grau.aluno = request.user

        existente = GrauAluno.objects.filter(
            aluno=request.user,
            disciplina=grau.disciplina,
            periodo_letivo=grau.periodo_letivo
        ).first()

        if existente:
            grau.pk = existente.pk

        grau.save()
        return redirect('notas_periodo')

    graus = GrauAluno.objects.filter(
        aluno=request.user
    ).select_related('disciplina').order_by(
        '-periodo_letivo',
        'disciplina__nome'
    )

    return render(request, 'notas-periodo.html', {
        'form': form,
        'graus': graus
    })


def telaErro(
    request,
    titulo='Algo deu errado',
    mensagem='Não foi possível carregar esta página.',
    status=200
):
    return render(request, 'erro.html', {
        'titulo': titulo,
        'mensagem': mensagem
    }, status=status)


def erro_404(request, exception):
    return telaErro(
        request,
        'Página não encontrada',
        'O endereço acessado não existe.',
        404
    )


def erro_500(request):
    return telaErro(
        request,
        'Algo deu errado',
        'Ocorreu um erro no servidor. Tente novamente em alguns instantes.',
        500
    )


def perfil(request):
    return render(request, 'perfil.html')


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
    try:
        disciplina = Disciplina.objects.get(codigo=codigo)

    except Disciplina.DoesNotExist:
        return telaErro(
            request,
            'Disciplina não encontrada',
            f'Não existe disciplina com o código {codigo}.',
            404
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
