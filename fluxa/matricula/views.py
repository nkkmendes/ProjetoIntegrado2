import unicodedata
import os
import tempfile
from pathlib import Path
from urllib.parse import urlencode

from .ocr_sau import analisar_pdf

from django.db import transaction
from django.shortcuts import render, redirect, resolve_url, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetConfirmView
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from .models import (
    CalendarioMatricula, Disciplina, HistoricoDisciplina, PlanejamentoSalvo,
)
from .forms import (
    LoginForm, CadastroForm, RecuperarSenhaForm, PerfilNomeForm, TrocarSenhaForm,
    PerfilCursoForm, HistoricoForm, NivelamentoAlunoForm,
)
from .servicos import (
    obter_perfil, resumo_creditos, avisos_de_nivel, quadro_de_nivelamento,
    periodo_de_oferta, disciplinas_disponiveis, dados_do_simulador,
    validar_selecao, resumo_da_grade,
)

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


def _pk(valor):
    """Converte um id vindo do navegador em inteiro (0 se não for válido)."""
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


def _nota_das_ocultas(ocultas, periodo):
    """Texto do rodapé da lista lateral do Simulador."""
    partes = []
    if ocultas['pre_requisito']:
        partes.append(f"{ocultas['pre_requisito']} com pré-requisito pendente")
    if ocultas['nivelamento']:
        n = ocultas['nivelamento']
        partes.append(f"{n} bloqueada{'s' if n != 1 else ''} pelo nível de nivelamento")
    if ocultas['co_requisito']:
        partes.append(f"{ocultas['co_requisito']} com co-requisito que não pode ser cursado agora")
    if ocultas['sem_turma']:
        partes.append(f"{ocultas['sem_turma']} sem turma em {periodo}")
    total = sum(ocultas.values())
    if not total:
        return ''
    inicio = (
        f'{total} disciplinas do seu curso não aparecem aqui'
        if total != 1 else '1 disciplina do seu curso não aparece aqui'
    )
    return inicio + ': ' + ', '.join(partes) + '.'


@login_required
def planejamento(request):
    """Grades salvas do aluno. Só guarda, nomeia e reabre: quem monta a grade
    é o Simulador. Cada aluno só enxerga e altera as próprias grades."""
    perfil = obter_perfil(request.user)

    if request.method == 'POST':
        plano = get_object_or_404(
            PlanejamentoSalvo,
            pk=_pk(request.POST.get('planejamento_id')),
            usuario=request.user,
        )
        acao = request.POST.get('acao')
        if acao == 'excluir':
            nome = plano.nome
            plano.delete()
            messages.success(request, f'Grade “{nome}” excluída.')
        elif acao == 'renomear':
            novo_nome = request.POST.get('nome', '').strip()[:100]
            if not novo_nome:
                messages.error(request, 'O nome da grade não pode ficar vazio.')
            elif request.user.planejamentos.filter(nome=novo_nome).exclude(pk=plano.pk).exists():
                messages.error(request, 'Você já tem uma grade com esse nome.')
            else:
                plano.nome = novo_nome
                plano.save()
                messages.success(request, 'Nome da grade atualizado.')
        return redirect('planejamento')

    planos = (
        request.user.planejamentos
        .prefetch_related('turmas__disciplina', 'turmas__horarios')
    )
    grades = [
        {'plano': plano, **resumo_da_grade(plano.turmas.all())}
        for plano in planos
    ]
    return render(request, 'planejamento.html', {
        'grades': grades,
        'curso': perfil.curso,
    })


