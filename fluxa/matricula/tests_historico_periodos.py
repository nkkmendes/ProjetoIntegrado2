"""Visualização das notas depois de ler o histórico: disciplinas agrupadas
por período com o CR de cada período, créditos e turma na conferência, e
colunas G1/G2/G3 escondidas quando nenhuma disciplina tem grau lançado.
"""
from decimal import Decimal

from django.urls import reverse

from .models import HistoricoDisciplina
from .servicos import historico_por_periodo, obter_perfil
from .tests_sau import FluxoSAUTest, montar_pdf
from .tests_sau_reprovacao import REFEZ_E_PASSOU, ImportacaoDaReprovacaoTest


class HistoricoPorPeriodoTest(FluxoSAUTest):
    importar = ImportacaoDaReprovacaoTest.importar

    def periodos(self):
        registros = obter_perfil(self.ana).historico.select_related('disciplina')
        return {p['periodo']: p for p in historico_por_periodo(registros)}

    def test_cr_de_cada_periodo(self):
        self.importar()
        periodos = self.periodos()
        # 2026.1: (7,0×4 + 9,1×4) ÷ 8 = 8,05
        self.assertEqual(periodos['2026.1']['cr'], Decimal('8.05'))
        # 2025.1: só a reprovação de MAT4162, que conta no período em que aconteceu.
        self.assertEqual(periodos['2025.1']['cr'], Decimal('3.50'))
        self.assertEqual(periodos['2025.1']['registros'], [])
        self.assertEqual(len(periodos['2025.1']['anteriores']), 1)

    def test_periodo_mais_recente_primeiro(self):
        self.importar()
        registros = obter_perfil(self.ana).historico.select_related('disciplina')
        self.assertEqual([p['periodo'] for p in historico_por_periodo(registros)],
                         ['2026.1', '2025.1'])

    def test_pagina_mostra_periodos_e_cr(self):
        pagina = self.importar()
        self.assertContains(pagina, 'CR do período: 8,05')
        self.assertContains(pagina, 'CR do período: 3,50')
        self.assertContains(pagina, 'Refeita em 2026.1')

    def test_g1_g2_g3_escondidos_sem_graus(self):
        pagina = self.importar()
        self.assertNotContains(pagina, '<th>G1</th>')

    def test_g1_g2_g3_aparecem_quando_ha_grau(self):
        self.importar()
        HistoricoDisciplina.objects.filter(disciplina__codigo='CTC4001').update(g1=Decimal('8.0'))
        pagina = self.client.get(reverse('historico'))
        self.assertContains(pagina, '<th>G1</th>')

    def test_conferencia_mostra_creditos_e_turma(self):
        caminho = montar_pdf(self.pasta.name, REFEZ_E_PASSOU)
        with open(caminho, 'rb') as f:
            self.client.post(reverse('historico'), {'acao': 'enviar_pdf_sau', 'pdf_sau': f})
        self.client.post(reverse('historico'), {'acao': 'analisar_pdf_sau'})
        pagina = self.client.get(reverse('historico'))
        self.assertContains(pagina, '<th>Créd.</th><th>Período</th><th>Turma</th>')
        self.assertContains(pagina, '<td>33A</td>')

    def test_periodo_nao_informado_fica_no_fim(self):
        self.importar()
        HistoricoDisciplina.objects.filter(disciplina__codigo='CTC4001').update(periodo_letivo='')
        registros = obter_perfil(self.ana).historico.select_related('disciplina')
        self.assertEqual([p['periodo'] for p in historico_por_periodo(registros)][-1], '')
