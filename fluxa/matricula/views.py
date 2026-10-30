from django.shortcuts import render, redirect, resolve_url
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetConfirmView
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from .models import CalendarioMatricula, Disciplina
from .forms import LoginForm, CadastroForm, RecuperarSenhaForm, PerfilNomeForm, TrocarSenhaForm

from .models import PlanejamentoSalvo, SimulacaoSalva, NivelamentoSalvo
from .forms import PlanejamentoForm, SimulacaoForm, NivelamentoForm

from django.db.models import F, Q

def inicio(request):
    return render(request, 'index.html')

@login_required
def telaInicio(request):
    calendario = CalendarioMatricula.objects.first()

    return render(request, 'inicio_html.html', {
        'calendario': calendario
    })

def destino_seguro(request):
    proximo = request.POST.get('next') or request.GET.get('next') or ''
    if proximo and url_has_allowed_host_and_scheme(
        proximo,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return proximo
    return resolve_url('telaInicio')

def login(request):
    destino = destino_seguro(request)

    if request.user.is_authenticated:
        return redirect(destino)

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            auth_login(request, form.usuario)
            return redirect(destino)
    else:
        form = LoginForm()

    return render(request, 'login.html', {
        'form': form,
        'next': request.POST.get('next') or request.GET.get('next') or '',
    })

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
                use_https=request.is_secure(),
                extra_email_context={'site_name': 'Fluxa'},
            )
            messages.success(
                request,
                'Se o e-mail estiver cadastrado, enviamos um link para redefinir a senha.'
            )
            return redirect('login')
    else:
        form = RecuperarSenhaForm()

    return render(request, 'recuperar_senha.html', {'form': form})

class RedefinirSenhaView(SuccessMessageMixin, PasswordResetConfirmView):
    template_name = 'redefinir_senha.html'
    success_url = reverse_lazy('login')
    success_message = 'Senha alterada com sucesso. Entre com a nova senha.'

@require_POST
def logout_view(request):
    auth_logout(request)
    return redirect('login')


@login_required
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


@login_required
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


@login_required
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

def telaErro(request, titulo='Algo deu errado', mensagem='Não foi possível carregar esta página.', status=200):
    return render(request, 'erro.html', {
        'titulo': titulo,
        'mensagem': mensagem
    }, status=status)

def erro_404(request, exception):
    return telaErro(request, 'Página não encontrada', 'O endereço acessado não existe.', 404)

def erro_500(request):
    return telaErro(request, 'Algo deu errado', 'Ocorreu um erro no servidor. Tente novamente em alguns instantes.', 500)

@login_required
def perfil(request):
    form_nome = PerfilNomeForm(initial={'nome': request.user.get_full_name()})
    form_senha = TrocarSenhaForm(request.user)

    if request.method == 'POST':
        acao = request.POST.get('acao')

        if acao == 'nome':
            form_nome = PerfilNomeForm(request.POST)
            if form_nome.is_valid():
                form_nome.save(request.user)
                messages.success(request, 'Nome atualizado com sucesso.')
                return redirect('perfil')

        elif acao == 'senha':
            form_senha = TrocarSenhaForm(request.user, request.POST)
            if form_senha.is_valid():
                usuario = form_senha.save()
                update_session_auth_hash(request, usuario)
                messages.success(request, 'Senha alterada com sucesso.')
                return redirect('perfil')

    return render(request, 'perfil.html', {
        'form_nome': form_nome,
        'form_senha': form_senha,
    })

@login_required
def fluxograma(request):
    disciplinas = Disciplina.objects.all().order_by(
        F('periodo').asc(nulls_last=True),
        'nome'
    )

    return render(request, 'fluxograma.html', {
        'disciplinas': disciplinas
    })

@login_required
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

@login_required
def detalhes_disciplina(request, codigo):
    try:
        disciplina = Disciplina.objects.get(codigo=codigo)
    except Disciplina.DoesNotExist:
        return telaErro(request, 'Disciplina não encontrada', f'Não existe disciplina com o código {codigo}.', 404)

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