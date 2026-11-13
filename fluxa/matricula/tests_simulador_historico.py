"""Testes do Simulador explicando, pelo Histórico, o que ficou de fora."""
from django.urls import reverse

from .models import (
    Disciplina, GrupoPreRequisito, HistoricoDisciplina, NivelamentoAluno, PlanejamentoSalvo,
)
from .servicos import disciplinas_disponiveis
from .tests_simulador import PERIODO, BaseSimulador, turma


class MotivosDasOcultasTest(BaseSimulador):
    def motivos(self):
        r = disciplinas_disponiveis(self.perfil_ana, PERIODO)
        return {m['codigo']: m['motivo'] for m in r['motivos']}

    def test_cada_disciplina_de_fora_tem_o_seu_motivo(self):
        motivos = self.motivos()
        # B exige A; E não tem turma. F (concluída), G (em curso) e X (outro
        # curso) não entram: não são "ocultas", simplesmente não se aplicam.
        self.assertEqual(motivos, {
            'BBB1000': 'Falta concluir AAA1000.',
            'EEE1000': f'Sem turma em {PERIODO}.',
        })

    def test_motivos_batem_com_os_contadores(self):
        r = disciplinas_disponiveis(self.perfil_ana, PERIODO)
        self.assertEqual(len(r['motivos']), sum(r['ocultas'].values()))

    def test_pre_requisito_em_curso_e_citado(self):
        HistoricoDisciplina.objects.create(perfil=self.perfil_ana, disciplina=self.A, status='em_curso')
        self.assertEqual(self.motivos()['BBB1000'], 'Falta concluir AAA1000 (AAA1000 em curso).')

    def test_grupos_alternativos_mostram_o_mais_perto(self):
        extra = Disciplina.objects.create(codigo='HHH1000', nome='Disciplina HHH1000', creditos=4)
        extra.cursos.add(self.curso)
        turma(extra, 'H1', [(5, 8, 10)])
        g1 = GrupoPreRequisito.objects.create(disciplina=extra)
        g1.disciplinas.set([self.A, self.C, self.E])   # faltam 3
        g2 = GrupoPreRequisito.objects.create(disciplina=extra)
        g2.disciplinas.set([self.B, self.F])            # F concluída: falta só B
        self.assertEqual(
            self.motivos()['HHH1000'],
            'Falta concluir BBB1000, ou outra combinação de pré-requisitos.'
        )

    def test_nivelamento_insuficiente_explica_o_nivel(self):
        NivelamentoAluno.objects.create(perfil=self.perfil_ana, area=self.area, nivel=1)
        self.assertEqual(
            self.motivos()['DDD1000'],
            'Nivelamento insuficiente. Exige nível 2 em Matemática; seu nível: 1.'
        )

    def test_co_requisito_que_nao_pode_ser_cursado(self):
        self.C.co_requisitos.add(self.B)   # C exige cursar junto B, que está trancada
        self.assertEqual(
            self.motivos()['CCC1000'],
            'Exige cursar junto BBB1000, que você ainda não pode cursar.'
        )

    def test_tela_lista_as_ocultas_com_motivo(self):
        r = self.client.get(reverse('simulacao'))
        self.assertContains(r, 'Ver quais e por quê')
        self.assertContains(r, '<strong>BBB1000</strong> — Disciplina BBB1000<span>Falta concluir AAA1000.</span>', html=True)


class GradeReabertaTest(BaseSimulador):
    def test_disciplina_concluida_depois_de_salvar(self):
        self.salvar([self.A1, self.C1])
        HistoricoDisciplina.objects.create(perfil=self.perfil_ana, disciplina=self.A, status='concluida')
        plano = PlanejamentoSalvo.objects.get()
        r = self.client.get(f"{reverse('simulacao')}?planejamento={plano.pk}")
        self.assertContains(r, 'AAA1000 (A1): você já a concluiu no Histórico.')
        self.assertNotContains(r, 'CCC1000 (C1)')

    def test_disciplina_marcada_em_curso(self):
        self.salvar([self.C1])
        HistoricoDisciplina.objects.create(perfil=self.perfil_ana, disciplina=self.C, status='em_curso')
        plano = PlanejamentoSalvo.objects.get()
        r = self.client.get(f"{reverse('simulacao')}?planejamento={plano.pk}")
        self.assertContains(r, 'CCC1000 (C1): ela está como &quot;em curso&quot; no seu Histórico.')

    def test_pre_requisito_desfeito_no_historico(self):
        HistoricoDisciplina.objects.create(perfil=self.perfil_ana, disciplina=self.A, status='concluida')
        self.salvar([self.B1])
        HistoricoDisciplina.objects.filter(disciplina=self.A).delete()
        plano = PlanejamentoSalvo.objects.get()
        r = self.client.get(f"{reverse('simulacao')}?planejamento={plano.pk}")
        self.assertContains(r, 'BBB1000 (B1): falta concluir AAA1000.')

    def test_disciplina_fora_do_curso(self):
        self.salvar([self.C1])
        self.C.cursos.set([self.outro_curso])
        plano = PlanejamentoSalvo.objects.get()
        r = self.client.get(f"{reverse('simulacao')}?planejamento={plano.pk}")
        self.assertContains(r, 'CCC1000 (C1): ela não faz parte do seu curso atual.')


class HistoricoVazioTest(BaseSimulador):
    def test_aluno_com_historico_nao_ve_o_aviso(self):
        r = self.client.get(reverse('simulacao'))
        self.assertFalse(r.context['historico_vazio'])
        self.assertNotContains(r, 'Seu Histórico está vazio')

    def test_aluno_sem_historico_ve_o_aviso(self):
        self.client.login(username='beto', password='abc123')
        r = self.client.get(reverse('simulacao'))
        self.assertTrue(r.context['historico_vazio'])
        self.assertContains(r, 'Seu Histórico está vazio')
        self.assertContains(r, reverse('historico'))