@login_required
def simulacao(request):
    """Simulador de matrícula: o aluno escolhe turmas reais do micro-horário
    entre as disciplinas que o histórico dele permite cursar. O servidor
    confere tudo de novo ao salvar (disponibilidade, uma turma por disciplina
    e conflito de horário)."""
    perfil = obter_perfil(request.user)
    periodo = periodo_de_oferta()

    postando = request.method == 'POST'
    id_plano = _pk(request.POST.get('planejamento_id') if postando else request.GET.get('planejamento'))
    plano = None
    if id_plano:
        plano = get_object_or_404(PlanejamentoSalvo, pk=id_plano, usuario=request.user)

    erro = ''
    nome = plano.nome if plano else ''
    selecionadas = []

    if postando and request.POST.get('acao') == 'salvar':
        nome = request.POST.get('nome', '').strip()[:100]
        ids = request.POST.getlist('turmas')
        turmas, erro = validar_selecao(perfil, periodo, ids)
        if not erro and not nome:
            erro = 'Dê um nome à grade para salvá-la em Planejamento.'
        if not erro:
            repetido = request.user.planejamentos.filter(nome=nome)
            if plano:
                repetido = repetido.exclude(pk=plano.pk)
            if repetido.exists():
                erro = 'Você já tem uma grade com esse nome.'
        if not erro:
            with transaction.atomic():
                if plano is None:
                    plano = PlanejamentoSalvo(usuario=request.user)
                plano.nome = nome
                plano.periodo_letivo = periodo
                plano.save()
                plano.turmas.set(turmas)
            messages.success(request, f'Grade “{nome}” salva em Planejamento.')
            return redirect(f"{reverse('simulacao')}?planejamento={plano.pk}")
        selecionadas = [_pk(i) for i in ids]
    elif plano:
        selecionadas = list(plano.turmas.values_list('pk', flat=True))

    disponiveis = disciplinas_disponiveis(perfil, periodo)
    ids_disponiveis = {t.pk for d in disponiveis['disciplinas'] for t in d.turmas_periodo}
    mantidas = [i for i in selecionadas if i in ids_disponiveis]
    if plano and not postando and len(mantidas) != len(selecionadas):
        messages.warning(
            request,
            f'{len(selecionadas) - len(mantidas)} turma(s) desta grade não estão mais '
            'disponíveis para você (por exemplo, a disciplina já foi concluída) e foram retiradas.'
        )

    return render(request, 'simulador.html', {
        'curso': perfil.curso,
        'periodo': periodo,
        'plano': plano,
        'nome': nome,
        'erro': erro,
        'dados_simulador': dados_do_simulador(disponiveis['disciplinas']),
        'selecao_inicial': mantidas,
        'nota_ocultas': _nota_das_ocultas(disponiveis['ocultas'], periodo),
    })


def _caminho_pdf_sau(user):
    return Path.home() / '.fluxa' / 'sau' / f'usuario_{user.pk}.pdf'


def _apagar_pdf_sau(user):
    """Remove o PDF do SAU do aluno (se existir). Os dados pessoais do PDF
    não ficam guardados depois da análise."""
    try:
        _caminho_pdf_sau(user).unlink(missing_ok=True)
    except OSError:
        pass


