"""Leitura do "Espelho do Histórico" do SAU (PUC-Rio).

Como o PDF do SAU é organizado:
  * o período aparece sozinho, num cabeçalho (ex.: 20261);
  * cada disciplina é uma linha de tabela: código - nome, turma, grau,
    situação (sigla), tipo da disciplina, código de grupo (opcional),
    créditos, horas, horas de extensão e nº de oportunidades;
  * ao extrair o texto, cada célula costuma virar uma linha separada e o nome
    da disciplina pode quebrar em duas linhas.

Por isso o texto é juntado em "blocos" (um por disciplina) e cada bloco é lido
de uma vez, funcionando tanto com texto digital quanto com OCR.

As bibliotecas de PDF e de OCR só são carregadas quando um PDF é analisado:
se faltarem, só o envio do SAU deixa de funcionar, nunca o site inteiro.
"""
import os
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path

from .models import Disciplina, HistoricoDisciplina

MAX_PAGINAS = 12

CONCLUIDA = HistoricoDisciplina.CONCLUIDA
EM_CURSO = HistoricoDisciplina.EM_CURSO
REPROVADA = HistoricoDisciplina.REPROVADA
IGNORAR = 'ignorar'
ESCOLHER = 'escolher'

# Siglas de "Situação em disciplina" do SAU -> (o que o Fluxa faz, descrição).
SITUACOES = {
    'AP': (CONCLUIDA, 'Aprovado'),
    'CP': (CONCLUIDA, 'Cumpriu'),
    'CC': (CONCLUIDA, 'Crédito creditado'),
    'CT': (CONCLUIDA, 'Crédito transferido'),
    'DS': (CONCLUIDA, 'Dispensado'),
    'EA': (EM_CURSO, 'Em andamento'),
    'RM': (REPROVADA, 'Reprovado por média'),
    'RF': (REPROVADA, 'Reprovado por faltas'),
    'NC': (REPROVADA, 'Não cumpriu'),
    'NI': (ESCOLHER, 'Grau não informado'),
    'IN': (IGNORAR, 'Incompleto'),
    'AT': (IGNORAR, 'Trancamento de matrícula'),
    'CA': (IGNORAR, 'Cancelada administrativamente'),
    'CD': (IGNORAR, 'Cancelada no DE-PARA (3ª fase)'),
    'CJ': (IGNORAR, 'Cancelada no DE-PARA (2ª fase)'),
    'CL': (IGNORAR, 'Cancelada sem alteração de carnê'),
    'DT': (IGNORAR, 'Trancamento após CD ou CJ'),
    'LT': (IGNORAR, 'Trancamento após CL'),
}

TIPOS_DISCIPLINA = {
    'AC': 'Atividade complementar',
    'ED': 'Eletiva do departamento',
    'EF': 'Eletiva fora do departamento',
    'EL': 'Eletiva livre',
    'EO': 'Eletiva de orientação',
    'NC': 'Não curricular',
    'OB': 'Obrigatória básica',
    'OC': 'Obrigatória do curso',
    'OE': 'Obrigatória da ênfase',
    'OG': 'Obrigatória geral',
    'OH': 'Obrigatória da habilitação',
    'OP': 'Obrigatória pedagógica',
    'OR': 'Obrigatória religiosa',
    'PB': 'Optativa básica',
    'PC': 'Optativa do curso',
    'PE': 'Optativa da ênfase',
    'PG': 'Optativa geral',
    'PH': 'Optativa da habilitação',
    'PR': 'Optativa religiosa',
}

_CODIGO = r'[A-Z]{3}\d{4}'
_INICIO_BLOCO = re.compile(rf'\b({_CODIGO})\s*-\s*(.*)$')
_CABECALHO_PERIODO = re.compile(r'^(20\d{2})\s?[.\-/]?\s?([12])(?!\d)\s*(.*)$')
_CAUDA = re.compile(
    r'^(?P<nome>.+?)\s+(?P<turma>[0-9A-Z]{2,4})\s+'
    r'(?:(?P<grau>\d{1,2}(?:[.,]\d{1,2})?)\s+)?'
    rf'(?P<sigla>{"|".join(SITUACOES)})\s+'
    r'(?:(?P<tipo>[A-Z]{2})(?=\s)\s+)?'
    rf'(?:(?P<grupo>{_CODIGO})(?=\s)\s+)?'
    r'(?P<creditos>\d{1,2})(?=\s|$)'
)


class ErroLeituraSAU(ValueError):
    """Erro que pode ser mostrado ao aluno, em português."""


# ---------------------------------------------------------------- leitura do PDF

