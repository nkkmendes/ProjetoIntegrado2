import unicodedata
from urllib.parse import urlencode

from django.shortcuts import render, redirect, resolve_url
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetConfirmView
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from .models import CalendarioMatricula, Disciplina, Curso, PerfilAluno, DisciplinaCursada
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
    perfil_aluno, _ = PerfilAluno.objects.get_or_create(
        user=request.user,
        defaults={'curso': Curso.objects.first()},
    )

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
        'perfil_aluno': perfil_aluno,
    })

def ordenar_por_camada(disciplinas):
    """Calcula a "camada" de cada matéria (0 = sem pré-requisito; senão 1 + a
    maior camada entre as matérias que ela exige) e devolve a lista ordenada
    por camada e código. É uma organização provisória: nenhuma matéria tem
    período ideal."""
    todas = list(disciplinas)
    exigidas = {d.codigo: set() for d in todas}
    for d in todas:
        for grupo in d.grupos_pre_requisito.all():
            for item in grupo.disciplinas.all():
                exigidas[d.codigo].add(item.codigo)

    camadas = {}

    def camada_de(codigo, visitando=()):
        if codigo in camadas:
            return camadas[codigo]
        if codigo in visitando or codigo not in exigidas:
            return 0
        pais = [camada_de(c, visitando + (codigo,)) for c in exigidas[codigo]]
        camadas[codigo] = 1 + max(pais) if pais else 0
        return camadas[codigo]

    for d in todas:
        d.camada = camada_de(d.codigo)

    return sorted(todas, key=lambda d: (d.camada, d.codigo))

CARTA_L = 210
CARTA_A = 74
ESPACO_H = 90
ESPACO_V = 18
MARGEM_X = 24
TOPO = 44

COR_PADRAO = '#6b86a8'
COR_CO = '#7c3aed'
PALETA = ['#2563eb', '#059669', '#d97706', '#db2777', '#0891b2']


def _normalizar(texto):
    sem_acento = unicodedata.normalize('NFD', texto)
    sem_acento = ''.join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.lower().strip()


def _url_fluxograma(foco=None, ancora=None):
    url = reverse('fluxograma')
    if foco:
        url += '?' + urlencode({'foco': foco})
    if ancora:
        url += '#c-' + ancora
    return url


def _cor_do_grupo(indice, total):
    return PALETA[indice % len(PALETA)] if total > 1 else COR_PADRAO


def _cadeia(codigo, grupos, concluidas):
    """Todos os pré-requisitos (de todos os grupos), até o começo ou até
    uma matéria concluída."""
    achados = set()
    fila = [codigo]
    while fila:
        atual = fila.pop()
        for membros in grupos.get(atual, []):
            for c in membros:
                if c not in concluidas and c not in achados:
                    achados.add(c)
                    fila.append(c)
    return achados


