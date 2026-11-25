"""Regras por curso da planilha A, compartilhadas pelo simulador e fluxograma."""
import re
import unicodedata

from .catalogos_fluxograma import GRADE, _linhas, _requisitos, relacoes_do_curso
from .models import HistoricoDisciplina
from .ementas_oficiais import falhas_oficiais, regras_oficiais


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                   if not unicodedata.combining(c)).lower().strip()


def catalogo_regras(nome_curso):
    regras = relacoes_do_curso(nome_curso)
    opcoes = {}
    if not regras:
        return regras, opcoes
    for linha in _linhas(GRADE, 'OPTATIVAS'):
        if linha.get('curso') != nome_curso or not linha.get('disciplina_codigo'):
            continue
        codigo = str(linha['disciplina_codigo']).strip().upper()
        grupo = str(linha['grupo_codigo']).strip().upper()
        creditos = int(linha.get('disciplina_creditos') or 0)
        opcoes.setdefault(grupo, {})[codigo] = creditos
        if codigo not in regras:
            co = _requisitos(linha.get('co_requisitos_ementa'))
            regras[codigo] = {
                'nome': linha.get('disciplina_nome') or codigo,
                'creditos': creditos, 'periodo': 0, 'grupo_optativa': False,
                'grupos': _requisitos(linha.get('pre_requisitos_ementa')),
                'co_grupos': co, 'co': sorted({c for g in co for c in g}),
                'adicionais': '', 'verificacao': str(linha.get('observacao') or ''),
            }
    oficiais = regras_oficiais()
    falhas = falhas_oficiais()
    for codigo, regra in regras.items():
        oficial = oficiais.get(codigo)
        if regra.get('grupo_optativa'):
            continue
        if oficial is None:
            # Uma célula vazia, sem ementa verificável, não comprova ausência
            # de requisitos. Preservar regras já documentadas na planilha.
            if (codigo in falhas and not regra['grupos'] and not regra['co_grupos']
                    and not regra.get('adicionais') and not regra.get('verificacao')):
                regra['verificacao'] = 'Requisitos não verificados: ementa oficial indisponível.'
            continue
        regra['grupos_curriculo'] = regra['grupos']
        regra['co_curriculo'] = regra['co']
        regra['grupos'] = oficial['grupos']
        regra['co_grupos'] = oficial['co_grupos']
        regra['co'] = sorted({c for grupo in oficial['co_grupos'] for c in grupo})
        regra['adicionais'] = ''  # Créditos e níveis ficam na alternativa oficial correta.
        regra['verificacao'] = 'Requisitos consultados na ementa oficial da PUC-Rio.'
        regra['fonte_requisitos'] = oficial['fonte']
        regra['consultado_em'] = oficial['consultado_em']
    return regras, opcoes


def termo_cumprido(termo, codigos):
    return termo['codigo'] in codigos or bool(termo.get('opcoes')) and sum(
        op['creditos'] for op in termo['opcoes'] if op['codigo'] in codigos
    ) >= termo['creditos']


def correquisitos_cumpridos(alternativas, codigos):
    return not alternativas or any(all(termo_cumprido(t, codigos) for t in grupo)
                                   for grupo in alternativas)


