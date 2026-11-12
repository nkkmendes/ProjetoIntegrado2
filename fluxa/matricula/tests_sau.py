"""Testes da importação do histórico pelo PDF do SAU.

Os PDFs são gerados aqui mesmo, imitando o layout do "Espelho do Histórico"
(período em cabeçalho, uma célula por linha, nome quebrado em duas linhas).
Nenhum dado pessoal real é usado.
"""
import tempfile
from pathlib import Path
from unittest import mock

import pymupdf
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Disciplina
from .ocr_sau import analisar_pdf, ErroLeituraSAU
from .servicos import obter_perfil


def montar_pdf(pasta, linhas, nome='sau.pdf'):
    """linhas: lista de ('periodo', '20261') ou ('disc', [células...]).
    Cada célula vira um texto independente, como numa tabela de verdade."""
    doc = pymupdf.open()
    pagina = doc.new_page()
    y = 50
    pagina.insert_text((40, y), 'ESPELHO DO HISTÓRICO', fontsize=11)
    y += 30
    for tipo, conteudo in linhas:
        if tipo == 'periodo':
            pagina.insert_text((40, y), conteudo, fontsize=9)
            y += 16
            continue
        for i, celula in enumerate(conteudo):
            pagina.insert_text((40 + 90 * (i % 6), y + 11 * (i // 6)), celula, fontsize=9)
        y += 11 * ((len(conteudo) - 1) // 6 + 1) + 8
    pagina.insert_text((40, y + 10), '* Será desligado compulsoriamente da Universidade', fontsize=8)
    caminho = Path(pasta) / nome
    doc.save(str(caminho))
    return caminho


LINHAS = [
    ('periodo', '20251'),
    ('disc', ['MAT4162 - CÁLCULO A', 'VÁRIAS VARIÁVEIS I', '33D', '3,5', 'RM', 'OB', '4', '60', '0', '1']),
    ('disc', ['FIS4001 - FÍSICA I', '33F', 'CL', 'OB', '5', '75', '0', '1']),
    ('periodo', '20261'),
    ('disc', ['CTC4001 - INSTRUMENTAÇÃO E', 'MEDIÇÃO', '33A', '9,1', 'AP', 'OB', '4', '60', '0', '1']),
    ('disc', ['MAT4181 - CÁLCULO A UMA', 'VARIÁVEL ESP', '33A', '9,4', 'AP', 'OB', 'MAT4161', '6', '90', '0', '1']),
    ('disc', ['EMP1310 - COMUNICAC E', 'TRABALHO EM EQUIPE', '83A', 'DS', 'OC', '2', '30', '0', '1']),
    ('disc', ['ENG4025 - CIÊNCIAS AMBIENTAIS', '33A', 'NI', 'OC', '2', '30', '0', '1']),
    ('disc', ['INF1012 - MODELAGEM DE DADOS', '3WB', 'IN', '2', '30', '0', '1']),
    ('periodo', '20262'),
    ('disc', ['MAT4162 - CÁLCULO A', 'VÁRIAS VARIÁVEIS I', '33D', 'EA', '4', '60', '0', '1']),
    ('disc', ['INF1037 - PROGRAMACAO EM C', '33D', 'EA', '4', '60', '0', '1']),
    ('disc', ['XYZ9999 - DISCIPLINA FORA DO CATALOGO', '33A', '8,0', 'AP', 'PG', '2', '30', '0', '1']),
]

CATALOGO = [
    ('MAT4162', 'Cálculo a Várias Variáveis I', 4),
    ('FIS4001', 'Física I', 5),
    ('CTC4001', 'Instrumentação e Medição', 4),
    ('MAT4161', 'Cálculo a uma Variável', 6),
    ('EMP1310', 'Comunicação e Trabalho em Equipe', 2),
    ('ENG4025', 'Ciências Ambientais', 2),
    ('INF1012', 'Modelagem de Dados', 2),
    ('INF1037', 'Programação em C', 4),
]


class BaseSAU(TestCase):
    def setUp(self):
        for codigo, nome, creditos in CATALOGO:
            Disciplina.objects.create(codigo=codigo, nome=nome, creditos=creditos)
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)


class LeitorSAUTest(BaseSAU):
    def analisar(self, linhas=LINHAS):
        return analisar_pdf(montar_pdf(self.pasta.name, linhas))

    def registro(self, resultado, codigo):
        return next(r for r in resultado['registros'] if r['codigo'] == codigo)

    def test_le_periodo_do_cabecalho_e_nome_quebrado(self):
        r = self.analisar()
        ctc = self.registro(r, 'CTC4001')
        self.assertEqual(ctc['periodo'], '2026.1')
        self.assertEqual(ctc['status'], 'concluida')
        self.assertEqual(ctc['media'], '9.10')
        self.assertEqual(ctc['turma'], '33A')
        self.assertFalse(r['usou_ocr'])

    def test_equivalencia_de_codigo_pela_coluna_de_grupo(self):
        r = self.analisar()
        calc = self.registro(r, 'MAT4161')
        self.assertEqual(calc['codigo_lido'], 'MAT4181')
        self.assertIn('MAT4181', calc['aviso'])
        self.assertEqual(calc['media'], '9.40')

    def test_creditos_transferidos_e_dispensados_contam_como_concluidos_sem_media(self):
        emp = self.registro(self.analisar(), 'EMP1310')
        self.assertEqual(emp['status'], 'concluida')
        self.assertIsNone(emp['media'])

    def test_ni_pede_escolha_do_aluno(self):
        amb = self.registro(self.analisar(), 'ENG4025')
        self.assertTrue(amb['escolher'])
        self.assertEqual(amb['status'], '')

    def test_in_e_cancelamentos_sao_ignorados(self):
        r = self.analisar()
        codigos = {i['codigo'] for i in r['ignoradas']}
        self.assertEqual(codigos, {'FIS4001', 'INF1012'})
        self.assertNotIn('FIS4001', [x['codigo'] for x in r['registros']])
        self.assertNotIn('INF1012', [x['codigo'] for x in r['registros']])

    def test_disciplina_repetida_vale_a_melhor_situacao(self):
        r = self.analisar()
        calc = self.registro(r, 'MAT4162')
        # reprovou em 2025.1 (RM) e está cursando em 2026.2 (EA)
        self.assertEqual(calc['status'], 'em_curso')
        self.assertEqual(calc['periodo'], '2026.2')
        self.assertEqual(calc['tentativas'], 2)

    def test_em_andamento_nao_tem_tipo_nem_grau(self):
        c = self.registro(self.analisar(), 'INF1037')
        self.assertEqual(c['status'], 'em_curso')
        self.assertIsNone(c['media'])

    def test_disciplina_fora_do_catalogo_aparece_mas_nao_e_cadastrada(self):
        r = self.analisar()
        xyz = self.registro(r, 'XYZ9999')
        self.assertFalse(xyz['cadastrada'])
        self.assertEqual(r['nao_cadastradas'], 1)

    def test_pdf_invalido_gera_erro_em_portugues(self):
        ruim = Path(self.pasta.name) / 'ruim.pdf'
        ruim.write_bytes(b'isto nao e um pdf')
        with self.assertRaises(ErroLeituraSAU):
            analisar_pdf(ruim)

    def test_sem_biblioteca_de_pdf_o_erro_e_claro(self):
        with mock.patch.dict('sys.modules', {'pymupdf': None, 'fitz': None}):
            with self.assertRaises(ErroLeituraSAU):
                analisar_pdf(montar_pdf(self.pasta.name, LINHAS))


class FluxoSAUTest(BaseSAU):
    def setUp(self):
        super().setUp()
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        patch = mock.patch('matricula.views.Path.home', return_value=Path(self.home.name))
        patch.start()
        self.addCleanup(patch.stop)
        self.ana = User.objects.create_user('ana', password='abc123')
        self.beto = User.objects.create_user('beto', password='abc123')
        self.client.login(username='ana', password='abc123')

    def enviar(self, client=None):
        caminho = montar_pdf(self.pasta.name, LINHAS)
        with open(caminho, 'rb') as f:
            return (client or self.client).post(
                reverse('historico'), {'acao': 'enviar_pdf_sau', 'pdf_sau': f}
            )

    def pdfs_guardados(self):
        return list((Path(self.home.name) / '.fluxa' / 'sau').glob('*.pdf'))

    def test_pdf_e_apagado_depois_da_analise(self):
        self.enviar()
        self.assertEqual(len(self.pdfs_guardados()), 1)
        self.client.post(reverse('historico'), {'acao': 'analisar_pdf_sau'})
        self.assertEqual(self.pdfs_guardados(), [])

    def test_pdf_e_apagado_mesmo_quando_a_leitura_falha(self):
        pasta = Path(self.home.name) / '.fluxa' / 'sau'
        pasta.mkdir(parents=True)
        (pasta / f'usuario_{self.ana.pk}.pdf').write_bytes(b'%PDF-1.4 quebrado')
        self.client.post(reverse('historico'), {'acao': 'analisar_pdf_sau'})
        self.assertEqual(self.pdfs_guardados(), [])

    def test_descartar_apaga_pdf_e_dados_lidos(self):
        self.enviar()
        self.client.post(reverse('historico'), {'acao': 'analisar_pdf_sau'})
        self.assertIn('sau_registros_ocr', self.client.session)
        self.client.post(reverse('historico'), {'acao': 'descartar_sau'})
        self.assertNotIn('sau_registros_ocr', self.client.session)

    def test_confirmar_grava_escolha_de_ni_e_ignora_sem_escolha(self):
        self.enviar()
        self.client.post(reverse('historico'), {'acao': 'analisar_pdf_sau'})
        registros = self.client.session['sau_registros_ocr']
        indice = {r['codigo']: i for i, r in enumerate(registros)}
        resposta = self.client.post(reverse('historico'), {
            'acao': 'confirmar_ocr_sau',
            'selecionados': [str(indice['CTC4001']), str(indice['ENG4025']), str(indice['EMP1310'])],
            f"status_{indice['ENG4025']}": '',
        }, follow=True)
        perfil = obter_perfil(self.ana)
        h = {x.disciplina.codigo: x for x in perfil.historico.select_related('disciplina')}
        self.assertEqual(set(h), {'CTC4001', 'EMP1310'})  # NI sem escolha ficou de fora
        self.assertEqual(str(h['CTC4001'].media), '9.10')
        self.assertEqual(h['CTC4001'].turma, '33A')
        self.assertIsNone(h['EMP1310'].media)
        self.assertContains(resposta, 'não escolheu')

        # agora com a escolha
        self.enviar()
        self.client.post(reverse('historico'), {'acao': 'analisar_pdf_sau'})
        registros = self.client.session['sau_registros_ocr']
        i = next(k for k, r in enumerate(registros) if r['codigo'] == 'ENG4025')
        self.client.post(reverse('historico'), {
            'acao': 'confirmar_ocr_sau', 'selecionados': [str(i)], f'status_{i}': 'em_curso',
        })
        self.assertEqual(perfil.historico.get(disciplina__codigo='ENG4025').status, 'em_curso')

    def test_cr_do_historico_importado(self):
        self.enviar()
        self.client.post(reverse('historico'), {'acao': 'analisar_pdf_sau'})
        registros = self.client.session['sau_registros_ocr']
        self.client.post(reverse('historico'), {
            'acao': 'confirmar_ocr_sau',
            'selecionados': [str(i) for i, r in enumerate(registros) if r['codigo'] in ('CTC4001', 'MAT4161')],
        })
        from .servicos import resumo_creditos
        r = resumo_creditos(obter_perfil(self.ana))
        self.assertEqual(r['cumpridos'], 10)
        self.assertEqual(str(r['cr']), '9.28')  # (9,1*4 + 9,4*6) / 10

    def test_dados_de_um_aluno_nao_aparecem_para_outro(self):
        self.enviar()
        self.client.post(reverse('historico'), {'acao': 'analisar_pdf_sau'})
        outro = self.client.__class__()
        outro.login(username='beto', password='abc123')
        pagina = outro.get(reverse('historico'))
        self.assertNotContains(pagina, 'Conferir disciplinas reconhecidas')
        self.assertNotContains(pagina, 'No SAU a disciplina tem o código')
        # Beto não consegue confirmar a importação da Ana
        outro.post(reverse('historico'), {'acao': 'confirmar_ocr_sau', 'selecionados': ['0']})
        self.assertEqual(obter_perfil(self.beto).historico.count(), 0)

    def test_tela_do_historico_abre_com_conferencia(self):
        self.enviar()
        self.client.post(reverse('historico'), {'acao': 'analisar_pdf_sau'})
        pagina = self.client.get(reverse('historico'))
        self.assertContains(pagina, 'Conferir disciplinas reconhecidas')
        self.assertContains(pagina, 'Grau não informado')
        self.assertContains(pagina, 'No SAU a disciplina tem o código MAT4181')
