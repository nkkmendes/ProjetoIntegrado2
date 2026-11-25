import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from django.core.management.base import BaseCommand

from matricula.catalogos_fluxograma import ABAS
from matricula.ementas_oficiais import ARQUIVO, extrair_regras, regras_oficiais
from matricula.regras_planilha import catalogo_regras


class Command(BaseCommand):
    help = 'Atualiza o cache dos requisitos a partir das ementas oficiais da PUC-Rio.'

    def add_arguments(self, parser):
        parser.add_argument('--codigos', nargs='+')

    def handle(self, *args, **options):
        codigos = set(options['codigos'] or [])
        if not codigos:
            for nome in ABAS:
                regras, _ = catalogo_regras(nome)
                codigos.update(c for c, regra in regras.items() if not regra.get('grupo_optativa'))
        cache = dict(regras_oficiais())
        agora = datetime.now(timezone.utc).isoformat()

        def consultar(codigo):
            url = 'https://www.puc-rio.br/ferramentas/ementas/ementa.aspx?cd=' + codigo
            for tentativa in range(2):
                try:
                    req = urllib.request.Request(url, headers={'User-Agent': 'Fluxa academic requirements sync'})
                    with urllib.request.urlopen(req, timeout=20) as resposta:
                        html = resposta.read().decode('latin-1')
                    dados = extrair_regras(html, codigo)
                    return codigo, dict(dados, fonte=url, consultado_em=agora), None
                except Exception as erro:
                    if tentativa == 0:
                        time.sleep(0.5)
                    else:
                        return codigo, None, str(erro)

        falhas = []
        with ThreadPoolExecutor(max_workers=3) as pool:
            futuros = [pool.submit(consultar, c) for c in sorted(codigos)]
            for i, futuro in enumerate(as_completed(futuros), 1):
                codigo, dados, erro = futuro.result()
                if dados:
                    cache[codigo] = dados
                else:
                    falhas.append({'codigo': codigo, 'erro': erro})
                if i % 30 == 0 or i == len(codigos):
                    self.stdout.write(f'{i}/{len(codigos)} consultadas; {len(falhas)} não verificadas')
                    self.stdout.flush()
        conteudo = {'atualizado_em': agora, 'disciplinas': cache, 'falhas': falhas}
        temporario = ARQUIVO.with_suffix('.tmp')
        temporario.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporario.replace(ARQUIVO)
        self.stdout.write(self.style.SUCCESS(f'{len(cache)} ementas oficiais em cache; {len(falhas)} falhas registradas.'))
