"""A nota de uma reprovação não pode sumir quando o aluno refaz a disciplina.

O histórico guarda uma linha por disciplina (a melhor situação), mas o CR do
SAU conta todas as vezes em que a disciplina foi cursada. Por isso as vezes
anteriores ficam guardadas em TentativaAnterior e entram no CR.
"""
from decimal import Decimal

from django.urls import reverse

from .models import Disciplina, HistoricoDisciplina, TentativaAnterior
from .servicos import calcular_cr, obter_perfil, resumo_creditos
from .tests_sau import FluxoSAUTest, LeitorSAUTest, montar_pdf

# MAT4162 (4 créditos): reprovou em 2025.1 com 3,5 e passou em 2026.1 com 7,0.
# CTC4001 (4 créditos): passou de primeira com 9,1.
REFEZ_E_PASSOU = [
    ('periodo', '20251'),
    ('disc', ['MAT4162 - CÁLCULO A', 'VÁRIAS VARIÁVEIS I', '33D', '3,5', 'RM', 'OB', '4', '60', '0', '1']),
    ('periodo', '20261'),
    ('disc', ['MAT4162 - CÁLCULO A', 'VÁRIAS VARIÁVEIS I', '33B', '7,0', 'AP', 'OB', '4', '60', '0', '2']),
    ('disc', ['CTC4001 - INSTRUMENTAÇÃO E', 'MEDIÇÃO', '33A', '9,1', 'AP', 'OB', '4', '60', '0', '1']),
]


class LeituraDaReprovacaoTest(LeitorSAUTest):
    def test_reprovacao_vira_tentativa_anterior(self):
        calc = self.registro(self.analisar(REFEZ_E_PASSOU), 'MAT4162')
        self.assertEqual(calc['status'], 'concluida')       # vale a aprovação
        self.assertEqual(calc['media'], '7.00')
        self.assertEqual(calc['tentativas'], 2)
        self.assertEqual(calc['anteriores'], [{
            'periodo': '2025.1', 'turma': '33D', 'situacao_sau': 'Reprovado por média',
            'status': 'reprovada', 'media': '3.50',
        }])

    def test_reprovacao_antes_de_cursar_de_novo_tambem_fica(self):
        # No PDF padrão: RM em 2025.1 e cursando de novo (EA) em 2026.2.
        calc = self.registro(self.analisar(), 'MAT4162')
        self.assertEqual(calc['status'], 'em_curso')
        self.assertEqual([a['media'] for a in calc['anteriores']], ['3.50'])

    def test_quem_passou_de_primeira_nao_tem_anteriores(self):
        ctc = self.registro(self.analisar(REFEZ_E_PASSOU), 'CTC4001')
        self.assertEqual(ctc['anteriores'], [])


class ImportacaoDaReprovacaoTest(FluxoSAUTest):
    def importar(self, linhas=REFEZ_E_PASSOU):
        caminho = montar_pdf(self.pasta.name, linhas)
        with open(caminho, 'rb') as f:
            self.client.post(reverse('historico'), {'acao': 'enviar_pdf_sau', 'pdf_sau': f})
        self.client.post(reverse('historico'), {'acao': 'analisar_pdf_sau'})
        registros = self.client.session['sau_registros_ocr']
        return self.client.post(reverse('historico'), {
            'acao': 'confirmar_ocr_sau',
            'selecionados': [str(i) for i in range(len(registros))],
        }, follow=True)

    def test_cr_conta_a_reprovacao_como_o_sau(self):
        self.importar()
        resumo = resumo_creditos(obter_perfil(self.ana))
        # (3,5×4 + 7,0×4 + 9,1×4) ÷ 12 = 6,53 — sem a reprovação daria 8,05.
        self.assertEqual(resumo['cr'], Decimal('6.53'))
        self.assertEqual(resumo['creditos_cr'], 12)
        # Créditos cumpridos não contam a disciplina duas vezes.
        self.assertEqual(resumo['cumpridos'], 8)

    def test_historico_mostra_a_reprovacao_anterior(self):
        pagina = self.importar()
        self.assertContains(pagina, 'Reprovada em 2025.1 — nota 3,50')

    def test_conferencia_mostra_a_reprovacao_antes_de_confirmar(self):
        caminho = montar_pdf(self.pasta.name, REFEZ_E_PASSOU)
        with open(caminho, 'rb') as f:
            self.client.post(reverse('historico'), {'acao': 'enviar_pdf_sau', 'pdf_sau': f})
        self.client.post(reverse('historico'), {'acao': 'analisar_pdf_sau'})
        pagina = self.client.get(reverse('historico'))
        self.assertContains(pagina, 'Antes: Reprovado por média em 2025.1 (nota 3,50, entra no CR).')

    def test_importar_de_novo_nao_duplica_a_reprovacao(self):
        self.importar()
        self.importar()
        self.assertEqual(TentativaAnterior.objects.count(), 1)
        self.assertEqual(resumo_creditos(obter_perfil(self.ana))['cr'], Decimal('6.53'))

    def test_remover_a_disciplina_remove_a_reprovacao(self):
        self.importar()
        self.client.post(reverse('historico_remover', args=['MAT4162']))
        self.assertEqual(TentativaAnterior.objects.count(), 0)

    def test_calcular_cr_com_registros_do_banco(self):
        self.importar()
        registros = obter_perfil(self.ana).historico.select_related('disciplina')
        self.assertEqual(calcular_cr(registros), Decimal('6.53'))

    def test_aluno_sem_reprovacao_continua_igual(self):
        perfil = obter_perfil(self.ana)
        HistoricoDisciplina.objects.create(
            perfil=perfil, disciplina=Disciplina.objects.get(codigo='CTC4001'),
            status='concluida', media=Decimal('9.1'),
        )
        self.assertEqual(resumo_creditos(perfil)['cr'], Decimal('9.10'))
