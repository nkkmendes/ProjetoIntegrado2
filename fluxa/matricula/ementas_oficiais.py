"""Leitura estrita das seções de requisitos das ementas oficiais da PUC-Rio."""
import json
import re
from functools import lru_cache
from html.parser import HTMLParser

from .catalogos_fluxograma import BASE

ARQUIVO = BASE / 'dados' / 'requisitos_oficiais_puc.json'


class ParserEmenta(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.secoes = {}
        self.secao = None
        self.legenda = False

    def handle_starttag(self, tag, attrs):
        atributos = dict(attrs)
        if tag == 'fieldset' and atributos.get('id') in ('prerequisito', 'corequisito'):
            self.secao = atributos['id']
            self.secoes[self.secao] = []
        if self.secao and tag == 'legend':
            self.legenda = True

    def handle_endtag(self, tag):
        if tag == 'legend':
            self.legenda = False
        if tag == 'fieldset':
            self.secao = None

    def handle_data(self, data):
        if self.secao and not self.legenda and data.strip():
            self.secoes[self.secao].append(data.strip())


def extrair_regras(html, codigo):
    parser = ParserEmenta()
    parser.feed(html)
    if not all(s in parser.secoes for s in ('prerequisito', 'corequisito')):
        raise ValueError(f'{codigo}: ementa sem as duas seções de requisitos')
    resultado = {}
    for secao, chave in [('prerequisito', 'grupos'), ('corequisito', 'co_grupos')]:
        texto = re.sub(r'\s+', ' ', ' '.join(parser.secoes[secao])).strip()
        if not texto:
            raise ValueError(f'{codigo}: seção {secao} vazia, não verificada')
        if re.fullmatch(r'Nenhum (?:pr[eé]|co)-requisito encontrado para '
                        + re.escape(codigo) + r'\.?', texto, re.I):
            resultado[chave] = []
        else:
            grupos = [[parte.strip() for parte in re.split(r'\s+e\s+', alternativa, flags=re.I)]
                      for alternativa in re.split(r'\s+ou\s+', texto, flags=re.I)]
            # Não aceitar erro HTTP, aviso ou texto de outra seção como requisito.
            for grupo in grupos:
                for termo in grupo:
                    if not re.fullmatch(r'(?:[A-Z]{3}\d{4}|\d+ créditos|[^()]+\(n[ií]vel \d+\))', termo, re.I):
                        raise ValueError(f'{codigo}: requisito não reconhecido: {termo}')
            grupos = [[termo.upper() if re.fullmatch(r'[A-Z]{3}\d{4}', termo, re.I)
                       else termo for termo in grupo] for grupo in grupos]
            resultado[chave] = grupos
    return resultado


@lru_cache(maxsize=2)
def _ler_cache(modificacao):
    return json.loads(ARQUIVO.read_text(encoding='utf-8'))


def regras_oficiais():
    if not ARQUIVO.exists():
        return {}
    return _ler_cache(ARQUIVO.stat().st_mtime_ns)['disciplinas']


def falhas_oficiais():
    if not ARQUIVO.exists():
        return set()
    return {falha['codigo'] for falha in _ler_cache(ARQUIVO.stat().st_mtime_ns).get('falhas', [])}