def _biblioteca_pdf():
    try:
        import pymupdf as lib
    except ImportError:
        try:
            import fitz as lib
        except ImportError as exc:
            raise ErroLeituraSAU(
                'A leitura de PDF não está instalada neste computador. '
                'Rode: pip install -r requirements.txt'
            ) from exc
    return lib


def _ocr_da_pagina(pagina, lib):
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise ErroLeituraSAU(
            'Este PDF é uma imagem e precisa de OCR, que não está instalado. '
            'Instale com: pip install -r requirements-ocr.txt (e o programa Tesseract).'
        ) from exc

    caminho = os.environ.get('TESSERACT_CMD', '')
    if not caminho and os.name == 'nt':
        caminho = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if caminho:
        pytesseract.pytesseract.tesseract_cmd = caminho

    imagem_pdf = pagina.get_pixmap(matrix=lib.Matrix(2, 2), alpha=False)
    imagem = Image.frombytes('RGB', (imagem_pdf.width, imagem_pdf.height), imagem_pdf.samples)
    try:
        return pytesseract.image_to_string(imagem, lang='por+eng', config='--psm 6', timeout=25)
    except pytesseract.pytesseract.TesseractNotFoundError as exc:
        raise ErroLeituraSAU('O programa Tesseract não foi encontrado neste computador.') from exc
    except pytesseract.pytesseract.TesseractError as exc:
        raise ErroLeituraSAU('Falha ao executar o OCR nesta página.') from exc
    except RuntimeError as exc:
        raise ErroLeituraSAU('O OCR excedeu o tempo limite.') from exc


def extrair_texto_pdf(caminho_pdf):
    """Devolve (texto, usou_ocr). OCR só entra nas páginas sem texto."""
    lib = _biblioteca_pdf()
    try:
        documento = lib.open(str(caminho_pdf))
    except Exception as exc:  # arquivo corrompido ou não é PDF
        raise ErroLeituraSAU('Não foi possível abrir o arquivo como PDF.') from exc

    partes = []
    usou_ocr = False
    with documento:
        if documento.needs_pass:
            raise ErroLeituraSAU('Este PDF está protegido por senha.')
        if documento.page_count == 0 or documento.page_count > MAX_PAGINAS:
            raise ErroLeituraSAU(f'O PDF precisa ter entre 1 e {MAX_PAGINAS} páginas.')
        for pagina in documento:
            texto = pagina.get_text('text').strip()
            if len(texto) < 80:
                usou_ocr = True
                texto = _ocr_da_pagina(pagina, lib)
            partes.append(texto)
    return '\n'.join(partes), usou_ocr


# ---------------------------------------------------------------- interpretação