@login_required
def historico(request):
    """Tela única do aluno: disciplinas já cursadas (com notas), contagem de
    créditos e nivelamento. Une as antigas telas de Nivelamento, Consulta de
    Graus e Contagem de Créditos."""
    perfil = obter_perfil(request.user)

    editar = request.GET.get('editar', '').strip().upper()
    registro_editado = None
    if editar:
        registro_editado = perfil.historico.filter(
            disciplina__codigo=editar
        ).select_related('disciplina').first()

    form = HistoricoForm(instance=registro_editado) if registro_editado else HistoricoForm()
    form_nivel = NivelamentoAlunoForm()

    if request.method == 'POST':
        acao = request.POST.get('acao')

        if acao == 'enviar_pdf_sau':
            pdf = request.FILES.get('pdf_sau')
            limite_bytes = 10 * 1024 * 1024

            if pdf is None:
                messages.error(request, 'Selecione um arquivo PDF para enviar.')
            elif not pdf.name.lower().endswith('.pdf'):
                messages.error(request, 'O arquivo precisa ter a extensão .pdf.')
            elif pdf.size == 0 or pdf.size > limite_bytes:
                messages.error(request, 'O PDF precisa ter entre 1 byte e 10 MB.')
            else:
                cabecalho = pdf.read(5)
                pdf.seek(0)
                if cabecalho != b'%PDF-':
                    messages.error(request, 'O arquivo selecionado não parece ser um PDF válido.')
                else:
                    # Salva fora do repositório e fora da pasta static/media pública.
                    pasta = Path.home() / '.fluxa' / 'sau'
                    temporario = None
                    try:
                        pasta.mkdir(parents=True, exist_ok=True)
                        with tempfile.NamedTemporaryFile(
                            mode='wb', prefix='sau_', suffix='.tmp',
                            dir=pasta, delete=False
                        ) as destino:
                            temporario = Path(destino.name)
                            for bloco in pdf.chunks():
                                destino.write(bloco)
                        arquivo_final = _caminho_pdf_sau(request.user)
                        os.replace(temporario, arquivo_final)
                        request.session.pop('sau_registros_ocr', None)
                        messages.success(request, 'PDF do SAU enviado com sucesso!')
                    except OSError:
                        messages.error(request, 'Não foi possível salvar o PDF. Tente novamente.')
                    finally:
                        if temporario is not None:
                            temporario.unlink(missing_ok=True)
            return redirect(reverse('historico') + '#pdf-sau')

        if acao == 'analisar_pdf_sau':
            caminho = _caminho_pdf_sau(request.user)
            if not caminho.is_file():
                messages.error(request, 'Envie o PDF do SAU antes de analisar.')
            else:
                try:
                    analise = analisar_pdf(caminho)
                except (ValueError, OSError) as exc:
                    request.session.pop('sau_registros_ocr', None)
                    messages.error(request, f'Não foi possível analisar o PDF: {exc}')
                else:
                    request.session['sau_registros_ocr'] = analise['registros']
                    request.session['sau_ocr_usuario'] = request.user.pk
                    request.session['sau_ocr_usado'] = analise['usou_ocr']
                    if analise['registros']:
                        messages.success(
                            request,
                            f"{len(analise['registros'])} disciplina(s) identificada(s) no PDF. "
                            'Confira os dados antes de importar.'
                        )
                    else:
                        messages.warning(
                            request,
                            'Nenhuma disciplina foi reconhecida. Confira se o PDF é o '
                            '"Espelho do Histórico" do SAU.'
                        )
                    if analise['nao_cadastradas']:
                        messages.warning(
                            request,
                            f"{analise['nao_cadastradas']} disciplina(s) não cadastrada(s) "
                            'no Fluxa aparecem para conferência, mas não podem ser importadas.'
                        )
                    if analise['ignoradas']:
                        messages.info(
                            request,
                            f"{len(analise['ignoradas'])} linha(s) de cancelamento, trancamento "
                            'ou incompleto foram ignoradas, pois a disciplina não foi cursada.'
                        )
                    if analise['nao_lidas']:
                        messages.warning(
                            request,
                            'Não consegui ler estas disciplinas do PDF: '
                            + ', '.join(analise['nao_lidas']) + '.'
                        )
                finally:
                    # Privacidade: o PDF só existe até ser lido.
                    _apagar_pdf_sau(request.user)
            return redirect(reverse('historico') + '#pdf-sau')

        if acao == 'descartar_sau':
            _apagar_pdf_sau(request.user)
            for chave in ('sau_registros_ocr', 'sau_ocr_usuario', 'sau_ocr_usado'):
                request.session.pop(chave, None)
            messages.success(request, 'PDF e dados lidos descartados.')
            return redirect(reverse('historico') + '#pdf-sau')

        if acao == 'confirmar_ocr_sau':
            opcoes = request.session.get('sau_registros_ocr', [])
            if request.session.get('sau_ocr_usuario') != request.user.pk or not opcoes:
                messages.error(request, 'Analise novamente o PDF antes de confirmar.')
            else:
                indices = set(request.POST.getlist('selecionados'))
                selecionados = []
                sem_escolha = 0
                for i, item in enumerate(opcoes):
                    if str(i) not in indices or not item.get('cadastrada', True):
                        continue
                    status = item['status']
                    if item.get('escolher'):
                        status = request.POST.get(f'status_{i}', '')
                        if status not in (HistoricoDisciplina.CONCLUIDA, HistoricoDisciplina.EM_CURSO):
                            sem_escolha += 1
                            continue
                    selecionados.append((item, status))
                disciplinas = Disciplina.objects.in_bulk(
                    [item['codigo'] for item, _ in selecionados], field_name='codigo'
                )
                alterados = 0
                for item, status in selecionados:
                    disciplina = disciplinas.get(item['codigo'])
                    if not disciplina:
                        continue
                    dados = {
                        'status': status,
                        'periodo_letivo': item['periodo'],
                        'turma': item.get('turma', ''),
                    }
                    if item['media'] is not None:
                        dados['media'] = item['media']
                    HistoricoDisciplina.objects.update_or_create(
                        perfil=perfil, disciplina=disciplina, defaults=dados
                    )
                    alterados += 1
                for chave in ('sau_registros_ocr', 'sau_ocr_usuario', 'sau_ocr_usado'):
                    request.session.pop(chave, None)
                messages.success(request, f'{alterados} disciplina(s) confirmada(s) no histórico.')
                if sem_escolha:
                    messages.warning(
                        request,
                        f'{sem_escolha} disciplina(s) com grau não informado ficaram de fora '
                        'porque você não escolheu entre concluída e em curso.'
                    )
            return redirect(reverse('historico') + '#cursadas')

        if acao == 'historico':
            form = HistoricoForm(request.POST)
            if form.is_valid():
                registro = form.save(perfil)
                messages.success(request, f'{registro.disciplina.codigo} salva no histórico.')
                return redirect('historico')

        elif acao == 'nivel':
            form_nivel = NivelamentoAlunoForm(request.POST)
            if form_nivel.is_valid():
                registro = form_nivel.save(perfil)
                messages.success(
                    request, f'Nível de {registro.area.nome} salvo: {registro.nivel}.'
                )
                return redirect(reverse('historico') + '#nivelamento')

    registros = perfil.historico.select_related('disciplina').order_by(
        '-periodo_letivo', 'disciplina__codigo'
    )

    return render(request, 'historico.html', {
        'perfil': perfil,
        'form': form,
        'editando': registro_editado,
        'form_nivel': form_nivel,
        'registros': registros,
        'resumo': resumo_creditos(perfil),
        'quadro_nivel': quadro_de_nivelamento(perfil),
        'sau_pdf_existe': _caminho_pdf_sau(request.user).is_file(),
        'sau_ocr_registros': request.session.get('sau_registros_ocr', [])
            if request.session.get('sau_ocr_usuario') == request.user.pk else [],
        'sau_ocr_usado': request.session.get('sau_ocr_usado', False),
    })


