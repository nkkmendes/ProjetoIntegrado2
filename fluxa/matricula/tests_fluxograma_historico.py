"""Testes do fluxograma atualizado pelo histórico do aluno.

Usa o currículo real de Engenharia de Computação (planilha do fluxograma):
ENG4010 não tem pré-requisito, ENG4021 exige ENG4010 e ENG4030 exige ENG4021.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .catalogos_fluxograma import relacoes_do_curso
from .models import Curso, Disciplina, HistoricoDisciplina
from .servicos import obter_perfil

CURSO = 'Engenharia de Computação'


class FluxogramaPeloHistoricoTest(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(nome=CURSO)
        self.disc = {
            codigo: Disciplina.objects.create(codigo=codigo, nome=codigo, creditos=4)
            for codigo in ('ENG4010', 'ENG4021', 'ENG4030')
        }
        self.user = User.objects.create_user('ana@fluxa.com', password='abc123')
        self.perfil = obter_perfil(self.user)
        self.perfil.curso = self.curso
        self.perfil.save()
        self.client.login(username='ana@fluxa.com', password='abc123')

    def historico(self, codigo, status=HistoricoDisciplina.CONCLUIDA):
        HistoricoDisciplina.objects.create(
            perfil=self.perfil, disciplina=self.disc[codigo], status=status
        )

    def cartas(self):
        r = self.client.get(reverse('fluxograma'))
        self.assertEqual(r.status_code, 200)
        return r, {d.codigo: d for d in r.context['cartas']}

    def test_sem_historico_so_as_sem_pre_requisito_estao_liberadas(self):
        r, cartas = self.cartas()
        self.assertTrue(cartas['ENG4010'].liberada)
        self.assertFalse(cartas['ENG4021'].liberada)
        sem_requisito = {c for c, d in relacoes_do_curso(CURSO).items() if not d['grupos']}
        self.assertEqual(r.context['progresso']['liberadas'], len(sem_requisito))
        self.assertEqual(r.context['progresso']['concluidas'], 0)

    def test_concluir_libera_as_proximas(self):
        self.historico('ENG4010')
        r, cartas = self.cartas()
        self.assertTrue(cartas['ENG4010'].concluida)
        self.assertFalse(cartas['ENG4010'].liberada)
        self.assertTrue(cartas['ENG4021'].liberada)
        self.assertFalse(cartas['ENG4030'].liberada)   # ainda falta ENG4021
        self.assertContains(r, 'id="c-ENG4021-P2-1"')
        self.assertIn(' liberada', r.content.decode().split('id="c-ENG4021-P2-1"')[0].rsplit('<a', 1)[1])

    def test_em_curso_aparece_no_cartao_e_nao_libera_as_seguintes(self):
        self.historico('ENG4010')
        self.historico('ENG4021', HistoricoDisciplina.EM_CURSO)
        r, cartas = self.cartas()
        self.assertTrue(cartas['ENG4021'].em_curso)
        self.assertFalse(cartas['ENG4021'].liberada)
        self.assertFalse(cartas['ENG4030'].liberada)
        self.assertContains(r, 'tag-cursando')
        self.assertEqual(r.context['progresso']['em_curso'], 1)

    def test_progresso_conta_as_concluidas(self):
        self.historico('ENG4010')
        self.historico('ENG4021')
        r, cartas = self.cartas()
        p = r.context['progresso']
        self.assertEqual(p['concluidas'], 2)
        self.assertEqual(p['total'], len(cartas))
        self.assertEqual(p['percentual'], round(200 / len(cartas)))
        self.assertTrue(cartas['ENG4030'].liberada)
        self.assertContains(r, f'2 de {len(cartas)}')

    def test_marcar_como_concluida_atualiza_o_desenho(self):
        url = reverse('marcar_concluida', args=['ENG4010'])
        self.client.post(url, {'acao': 'concluir'})
        _, cartas = self.cartas()
        self.assertTrue(cartas['ENG4021'].liberada)
        # Desfazer volta ao estado inicial.
        self.client.post(url, {'acao': 'desfazer'})
        _, cartas = self.cartas()
        self.assertTrue(cartas['ENG4010'].liberada)
        self.assertFalse(cartas['ENG4021'].liberada)

    def test_aluno_sem_curso_nao_quebra(self):
        self.perfil.curso = None
        self.perfil.save()
        self.assertEqual(self.client.get(reverse('fluxograma')).status_code, 200)
