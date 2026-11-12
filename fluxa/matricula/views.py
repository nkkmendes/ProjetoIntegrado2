import unicodedata
import fitz
import os
import tempfile
from pathlib import Path
from urllib.parse import urlencode

from .catalogos_fluxa import relacoes_do_curso
from .ocr_sau import analisar_pdf

from django.shortcuts import render, redirect, resolve_url, get_object_or_404
from django.db.models import Prefetch
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
    CalendarioMatricula, Disciplina, HistoricoDisciplina,
    PlanejamentoSalvo, SimulacaoSalva, Turma,
)
from .forms import (
    LoginForm, CadastroForm, RecuperarSenhaForm, PerfilNomeForm, TrocarSenhaForm,
    PerfilCursoForm, PlanejamentoForm, SimulacaoForm, HistoricoForm, NivelamentoAlunoForm,
)
from .servicos import (
    obter_perfil, resumo_creditos, avisos_de_nivel, quadro_de_nivelamento,
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


@login_required
def planejamento(request):
    perfil = obter_perfil(request.user)
    curso = perfil.curso
    periodo_oferta = '2026.2'

    disciplinas = []
    if curso:
        turmas_periodo = Turma.objects.filter(
            periodo_letivo=periodo_oferta
        ).order_by('codigo')
        disciplinas = list(
            curso.disciplinas.prefetch_related(
                Prefetch('turmas', queryset=turmas_periodo, to_attr='turmas_ofertadas')
            ).order_by('codigo')
        )

    codigos_validos = {disciplina.codigo for disciplina in disciplinas}
    registros = PlanejamentoSalvo.objects.filter(usuario=request.user).order_by('-id')

    # A edição utiliza a mesma página, sem precisar criar uma nova URL.
    id_edicao = request.POST.get('planejamento_id') if request.method == 'POST' else request.GET.get('editar')
    planejamento_editado = None
    if id_edicao:
        planejamento_editado = get_object_or_404(
            PlanejamentoSalvo, pk=id_edicao, usuario=request.user
        )

    if request.method == 'POST' and request.POST.get('acao') == 'excluir':
        if planejamento_editado is None:
            messages.error(request, 'Planejamento não encontrado.')
        else:
            planejamento_editado.delete()
            messages.success(request, 'Planejamento excluído com sucesso.')
        return redirect('planejamento')

    if request.method == 'POST':
        selecionadas = list(dict.fromkeys(request.POST.getlist('disciplina')))
        dados = request.POST.copy()
        dados['disciplinas'] = ', '.join(selecionadas)
        form = PlanejamentoForm(dados, instance=planejamento_editado)

        if not curso:
            form.add_error(None, 'Selecione seu curso no Perfil antes de salvar.')
        elif not selecionadas:
            form.add_error(None, 'Selecione pelo menos uma disciplina.')
        elif any(codigo not in codigos_validos for codigo in selecionadas):
            form.add_error(None, 'Uma ou mais disciplinas não pertencem ao seu curso.')

        if form.is_valid():
            registro = form.save(commit=False)
            registro.usuario = request.user
            registro.save()
            messages.success(
                request,
                'Planejamento atualizado com sucesso.' if planejamento_editado else 'Nova opção de grade salva com sucesso.'
            )
            return redirect('planejamento')
    else:
        if planejamento_editado:
            form = PlanejamentoForm(instance=planejamento_editado)
            selecionadas = [
                codigo.strip() for codigo in planejamento_editado.disciplinas.split(',')
                if codigo.strip()
            ]
        else:
            form = PlanejamentoForm()
            selecionadas = []

    codigos_selecionados = set(selecionadas)
    com_oferta = []
    sem_oferta = []
    for disciplina in disciplinas:
        disciplina.selecionada = disciplina.codigo in codigos_selecionados
        disciplina.quantidade_turmas = len(disciplina.turmas_ofertadas)
        if disciplina.quantidade_turmas:
            com_oferta.append(disciplina)
        else:
            sem_oferta.append(disciplina)

    return render(request, 'planejamento (1).html', {
        'form': form,
        'dados': registros,
        'curso': curso,
        'periodo_oferta': periodo_oferta,
        'disciplinas_com_oferta': com_oferta,
        'disciplinas_sem_oferta': sem_oferta,
        'total_disciplinas': len(disciplinas),
        'planejamento_editado': planejamento_editado,
    })


@login_required
def simulacao(request):
    """Simula uma grade usando as turmas e os horários importados da PUC."""
    perfil = obter_perfil(request.user)
    curso = perfil.curso
    periodo_oferta = '2026.2'

    # Mostra somente turmas vinculadas às disciplinas do curso escolhido.
    turmas = list(
        Turma.objects.filter(
            disciplina__cursos=curso,
            periodo_letivo=periodo_oferta,
        ).select_related('disciplina').prefetch_related('horarios')
        .order_by('disciplina__codigo', 'codigo')
    ) if curso else []

    ids_permitidos = {str(t.id) for t in turmas}
    selecionados = request.POST.getlist('turmas') if request.method == 'POST' else []
    selecionados = list(dict.fromkeys(selecionados))
    nome = request.POST.get('nome', '').strip() if request.method == 'POST' else ''
    erro = ''

    if request.method == 'POST':
        if not curso:
            erro = 'Escolha seu curso no Perfil antes de montar a grade.'
        elif not selecionados:
            erro = 'Selecione ao menos uma turma.'
        elif any(tid not in ids_permitidos for tid in selecionados):
            erro = 'Uma das turmas selecionadas não pertence ao seu curso.'

    selecionadas = [t for t in turmas if str(t.id) in selecionados] if not erro else []
    codigos = [t.disciplina.codigo for t in selecionadas]
    if not erro and len(codigos) != len(set(codigos)):
        erro = 'Escolha apenas uma turma para cada disciplina.'

    # Eventos ordenados por dia e hora, diretamente do modelo HorarioTurma.
    eventos = []
    for turma in selecionadas:
        for horario in turma.horarios.all():
            eventos.append({
                'dia_numero': horario.dia_semana,
                'dia': horario.get_dia_semana_display(),
                'inicio': horario.hora_inicio,
                'fim': horario.hora_fim,
                'sala': horario.sala,
                'codigo': turma.disciplina.codigo,
                'disciplina': turma.disciplina.nome,
                'turma': turma.codigo,
            })
    eventos.sort(key=lambda evento: (evento['dia_numero'], evento['inicio'], evento['codigo']))

    conflitos = []
    for i, atual in enumerate(eventos):
        for outro in eventos[i + 1:]:
            if outro['dia_numero'] != atual['dia_numero']:
                if outro['dia_numero'] > atual['dia_numero']:
                    break
                continue
            if atual['codigo'] != outro['codigo'] and (
                atual['inicio'] < outro['fim'] and outro['inicio'] < atual['fim']
            ):
                conflitos.append(
                    f"{atual['dia']}: {atual['codigo']} ({atual['turma']}) "
                    f"e {outro['codigo']} ({outro['turma']})"
                )

    if request.method == 'POST' and request.POST.get('acao') == 'salvar' and not erro:
        if not nome:
            erro = 'Informe um nome para salvar a simulação.'
        else:
            descricao = ', '.join(
                f'{turma.disciplina.codigo} - Turma {turma.codigo} ({periodo_oferta})'
                for turma in selecionadas
            )
            SimulacaoSalva.objects.create(nome=nome, disciplinas=descricao)
            messages.success(request, 'Simulação salva com sucesso.')
            return redirect('simulacao')

    for turma in turmas:
        turma.selecionada = str(turma.id) in selecionados
        turma.horarios_lista = sorted(
            turma.horarios.all(), key=lambda h: (h.dia_semana, h.hora_inicio)
        )

    total_creditos = sum(t.disciplina.creditos for t in selecionadas)
    return render(request, 'Simulador (1).html', {
        'curso': curso,
        'periodo_oferta': periodo_oferta,
        'turmas': turmas,
        'selecionadas': selecionadas,
        'eventos': eventos,
        'conflitos': conflitos,
        'total_creditos': total_creditos,
        'erro': erro,
        'nome': nome,
        'dados': SimulacaoSalva.objects.order_by('-id')[:30],
    })


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
                        arquivo_final = pasta / f'usuario_{request.user.pk}.pdf'
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
            caminho = Path.home() / '.fluxa' / 'sau' / f'usuario_{request.user.pk}.pdf'
            if not caminho.is_file():
                messages.error(request, 'Envie o PDF do SAU antes de analisar.')
            else:
                try:
                    analise = analisar_pdf(caminho)
                    request.session['sau_registros_ocr'] = analise['registros']
                    request.session['sau_ocr_usuario'] = request.user.pk
                    request.session['sau_ocr_usado'] = analise['usou_ocr']
                    if analise['registros']:
                        messages.success(
                            request,
                            f"{len(analise['registros'])} disciplina(s) identificada(s) no PDF. "
                            'Confira os dados antes de importar.'
                        )
                        if analise['nao_cadastradas']:
                            messages.warning(
                                request,
                                f"{analise['nao_cadastradas']} disciplina(s) não cadastrada(s) "
                                'no Fluxa aparecem para conferência, mas não podem ser importadas.'
                            )
                    else:
                        messages.warning(
                            request,
                            'Nenhuma disciplina com código, período e situação reconhecíveis '
                            'foi encontrada no catálogo do Fluxa. Confira o PDF.'
                        )
                except (ValueError, OSError, fitz.FileDataError) as exc:
                    request.session.pop('sau_registros_ocr', None)
                    messages.error(request, f'Não foi possível analisar o PDF: {exc}')
            return redirect(reverse('historico') + '#pdf-sau')

        if acao == 'confirmar_ocr_sau':
            opcoes = request.session.get('sau_registros_ocr', [])
            if request.session.get('sau_ocr_usuario') != request.user.pk or not opcoes:
                messages.error(request, 'Analise novamente o PDF antes de confirmar.')
            else:
                indices = set(request.POST.getlist('selecionados'))
                selecionados = [
                    item for i, item in enumerate(opcoes)
                    if str(i) in indices and item.get('cadastrada', True)
                ]
                disciplinas = Disciplina.objects.in_bulk(
                    [item['codigo'] for item in selecionados], field_name='codigo'
                )
                alterados = 0
                for item in selecionados:
                    disciplina = disciplinas.get(item['codigo'])
                    if not disciplina:
                        continue
                    dados = {
                        'status': item['status'],
                        'periodo_letivo': item['periodo'],
                    }
                    if item['media'] is not None:
                        dados['media'] = item['media']
                    HistoricoDisciplina.objects.update_or_create(
                        perfil=perfil, disciplina=disciplina, defaults=dados
                    )
                    alterados += 1
                request.session.pop('sau_registros_ocr', None)
                request.session.pop('sau_ocr_usuario', None)
                messages.success(request, f'{alterados} disciplina(s) confirmada(s) no histórico.')
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
        'sau_pdf_existe': (Path.home() / '.fluxa' / 'sau' / f'usuario_{request.user.pk}.pdf').is_file(),
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
    """Busca os pre-requisitos diretos e indiretos."""
    encontrados = set()
    visitados = {codigo}
    pendentes = [codigo]

    while pendentes:
        atual = pendentes.pop()

        for grupo in grupos.get(atual, []):
            for requisito in grupo:
                if requisito == codigo:
                    continue

                encontrados.add(requisito)

                if requisito not in visitados:
                    visitados.add(requisito)
                    pendentes.append(requisito)

    return encontrados


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

    # Buscar disciplinas do curso
    if curso:
        disciplinas = curso.disciplinas.prefetch_related(
            'grupos_pre_requisito__disciplinas',
            'co_requisitos',
            'associadas',
        )
    else:
        disciplinas = Disciplina.objects.none()

    lista = ordenar_por_camada(disciplinas)
    relacoes = relacoes_do_curso(curso.nome) if curso else None
    por_periodo = bool(relacoes)

    # Separar as disciplinas por periodo
    if por_periodo:
        for d in lista:
            periodo = relacoes.get(d.codigo, {}).get('periodo')

            if isinstance(periodo, int) and 1 <= periodo <= 10:
                d.camada = periodo - 1
            else:
                d.camada = 10

        lista.sort(key=lambda d: (d.camada, d.codigo))

    codigos_curso = {d.codigo for d in lista}

    # Consultar historico do aluno
    situacoes = dict(
        perfil.historico.values_list(
            'disciplina__codigo',
            'status'
        )
    )

    concluidas = {
        codigo for codigo, status in situacoes.items()
        if status == HistoricoDisciplina.CONCLUIDA
    }

    em_curso = {
        codigo for codigo, status in situacoes.items()
        if status == HistoricoDisciplina.EM_CURSO
    }

    avisos = avisos_de_nivel(perfil, lista)

    # Organizar requisitos das disciplinas
    info = {}
    usadas = set()

    for d in lista:
        if por_periodo:
            dados = relacoes.get(d.codigo, {})

            d.nome = dados.get('nome', d.nome)
            d.creditos = dados.get('creditos', d.creditos)

            grupos = [
                sorted(
                    codigo for codigo in grupo
                    if codigo in codigos_curso
                )
                for grupo in dados.get('grupos', [])
            ]

            grupos = [grupo for grupo in grupos if grupo]

            co = sorted(
                set(dados.get('co', [])) & codigos_curso
            )

        else:
            grupos = []

            for grupo in d.grupos_pre_requisito.all():
                membros = sorted(
                    item.codigo
                    for item in grupo.disciplinas.all()
                    if item.codigo in codigos_curso
                )

                if membros:
                    grupos.append(membros)

            co = sorted((
                {item.codigo for item in d.co_requisitos.all()}
                |
                {item.codigo for item in d.associadas.all()}
            ) & codigos_curso)

        for grupo in grupos:
            usadas.update(grupo)

        info[d.codigo] = {
            'obj': d,
            'grupos': grupos,
            'co': co
        }

    # Descobrir disciplinas dependentes
    dependentes = {codigo: set() for codigo in info}

    for codigo, dados in info.items():
        for grupo in dados['grupos']:
            for requisito in grupo:
                dependentes.setdefault(
                    requisito, set()
                ).add(codigo)

    # Situacao de cada disciplina
    for codigo, dados in info.items():
        d = dados['obj']

        d.isolada = (
            not por_periodo
            and not dados['grupos']
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

    # Identificar a disciplina selecionada
    foco = request.GET.get('foco', '').strip().upper()

    if foco not in info:
        foco = ''

    # Pesquisar disciplinas
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
            aviso = f'Nenhuma materia encontrada para "{busca}".'

        elif len(achadas) == 1:
            return redirect(
                _url_fluxograma(
                    achadas[0].codigo,
                    achadas[0].codigo
                )
            )

        else:
            aviso = (
                f'{len(achadas)} materias encontradas. '
                'Escolha uma:'
            )
            resultados = achadas

    # Organizar materias por coluna
    # Inclui materias concluidas para mostrar a cadeia completa
    colunas = {}

    for d in lista:
        if not d.isolada:
            colunas.setdefault(
                d.camada, []
            ).append(d)

    camadas = sorted(colunas)
    cabecalhos = []

    for i, camada in enumerate(camadas):
        x = MARGEM_X + i * (CARTA_L + ESPACO_H)

        if por_periodo:
            if camada < 10:
                titulo = f'{camada + 1}º período'
            else:
                titulo = 'Período não definido'
        else:
            if camada == 0:
                titulo = 'Sem pré-requisito'
            else:
                titulo = f'Nível {camada}'

        cabecalhos.append({
            'x': x,
            'titulo': titulo
        })

        for j, d in enumerate(colunas[camada]):
            d.x = x
            d.y = TOPO + j * (CARTA_A + ESPACO_V)

    # Calcular tamanho da area do fluxograma
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

    # Preparar painel lateral
    painel = None

    if foco:
        grupos_por_codigo = {
            codigo: dados['grupos']
            for codigo, dados in info.items()
        }

        cadeia = _cadeia(
            foco,
            grupos_por_codigo,
            concluidas
        )

        co_foco = (
            set(info[foco]['co'])
            - cadeia
            - {foco}
        )

        info[foco]['obj'].classe = 'alvo'

        for codigo in cadeia:
            if codigo in info:
                info[codigo]['obj'].classe = 'cadeia'

        for codigo in co_foco:
            if codigo in info:
                info[codigo]['obj'].classe = 'co'

        def itens(codigos):
            return [
                {
                    'codigo': codigo,
                    'concluida': info[codigo]['concluida']
                }
                for codigo in sorted(codigos)
                if codigo in info
            ]

        d = info[foco]['obj']
        total_grupos = len(info[foco]['grupos'])

        painel = {
            'codigo': d.codigo,
            'nome': d.nome,
            'creditos': d.creditos,
            'creditos_minimos': d.creditos_minimos,
            'grupos': [
                {
                    'cor': _cor_do_grupo(i, total_grupos),
                    'itens': itens(grupo)
                }
                for i, grupo in enumerate(
                    info[foco]['grupos']
                )
            ],
            'co': itens(info[foco]['co']),
            'dependentes': itens(
                dependentes.get(foco, [])
            ),
            'sem_relacoes': d.isolada,
            'avisos_nivel': d.avisos_nivel,
            'em_curso': foco in em_curso
        }

    # Materias concluidas
    feitas = [
        info[codigo]['obj']
        for codigo in sorted(concluidas)
        if codigo in info
    ]

    # JavaScript desenhara as setas
    return render(request, 'fluxograma.html', {
        'curso': curso,
        'cabecalhos': cabecalhos,
        'cartas': [
            d for d in lista
            if not d.isolada
        ],
        'isoladas': [
            d for d in lista
            if d.isolada
        ],
        'largura': largura,
        'altura': altura,
        'setas': [],
        'marcadores': [],
        'painel': painel,
        'foco': foco,
        'busca': busca,
        'aviso': aviso,
        'resultados': resultados,
        'concluidas': feitas,
        'total_disciplinas': len(lista)
    })



def _buscar_disciplina(codigo):
    try:
        return Disciplina.objects.get(codigo__iexact=codigo)
    except Disciplina.DoesNotExist:
        return None

@login_required
def grafo_fluxograma(request):
    perfil = obter_perfil(request.user)
    curso = perfil.curso

    if not curso:
        return JsonResponse({
            'grafo': {},
            'co_requisitos': {},
            'concluidas': []
        })

    disciplinas = list(
        curso.disciplinas.prefetch_related(
            'grupos_pre_requisito__disciplinas',
            'co_requisitos',
            'associadas'
        )
    )

    codigos = {d.codigo for d in disciplinas}
    relacoes = relacoes_do_curso(curso.nome)

    grafo = {}
    co_requisitos = {}

    for d in disciplinas:
        if relacoes is not None:
            dados = relacoes.get(d.codigo, {})
            grupos = dados.get('grupos', [])
            co = dados.get('co', [])

        else:
            grupos = [
                [
                    item.codigo
                    for item in grupo.disciplinas.all()
                ]
                for grupo in d.grupos_pre_requisito.all()
            ]

            co = (
                [item.codigo for item in d.co_requisitos.all()]
                +
                [item.codigo for item in d.associadas.all()]
            )

        grafo[d.codigo] = [
            [
                codigo
                for codigo in grupo
                if codigo in codigos
            ]
            for grupo in grupos
            if any(codigo in codigos for codigo in grupo)
        ]

        co_requisitos[d.codigo] = sorted(
            set(co) & codigos
        )

    concluidas = list(
        perfil.historico.filter(
            status=HistoricoDisciplina.CONCLUIDA,
            disciplina__codigo__in=codigos
        ).values_list(
            'disciplina__codigo',
            flat=True
        )
    )

    return JsonResponse({
        'grafo': grafo,
        'co_requisitos': co_requisitos,
        'concluidas': concluidas
    })

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