@login_required
@require_POST
def historico_remover(request, codigo):
    perfil = obter_perfil(request.user)
    apagados, _ = perfil.historico.filter(disciplina__codigo__iexact=codigo).delete()
    if apagados:
        messages.success(request, f'{codigo.upper()} removida do histórico.')
    else:
        messages.error(request, f'{codigo.upper()} não estava no seu histórico.')
    return redirect('historico')


@login_required
@require_POST
def nivelamento_remover(request, area_id):
    perfil = obter_perfil(request.user)
    registro = perfil.niveis.filter(area_id=area_id).select_related('area').first()
    if registro:
        nome = registro.area.nome
        registro.delete()
        messages.success(request, f'Nível de {nome} removido (agora: não informado).')
    return redirect(reverse('historico') + '#nivelamento')


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
    perfil_aluno = obter_perfil(request.user)
    form_nome = PerfilNomeForm(initial={'nome': request.user.get_full_name()})
    form_senha = TrocarSenhaForm(request.user)
    form_curso = PerfilCursoForm(instance=perfil_aluno)

    if request.method == 'POST':
        acao = request.POST.get('acao')

        if acao == 'nome':
            form_nome = PerfilNomeForm(request.POST)
            if form_nome.is_valid():
                form_nome.save(request.user)
                messages.success(request, 'Nome atualizado com sucesso.')
                return redirect('perfil')

        elif acao == 'curso':
            form_curso = PerfilCursoForm(request.POST, instance=perfil_aluno)
            if form_curso.is_valid():
                form_curso.save()
                messages.success(request, 'Curso atualizado. O fluxograma já usa o novo curso.')
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
        'form_curso': form_curso,
        'perfil_aluno': perfil_aluno,
        'resumo': resumo_creditos(perfil_aluno),
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
                # só conta pré-requisito que também está no curso mostrado
                if item.codigo in exigidas:
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
    perfil = obter_perfil(request.user)
    curso = perfil.curso

    # Buscar as disciplinas do curso escolhido
    if curso is None:
        disciplinas = Disciplina.objects.none()
    else:
        disciplinas = curso.disciplinas.prefetch_related(
            'grupos_pre_requisito__disciplinas',
            'co_requisitos',
            'associadas',
        )

    # Uma só lógica para todos os cursos: as colunas vêm dos pré-requisitos
    # (globais) que estão no banco, sem períodos.
    lista = ordenar_por_camada(disciplinas)

    codigos_curso = {d.codigo for d in lista}

    # Consultar o histórico do aluno
    situacoes = dict(
        perfil.historico.values_list(
            'disciplina__codigo',
            'status'
        )
    )

    concluidas = {
        codigo
        for codigo, status in situacoes.items()
        if status == HistoricoDisciplina.CONCLUIDA
    }

    em_curso = {
        codigo
        for codigo, status in situacoes.items()
        if status == HistoricoDisciplina.EM_CURSO
    }

    avisos = avisos_de_nivel(perfil, lista)

    # Organizar pré-requisitos e co-requisitos
    info = {}
    usadas = set()

    for d in lista:

        grupos = []

        for grupo in d.grupos_pre_requisito.all():
            membros = sorted(
                item.codigo
                for item in grupo.disciplinas.all()
                if item.codigo in codigos_curso
            )

            if membros:
                grupos.append(membros)

        co = sorted(
            (
                {item.codigo for item in d.co_requisitos.all()}
                |
                {item.codigo for item in d.associadas.all()}
            ) & codigos_curso
        )

        for membros in grupos:
            usadas.update(membros)

        info[d.codigo] = {
            'obj': d,
            'grupos': grupos,
            'co': co,
        }

    # Descobrir quais matérias dependem de outras
    dependentes = {codigo: set() for codigo in info}

    for codigo, dados in info.items():
        for membros in dados['grupos']:
            for materia in membros:
                dependentes.setdefault(
                    materia, set()
                ).add(codigo)

    # Identificar matérias concluídas e bloqueadas
    for codigo, dados in info.items():
        d = dados['obj']

        d.isolada = (
            not dados['grupos']
            and not dados['co']
            and codigo not in usadas
        )

        d.concluida = codigo in concluidas
        d.classe = ''
        d.avisos_nivel = avisos.get(codigo, [])

        d.bloqueada = any(
            aviso['bloqueia']
            for aviso in d.avisos_nivel
        )

        dados['concluida'] = d.concluida

    # Selecionar uma matéria no fluxograma
    foco = request.GET.get(
        'foco', ''
    ).strip().upper()

    if foco not in info or info[foco]['concluida']:
        foco = ''

    # Buscar disciplina pelo código ou nome
    busca = request.GET.get('q', '').strip()
    aviso = ''
    resultados = []

    if busca:
        termo = _normalizar(busca)

        achadas = [
            d for d in lista
            if termo in _normalizar(d.codigo)
            or termo in _normalizar(d.nome)
        ]

        if not achadas:
            aviso = (
                f'Nenhuma matéria encontrada para "{busca}".'
            )

        elif len(achadas) == 1:
            d = achadas[0]

            if d.concluida:
                aviso = (
                    f'{d.codigo} — {d.nome} já está concluída. '
                    'Veja a lista "Concluídas" para desfazer.'
                )
            else:
                return redirect(
                    _url_fluxograma(d.codigo, d.codigo)
                )

        else:
            aviso = (
                f'{len(achadas)} matérias encontradas. '
                'Escolha uma:'
            )
            resultados = achadas

    # Organizar as matérias em colunas
    colunas = {}

    for d in lista:
        if not d.isolada and not d.concluida:
            colunas.setdefault(
                d.camada, []
            ).append(d)

    camadas = sorted(colunas)

    # Criar os cabeçalhos e posições das caixas
    cabecalhos = []

    for i, camada in enumerate(camadas):
        x = MARGEM_X + i * (CARTA_L + ESPACO_H)

        if camada == 0:
            titulo = 'Sem pré-requisito'
        else:
            titulo = f'Nível {camada}'

        cabecalhos.append({
            'x': x,
            'titulo': titulo,
        })

        for j, d in enumerate(colunas[camada]):
            d.x = x
            d.y = TOPO + j * (CARTA_A + ESPACO_V)

    # Calcular o tamanho da área do fluxograma
    largura = 0
    altura = 0

    if camadas:
        largura = (
            2 * MARGEM_X
            + len(camadas) * CARTA_L
            + (len(camadas) - 1) * ESPACO_H
        )

        altura = (
            TOPO
            + max(len(v) for v in colunas.values())
            * (CARTA_A + ESPACO_V)
        )

    # Preparar as setas e o painel lateral
    painel = None
    setas = []
    marcadores = []

    grupos_por_codigo = {
        codigo: dados['grupos']
        for codigo, dados in info.items()
    }

    if foco:
        cadeia = _cadeia(
            foco,
            grupos_por_codigo,
            concluidas
        )

        co_foco = {
            codigo
            for codigo in info[foco]['co']
            if codigo not in concluidas
            and codigo not in cadeia
        }

        info[foco]['obj'].classe = 'alvo'

        for codigo in cadeia:
            info[codigo]['obj'].classe = 'cadeia'

        for codigo in co_foco:
            info[codigo]['obj'].classe = 'co'

        if not info[foco]['obj'].isolada:
            setas, marcadores = _desenhar_setas(
                foco,
                cadeia,
                co_foco,
                info
            )

        def itens(codigos):
            return [
                {
                    'codigo': codigo,
                    'concluida': info[codigo]['concluida']
                }
                for codigo in sorted(codigos)
            ]

        total_grupos = len(info[foco]['grupos'])
        d = info[foco]['obj']

        painel = {
            'codigo': d.codigo,
            'nome': d.nome,
            'creditos': d.creditos,
            'creditos_minimos': d.creditos_minimos,
            'grupos': [
                {
                    'cor': _cor_do_grupo(i, total_grupos),
                    'itens': itens(membros)
                }
                for i, membros in enumerate(
                    info[foco]['grupos']
                )
            ],
            'co': itens(info[foco]['co']),
            'dependentes': itens(
                dependentes.get(foco, [])
            ),
            'sem_relacoes': d.isolada,
            'avisos_nivel': d.avisos_nivel,
            'em_curso': foco in em_curso,
        }

    # Matérias concluídas ficam separadas
    feitas = [
        info[codigo]['obj']
        for codigo in sorted(concluidas)
        if codigo in info
    ]

    cartas = [d for d in lista if not d.isolada and not d.concluida]
    isoladas = [d for d in lista if d.isolada and not d.concluida]
    # Quando a maior parte do curso não tem nenhum requisito no banco, o
    # desenho fica quase vazio: avisamos que é falta de dados, não ausência
    # de requisitos.
    requisitos_incompletos = bool(lista) and (
        sum(1 for d in lista if d.isolada) > len(lista) / 2
    )

    return render(request, 'fluxograma.html', {
        'curso': curso,
        'cabecalhos': cabecalhos,
        'cartas': cartas,
        'isoladas': isoladas,
        'requisitos_incompletos': requisitos_incompletos,
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
        'total_disciplinas': len(lista),
    })


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

    perfil = obter_perfil(request.user)
    grupos = [
        sorted(d.codigo for d in grupo.disciplinas.all())
        for grupo in disciplina.grupos_pre_requisito.prefetch_related('disciplinas')
    ]

    dados = {
        'codigo': disciplina.codigo,
        'nome': disciplina.nome,
        'creditos': disciplina.creditos,
        'cursos': [c.nome for c in disciplina.cursos.all()],
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
        'avisos_nivel': avisos_de_nivel(perfil, [disciplina]).get(disciplina.codigo, []),
        'concluida': perfil.historico.filter(
            disciplina=disciplina,
            status=HistoricoDisciplina.CONCLUIDA,
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

    perfil = obter_perfil(request.user)
    foco = request.POST.get('foco', '').strip().upper()

    if request.POST.get('acao') == 'concluir':
        # Só muda a situação: se o aluno já tinha notas dessa disciplina, elas ficam.
        HistoricoDisciplina.objects.update_or_create(
            perfil=perfil,
            disciplina=disciplina,
            defaults={'status': HistoricoDisciplina.CONCLUIDA},
        )
        messages.success(request, f'{disciplina.codigo} marcada como concluída.')
        if foco == disciplina.codigo:
            foco = ''
        return redirect(_url_fluxograma(foco))

    registro = perfil.historico.filter(disciplina=disciplina).first()
    if registro and registro.status == HistoricoDisciplina.CONCLUIDA:
        if registro.tem_notas:
            # Não apaga as notas que o aluno digitou no Histórico.
            registro.status = HistoricoDisciplina.EM_CURSO
            registro.save(update_fields=['status'])
            messages.success(
                request,
                f'{disciplina.codigo} voltou para o fluxograma '
                '(as notas continuam no seu Histórico, como "Em curso").'
            )
        else:
            registro.delete()
            messages.success(request, f'{disciplina.codigo} voltou para o fluxograma.')
    return redirect(_url_fluxograma(foco, disciplina.codigo))
