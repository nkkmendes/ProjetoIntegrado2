from decimal import Decimal

from django.test import SimpleTestCase

from .models import Disciplina, HistoricoDisciplina
from .servicos import calcular_cr


class CalculoCRTest(SimpleTestCase):
    def registro(self, nota, creditos, status='concluida'):
        return HistoricoDisciplina(
            disciplina=Disciplina(creditos=creditos), status=status,
            media=Decimal(nota) if nota is not None else None,
            g1=Decimal('1'), g2=Decimal('2'), g3=Decimal('3'),
        )

    def test_media_ponderada_pela_nota_final_sem_usar_graus(self):
        self.assertEqual(calcular_cr([
            self.registro('8', 4), self.registro('6', 2),
        ]), Decimal('7.33'))

    def test_calculo_seis_creditos_e_algebra_quatro_creditos(self):
        self.assertEqual(calcular_cr([
            self.registro('8', 6), self.registro('9', 4),
        ]), Decimal('8.40'))

    def test_zero_e_reprovacao_contam_sem_nota_e_em_curso_nao(self):
        self.assertEqual(calcular_cr([
            self.registro('10', 4), self.registro('0', 4, 'reprovada'),
            self.registro(None, 6), self.registro('9', 8, 'em_curso'),
        ]), Decimal('5.00'))
        self.assertEqual(calcular_cr([self.registro('0', 4)]), Decimal('0.00'))

    def test_sem_notas_ou_creditos_nao_divide_por_zero(self):
        self.assertIsNone(calcular_cr([]))
        self.assertIsNone(calcular_cr([self.registro(None, 4)]))
        self.assertIsNone(calcular_cr([self.registro('8', 0)]))