class RegrasAluno:
    def __init__(self, perfil):
        self.regras, self.opcoes = catalogo_regras(perfil.curso.nome) if perfil.curso else ({}, {})
        historico = list(perfil.historico.select_related('disciplina'))
        self.concluidas = {r.disciplina.codigo for r in historico if r.status == HistoricoDisciplina.CONCLUIDA}
        self.em_curso = {r.disciplina.codigo for r in historico if r.status == HistoricoDisciplina.EM_CURSO}
        self.creditos = sum(self.regras.get(r.disciplina.codigo, {}).get('creditos', r.disciplina.creditos)
                            for r in historico if r.status == HistoricoDisciplina.CONCLUIDA)
        self.niveis = {normalizar(n.area.nome): n.nivel for n in perfil.niveis.select_related('area')}

    def completar_grupos(self, codigos):
        resultado = set(codigos)
        for grupo, opcoes in self.opcoes.items():
            exigidos = self.regras.get(grupo, {}).get('creditos', 0)
            if exigidos and sum(cr for c, cr in opcoes.items() if c in codigos) >= exigidos:
                resultado.add(grupo)
        return resultado

    def adicional_cumprido(self, texto):
        if not texto:
            return True
        for alternativa in normalizar(texto).split('|'):
            satisfeita = True
            for parte in alternativa.split('+'):
                parte = parte.strip()
                creditos = re.fullmatch(r'(\d+) creditos', parte)
                nivel = re.fullmatch(r'(.+?)\s*\(nivel (\d+)\)', parte)
                if creditos:
                    ok = self.creditos >= int(creditos[1])
                elif nivel:
                    area, minimo = nivel[1].strip(), int(nivel[2])
                    campos = {'ctc': ['matematica'], 'matematica': ['matematica'],
                              'portugues': ['compreensao textual', 'interpretacao textual']}.get(area, [area])
                    ok = all(self.niveis.get(c, 0) >= minimo for c in campos)
                else:
                    ok = False  # Exigência desconhecida nunca libera automaticamente.
                satisfeita = satisfeita and ok
            if satisfeita:
                return True
        return False

    def bloqueio(self, codigo):
        regra = self.regras[codigo]
        if 'nao verificad' in normalizar(regra.get('verificacao', '')):
            return 'Requisitos não verificados; confirme os requisitos desta disciplina.'
        concluidas = self.completar_grupos(self.concluidas)
        grupos = regra['grupos']
        adicionais = regra.get('adicionais', '')
        def grupo_cumprido(grupo):
            return all(c in concluidas if re.fullmatch(r'[A-Z]{3}\d{4}', c)
                       else self.adicional_cumprido(c) for c in grupo)
        pre_ok = not grupos or any(grupo_cumprido(g) for g in grupos)
        normal = normalizar(adicionais)
        if normal.startswith('ou, sem disciplina:'):
            ok = pre_ok or self.adicional_cumprido(adicionais.split(':', 1)[1].strip())
        elif normal.startswith('so na alternativa '):
            condicao, exigencia = adicionais.split(':', 1)
            codigos = set(re.findall(r'[A-Z]{3}\d{4}', condicao))
            ok = any(grupo_cumprido(g) and (set(g) != codigos or self.adicional_cumprido(exigencia.strip())) for g in grupos)
        else:
            ok = pre_ok and self.adicional_cumprido(adicionais)
        if ok:
            return ''

        # Só o que ainda falta: o que o aluno já cumpriu não aparece.
        def faltam_no_grupo(grupo):
            return [c for c in grupo if not (
                c in concluidas if re.fullmatch(r'[A-Z]{3}\d{4}', c)
                else self.adicional_cumprido(c)
            )]

        # Cada alternativa vira a lista do que falta nela.
        alternativas = []
        if normal.startswith('so na alternativa '):
            for g in grupos:
                faltam = faltam_no_grupo(g)
                if set(g) == codigos and not self.adicional_cumprido(exigencia.strip()):
                    faltam.append(exigencia.strip())
                alternativas.append(faltam)
        elif not pre_ok:
            alternativas = [faltam_no_grupo(g) for g in grupos]
        alternativas = [a for a in alternativas if a]

        def prioridade(itens):
            # Menos pendências primeiro; empate: mais disciplinas da grade do curso.
            da_grade = sum(1 for c in itens if c in self.regras)
            estrangeiro = sum(1 for c in itens if 'ESTRANG' in c.upper())
            return (len(itens), -da_grade, estrangeiro)

        texto = ''
        if alternativas:
            melhor = min(alternativas, key=prioridade)
            texto = ' + '.join(melhor)
            if len(alternativas) > 1:
                texto += ' (ou outra combinação equivalente)'
        if normal.startswith('ou, sem disciplina:'):
            extra = adicionais.split(':', 1)[1].strip()
            texto = (texto + ' ou ' if texto else '') + extra
        elif (not normal.startswith('so na alternativa ') and adicionais
              and not self.adicional_cumprido(adicionais)):
            texto = (texto + '; ' if texto else '') + adicionais
        return 'Falta: ' + texto + '.'

    def correquisitos(self, codigo):
        base = self.concluidas | self.em_curso
        cumpridos = self.completar_grupos(base)
        resultado = []
        for grupo in self.regras[codigo].get('co_grupos', []):
            termos = []
            for requisito in grupo:
                if requisito in cumpridos:
                    continue
                if not re.fullmatch(r'[A-Z]{3}\d{4}', requisito) and self.adicional_cumprido(requisito):
                    continue
                opcoes = self.opcoes.get(requisito, {})
                creditos = self.regras.get(requisito, {}).get('creditos', 0)
                termos.append({
                    'codigo': requisito,
                    'creditos': max(0, creditos - sum(cr for c, cr in opcoes.items() if c in base)),
                    'opcoes': [{'codigo': c, 'creditos': cr} for c, cr in opcoes.items() if c not in base],
                })
            if not termos:
                return []
            resultado.append(termos)
        return resultado