def _desenhar_setas(foco, cadeia, co_foco, info):
    """Monta as setas (SVG) só da matéria selecionada."""
    def caixa(c):
        d = info[c]['obj']
        return d.x, d.x + CARTA_L, d.y + CARTA_A // 2

    setas = []
    cores = set()

    for codigo in [foco] + sorted(cadeia):
        dados = info[codigo]
        if dados['concluida']:
            continue
        grupos_vivos = []
        for indice, membros in enumerate(dados['grupos']):
            vivos = [m for m in membros if m in info and not info[m]['concluida']]
            if vivos:
                grupos_vivos.append((indice, vivos))

        esq, _, meio = caixa(codigo)
        for pos, (indice, vivos) in enumerate(grupos_vivos):
            cor = _cor_do_grupo(indice, len(dados['grupos']))
            cores.add(cor)
            jx = esq - 22
            jy = meio + int(round((pos - (len(grupos_vivos) - 1) / 2) * 12))

            for m in vivos:
                _, dir_m, meio_m = caixa(m)
                folga = max(30, (jx - dir_m) // 2)
                setas.append({
                    'tipo': 'linha', 'classe': 'pre',
                    'd': f'M{dir_m},{meio_m} C{dir_m + folga},{meio_m} {jx - folga},{jy} {jx},{jy}',
                    'cor': cor, 'marcador': '',
                })
            setas.append({
                'tipo': 'linha', 'classe': 'pre',
                'd': f'M{jx},{jy} L{esq - 2},{meio}',
                'cor': cor, 'marcador': 'seta-' + cor.lstrip('#'),
            })
            setas.append({'tipo': 'ponto', 'cx': str(jx), 'cy': str(jy), 'cor': cor})

    for c in sorted(co_foco):
        a_esq, a_dir, a_meio = caixa(foco)
        b_esq, b_dir, b_meio = caixa(c)
        if a_esq == b_esq:
            x = a_dir + 6
            d = (f'M{a_dir},{a_meio} C{x + 34},{a_meio} {x + 34},{b_meio} {b_dir},{b_meio}')
        else:
            if a_esq < b_esq:
                ini_dir, ini_meio, fim_esq, fim_meio = a_dir, a_meio, b_esq, b_meio
            else:
                ini_dir, ini_meio, fim_esq, fim_meio = b_dir, b_meio, a_esq, a_meio
            f = max(30, (fim_esq - ini_dir) // 2)
            d = (f'M{ini_dir},{ini_meio} C{ini_dir + f},{ini_meio} '
                 f'{fim_esq - f},{fim_meio} {fim_esq},{fim_meio}')
        setas.append({'tipo': 'linha', 'classe': 'co', 'd': d, 'cor': COR_CO, 'marcador': ''})

    marcadores = [{'id': 'seta-' + c.lstrip('#'), 'cor': c} for c in sorted(cores)]
    return setas, marcadores


@login_required
def fluxograma(request):
    disciplinas = Disciplina.objects.prefetch_related(
        'grupos_pre_requisito__disciplinas',
        'co_requisitos',
        'associadas',
    )
    lista = ordenar_por_camada(disciplinas)

    concluidas = set(
        DisciplinaCursada.objects.filter(
            user=request.user, status=DisciplinaCursada.CONCLUIDA
        ).values_list('disciplina__codigo', flat=True)
    )

    info = {}
    usadas = set()
    for d in lista:
        grupos = [
            sorted(i.codigo for i in grupo.disciplinas.all())
            for grupo in d.grupos_pre_requisito.all()
        ]
        for membros in grupos:
            usadas.update(membros)
        co = sorted(
            {i.codigo for i in d.co_requisitos.all()} |
            {i.codigo for i in d.associadas.all()}
        )
        info[d.codigo] = {'obj': d, 'grupos': grupos, 'co': co}

    dependentes = {c: set() for c in info}
    for codigo, dados in info.items():
        for membros in dados['grupos']:
            for m in membros:
                dependentes.setdefault(m, set()).add(codigo)

    for codigo, dados in info.items():
        d = dados['obj']
        d.isolada = not dados['grupos'] and not dados['co'] and codigo not in usadas
        d.concluida = codigo in concluidas
        d.classe = ''
        dados['concluida'] = d.concluida

    foco = request.GET.get('foco', '').strip().upper()
    if foco not in info or info[foco]['concluida']:
        foco = ''

    busca = request.GET.get('q', '').strip()
    aviso = ''
    resultados = []
    if busca:
        termo = _normalizar(busca)
        achadas = [
            d for d in lista
            if termo in _normalizar(d.codigo) or termo in _normalizar(d.nome)
        ]
        if not achadas:
            aviso = f'Nenhuma matéria encontrada para "{busca}".'
        elif len(achadas) == 1:
            d = achadas[0]
            if d.concluida:
                aviso = (f'{d.codigo} — {d.nome} já está concluída. '
                         'Veja a lista "Concluídas" para desfazer.')
            else:
                return redirect(_url_fluxograma(d.codigo, d.codigo))
        else:
            aviso = f'{len(achadas)} matérias encontradas. Escolha uma:'
            resultados = achadas

    colunas = {}
    for d in lista:
        if not d.isolada and not d.concluida:
            colunas.setdefault(d.camada, []).append(d)
    camadas = sorted(colunas)

    cabecalhos = []
    for i, camada in enumerate(camadas):
        x = MARGEM_X + i * (CARTA_L + ESPACO_H)
        cabecalhos.append({
            'x': x,
            'titulo': 'Sem pré-requisito' if camada == 0 else f'Nível {camada}',
        })
        for j, d in enumerate(colunas[camada]):
            d.x = x
            d.y = TOPO + j * (CARTA_A + ESPACO_V)

    largura = altura = 0
    if camadas:
        largura = 2 * MARGEM_X + len(camadas) * CARTA_L + (len(camadas) - 1) * ESPACO_H
        altura = TOPO + max(len(v) for v in colunas.values()) * (CARTA_A + ESPACO_V)

    painel = None
    setas, marcadores = [], []
    grupos_por_codigo = {c: dados['grupos'] for c, dados in info.items()}
    if foco:
        cadeia = _cadeia(foco, grupos_por_codigo, concluidas)
        co_foco = {c for c in info[foco]['co'] if c not in concluidas and c not in cadeia}

        info[foco]['obj'].classe = 'alvo'
        for c in cadeia:
            info[c]['obj'].classe = 'cadeia'
        for c in co_foco:
            info[c]['obj'].classe = 'co'

        if not info[foco]['obj'].isolada:
            setas, marcadores = _desenhar_setas(foco, cadeia, co_foco, info)

        def itens(codigos):
            return [{'codigo': c, 'concluida': info[c]['concluida']} for c in sorted(codigos)]

        total_grupos = len(info[foco]['grupos'])
        d = info[foco]['obj']
        painel = {
            'codigo': d.codigo,
            'nome': d.nome,
            'creditos': d.creditos,
            'creditos_minimos': d.creditos_minimos,
            'grupos': [
                {'cor': _cor_do_grupo(i, total_grupos), 'itens': itens(membros)}
                for i, membros in enumerate(info[foco]['grupos'])
            ],
            'co': itens(info[foco]['co']),
            'dependentes': itens(dependentes.get(foco, [])),
            'sem_relacoes': d.isolada,
        }

    feitas = [info[c]['obj'] for c in sorted(concluidas) if c in info]

    return render(request, 'fluxograma.html', {
        'cabecalhos': cabecalhos,
        'cartas': [d for d in lista if not d.isolada and not d.concluida],
        'isoladas': [d for d in lista if d.isolada and not d.concluida],
        'largura': largura,
        'altura': altura,
        'setas': setas,
        'marcadores': marcadores,
        'painel': painel,
        'foco': foco,
        'busca': busca,
        'aviso': aviso,
        'resultados': resultados,
        'concluidas': feitas,
    })

@login_required
def filtrar_disciplinas(request):
    return redirect('fluxograma')

def _buscar_disciplina(codigo):
    try:
        return Disciplina.objects.get(codigo__iexact=codigo)
    except Disciplina.DoesNotExist:
        return None

@login_required
def detalhes_disciplina(request, codigo):
    disciplina = _buscar_disciplina(codigo)
    if disciplina is None:
        return JsonResponse({'erro': f'Não existe disciplina com o código {codigo}.'}, status=404)

    grupos = [
        sorted(d.codigo for d in grupo.disciplinas.all())
        for grupo in disciplina.grupos_pre_requisito.prefetch_related('disciplinas')
    ]

    dados = {
        'codigo': disciplina.codigo,
        'nome': disciplina.nome,
        'creditos': disciplina.creditos,
        'pre_requisitos': [
            d.codigo for d in disciplina.pre_requisitos.all()
        ],
        'grupos_pre_requisitos': grupos,
        'co_requisitos': sorted(
            {d.codigo for d in disciplina.co_requisitos.all()} |
            {d.codigo for d in disciplina.associadas.all()}
        ),
        'dependentes': [d.codigo for d in disciplina.dependentes.all()],
        'creditos_minimos': disciplina.creditos_minimos,
        'concluida': DisciplinaCursada.objects.filter(
            user=request.user,
            disciplina=disciplina,
            status=DisciplinaCursada.CONCLUIDA,
        ).exists(),
    }

    return JsonResponse(dados)

@login_required
@require_POST
def marcar_concluida(request, codigo):
    disciplina = _buscar_disciplina(codigo)
    if disciplina is None:
        messages.error(request, f'Não existe disciplina com o código {codigo}.')
        return redirect('fluxograma')

    foco = request.POST.get('foco', '').strip().upper()

    if request.POST.get('acao') == 'concluir':
        DisciplinaCursada.objects.update_or_create(
            user=request.user,
            disciplina=disciplina,
            defaults={'status': DisciplinaCursada.CONCLUIDA},
        )
        messages.success(request, f'{disciplina.codigo} marcada como concluída.')
        if foco == disciplina.codigo:
            foco = ''
        return redirect(_url_fluxograma(foco))

    DisciplinaCursada.objects.filter(user=request.user, disciplina=disciplina).delete()
    messages.success(request, f'{disciplina.codigo} voltou para o fluxograma.')
    return redirect(_url_fluxograma(foco, disciplina.codigo))