def _normalizar_nome(nome):
    nome = unicodedata.normalize('NFKD', nome.casefold())
    nome = ''.join(c for c in nome if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', nome).strip()


def _corrigir_codigo_por_nome(codigo_lido, nome_lido):
    """Corrige um código lido errado (erro típico de OCR) só quando o nome
    confirma uma única disciplina. Ex.: CRC4001 -> CTC4001."""
    numero = re.search(r'(\d{4})$', codigo_lido)
    nome_normalizado = _normalizar_nome(nome_lido)
    if not numero or len(nome_normalizado) < 8:
        return None

    candidatos = []
    for disciplina in Disciplina.objects.filter(codigo__endswith=numero.group(1)):
        semelhanca = SequenceMatcher(
            None, nome_normalizado, _normalizar_nome(disciplina.nome)
        ).ratio()
        prefixo_lido = codigo_lido[:-4]
        prefixo_cadastrado = disciplina.codigo[:-4]
        diferencas = sum(a != b for a, b in zip(prefixo_lido, prefixo_cadastrado))
        if diferencas <= 1 and semelhanca >= 0.90:
            candidatos.append(disciplina)
    return candidatos[0] if len(candidatos) == 1 else None


def _grau(texto):
    if not texto:
        return None
    try:
        valor = Decimal(texto.replace(',', '.'))
    except InvalidOperation:
        return None
    if 0 <= valor <= 10:
        return f'{valor:.2f}'
    return None


def _separar_blocos(texto):
    """Lista de (periodo, codigo, texto_do_bloco), na ordem do PDF."""
    blocos = []
    periodo = ''
    atual = None

    def fechar():
        nonlocal atual
        if atual:
            blocos.append((atual['periodo'], atual['codigo'], ' '.join(atual['partes'])))
        atual = None

    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        if linha.startswith('*') or 'será desligado' in linha.casefold():
            fechar()
            continue

        cabecalho = _CABECALHO_PERIODO.match(linha)
        if cabecalho:
            fechar()
            periodo = f'{cabecalho.group(1)}.{cabecalho.group(2)}'
            linha = cabecalho.group(3).strip()
            if not linha:
                continue

        inicio = _INICIO_BLOCO.search(linha)
        if inicio:
            fechar()
            atual = {
                'periodo': periodo,
                'codigo': inicio.group(1),
                'partes': [inicio.group(2).strip()],
            }
        elif atual:
            atual['partes'].append(linha)
    fechar()
    return blocos


def _ler_bloco(periodo, codigo, texto):
    achado = _CAUDA.match(texto)
    if not achado:
        return None
    acao, rotulo = SITUACOES[achado.group('sigla')]
    return {
        'codigo_lido': codigo,
        'nome_lido': achado.group('nome').strip(),
        'periodo': periodo,
        'turma': achado.group('turma'),
        'sigla': achado.group('sigla'),
        'situacao_sau': rotulo,
        'acao': acao,
        'media': _grau(achado.group('grau')),
        'tipo': achado.group('tipo') or '',
        'tipo_nome': TIPOS_DISCIPLINA.get(achado.group('tipo') or '', ''),
        'grupo': achado.group('grupo') or '',
        'creditos_sau': int(achado.group('creditos')),
    }


# Em caso de várias tentativas na mesma disciplina, vale a melhor situação.
_PESO = {CONCLUIDA: 3, EM_CURSO: 2, ESCOLHER: 2, REPROVADA: 1}


def identificar_disciplinas(texto):
    """Interpreta o texto do PDF. Devolve um dicionário com:
    registros (a importar/conferir), ignoradas, nao_lidas e codigos_detectados."""
    blocos = _separar_blocos(texto)
    lidos, nao_lidas, ignoradas = [], [], []
    for periodo, codigo, conteudo in blocos:
        dados = _ler_bloco(periodo, codigo, conteudo)
        if dados is None:
            nao_lidas.append(codigo)
        elif dados['acao'] == IGNORAR:
            ignoradas.append({
                'codigo': codigo, 'periodo': periodo,
                'situacao_sau': dados['situacao_sau'], 'sigla': dados['sigla'],
            })
        else:
            lidos.append(dados)

    codigos = {d['codigo_lido'] for d in lidos} | {d['grupo'] for d in lidos if d['grupo']}
    cadastradas = Disciplina.objects.in_bulk(codigos, field_name='codigo')

    por_disciplina = {}
    for dados in lidos:
        disciplina = cadastradas.get(dados['codigo_lido'])
        aviso = ''
        if disciplina is None and dados['grupo'] in cadastradas:
            disciplina = cadastradas[dados['grupo']]
            aviso = (f"No SAU a disciplina tem o código {dados['codigo_lido']}; "
                     f"no Fluxa ela é {disciplina.codigo}.")
        if disciplina is None:
            disciplina = _corrigir_codigo_por_nome(dados['codigo_lido'], dados['nome_lido'])
            if disciplina is not None:
                aviso = (f"Código lido como {dados['codigo_lido']}, "
                         f"corrigido para {disciplina.codigo} pelo nome.")
        if disciplina is not None and disciplina.creditos != dados['creditos_sau']:
            aviso = (aviso + ' ' if aviso else '') + (
                f"Créditos no SAU: {dados['creditos_sau']}; no Fluxa: {disciplina.creditos}."
            )

        registro = {
            **dados,
            'codigo': disciplina.codigo if disciplina else dados['codigo_lido'],
            'nome': disciplina.nome if disciplina else (dados['nome_lido'] or 'Nome não identificado'),
            'cadastrada': disciplina is not None,
            'escolher': dados['acao'] == ESCOLHER,
            'status': '' if dados['acao'] == ESCOLHER else dados['acao'],
            'aviso': aviso,
            'tentativas': 1,
        }
        anterior = por_disciplina.get(registro['codigo'])
        if anterior is None:
            por_disciplina[registro['codigo']] = registro
            continue
        registro['tentativas'] = anterior['tentativas'] + 1
        anterior['tentativas'] = registro['tentativas']
        melhor = max(
            (anterior, registro),
            key=lambda r: (_PESO[r['acao']], r['periodo']),
        )
        melhor['tentativas'] = registro['tentativas']
        por_disciplina[registro['codigo']] = melhor

    registros = sorted(por_disciplina.values(), key=lambda r: (r['periodo'], r['codigo']))
    return {
        'registros': registros,
        'ignoradas': ignoradas,
        'nao_lidas': nao_lidas,
        'codigos_detectados': len(blocos),
        'nao_cadastradas': sum(1 for r in registros if not r['cadastrada']),
    }


def analisar_pdf(caminho):
    texto, usou_ocr = extrair_texto_pdf(Path(caminho))
    resultado = identificar_disciplinas(texto)
    resultado['usou_ocr'] = usou_ocr
    return resultado
