import os
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import fitz
import pytesseract
from PIL import Image

from .models import Disciplina


MAX_PAGINAS = 12


def configurar_tesseract():
    caminho = os.environ.get('TESSERACT_CMD', '')
    if not caminho and os.name == 'nt':
        caminho = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if caminho:
        pytesseract.pytesseract.tesseract_cmd = caminho


def extrair_texto_pdf(caminho_pdf):
    configurar_tesseract()
    partes = []
    usou_ocr = False

    with fitz.open(str(caminho_pdf)) as documento:
        if documento.needs_pass:
            raise ValueError('Este PDF está protegido por senha.')
        if documento.page_count == 0 or documento.page_count > MAX_PAGINAS:
            raise ValueError(f'O PDF precisa ter entre 1 e {MAX_PAGINAS} páginas.')

        for pagina in documento:
            texto = pagina.get_text('text').strip()
            if len(texto) < 80:
                usou_ocr = True
                imagem_pdf = pagina.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                imagem = Image.frombytes(
                    'RGB', (imagem_pdf.width, imagem_pdf.height), imagem_pdf.samples
                )
                try:
                    texto = pytesseract.image_to_string(
                        imagem, lang='por+eng', config='--psm 6', timeout=25
                    )
                except pytesseract.pytesseract.TesseractNotFoundError as exc:
                    raise ValueError('Tesseract não encontrado no computador.') from exc
                except pytesseract.pytesseract.TesseractError as exc:
                    raise ValueError('Falha ao executar OCR nesta página.') from exc
                except RuntimeError as exc:
                    raise ValueError('OCR excedeu o tempo limite.') from exc
            partes.append(texto)

    return '\n'.join(partes), usou_ocr


def _normalizar_nome(nome):
    nome = unicodedata.normalize('NFKD', nome.casefold())
    nome = ''.join(c for c in nome if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', nome).strip()


def _corrigir_codigo_por_nome(codigo_lido, nome_lido):
    """Corrige código suspeito só quando o nome confirma uma única disciplina.

    Exemplo: CRC4001, reconhecido pelo OCR, corresponde a CTC4001
    quando o nome lido é 'Instrumentação e Medição'.
    """
    numero = re.search(r'(\d{4})$', codigo_lido)
    nome_normalizado = _normalizar_nome(nome_lido)
    if not numero or len(nome_normalizado) < 8:
        return None

    candidatos = []
    for disciplina in Disciplina.objects.filter(codigo__endswith=numero.group(1)):
        nome_cadastrado = _normalizar_nome(disciplina.nome)
        semelhanca = SequenceMatcher(None, nome_normalizado, nome_cadastrado).ratio()
        prefixo_lido = codigo_lido[:-4]
        prefixo_cadastrado = disciplina.codigo[:-4]
        diferencas = sum(a != b for a, b in zip(prefixo_lido, prefixo_cadastrado))
        diferencas += abs(len(prefixo_lido) - len(prefixo_cadastrado))
        if diferencas <= 1 and semelhanca >= 0.90:
            candidatos.append(disciplina)

    if len(candidatos) == 1:
        return candidatos[0]
    return None


def identificar_disciplinas(texto):
    # Extrai apenas linhas com código, período e situação reconhecíveis.
    codigo_re = re.compile(r'\b([A-Z]{2,4}\s*\d{4})\b', re.I)
    periodo_re = re.compile(r'\b(20\d{2}\s*[.\-/]\s*[12])\b')
    grade_re = re.compile(r'(?<!\d)(10(?:[,.]0{1,2})?|[0-9](?:[,.][0-9]{1,2})?)(?!\d)')
    reconhecidas = {}
    codigos = set()

    for linha in texto.splitlines():
        codigo_match = codigo_re.search(linha)
        if not codigo_match:
            continue
        codigo = re.sub(r'\s+', '', codigo_match.group(1)).upper()
        codigos.add(codigo)
        periodo_match = periodo_re.search(linha, codigo_match.end())
        if not periodo_match:
            continue

        # Ignora texto que precede o período (nome e créditos).
        detalhes = linha[periodo_match.end():]
        detalhes_normalizados = detalhes.casefold()
        if re.search(r'conclu[ií]d', detalhes_normalizados):
            status = 'concluida'
        elif re.search(r'em\s+curso|cursando', detalhes_normalizados):
            status = 'em_curso'
        elif re.search(r'reprovad', detalhes_normalizados):
            status = 'reprovada'
        else:
            continue

        media = None
        valores = grade_re.findall(detalhes)
        if valores:
            ultimo = valores[-1].replace(',', '.')
            try:
                nota = float(ultimo)
                if 0 <= nota <= 10:
                    media = f'{nota:.2f}'
            except ValueError:
                pass

        periodo = re.sub(r'\s+', '', periodo_match.group(1)).replace('-', '.').replace('/', '.')
        nome_lido = linha[codigo_match.end():periodo_match.start()].strip()
        nome_lido = re.sub(r'\s+\d{1,2}\s*$', '', nome_lido).strip()
        reconhecidas[codigo] = {
            'codigo': codigo,
            'nome_lido': nome_lido,
            'periodo': periodo,
            'status': status,
            'media': media,
        }

    cadastradas = Disciplina.objects.in_bulk(reconhecidas.keys(), field_name='codigo')
    resultados = []
    nao_cadastradas = 0
    codigos_adicionados = set()
    for codigo, dados in reconhecidas.items():
        disciplina = cadastradas.get(codigo)
        corrigido = False
        if disciplina is None:
            disciplina = _corrigir_codigo_por_nome(codigo, dados['nome_lido'])
            corrigido = disciplina is not None

        codigo_final = disciplina.codigo if disciplina else codigo
        if codigo_final in codigos_adicionados:
            continue
        codigos_adicionados.add(codigo_final)

        if not disciplina:
            nao_cadastradas += 1
        resultados.append({
            **dados,
            'codigo': codigo_final,
            'codigo_lido': codigo if corrigido else '',
            'nome': disciplina.nome if disciplina else (dados['nome_lido'] or 'Nome não identificado'),
            'cadastrada': disciplina is not None,
        })
    return resultados, len(codigos), nao_cadastradas


def analisar_pdf(caminho):
    texto, usou_ocr = extrair_texto_pdf(Path(caminho))
    registros, codigos_detectados, nao_cadastradas = identificar_disciplinas(texto)
    return {
        'registros': registros,
        'usou_ocr': usou_ocr,
        'codigos_detectados': codigos_detectados,
        'nao_cadastradas': nao_cadastradas,
    }
