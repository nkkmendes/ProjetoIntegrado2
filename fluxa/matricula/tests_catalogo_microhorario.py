from django.urls import reverse
from .models import Disciplina, GrupoPreRequisito, HistoricoDisciplina, PlanejamentoSalvo
from .tests_simulador import BaseSimulador


class CatalogoMicrohorarioTest(BaseSimulador):
    def test_identifica_curso_sem_excluir_catalogo_global(self):
        dados = self.catalogo()
        self.assertEqual(
            {codigo for codigo, d in dados.items() if d['do_curso']},
            {self.A.codigo, self.B.codigo, self.C.codigo, self.D.codigo,
             self.E.codigo, self.F.codigo, self.G.codigo},
        )
        self.assertIn(self.X.codigo, dados)
        self.assertFalse(dados[self.X.codigo]['do_curso'])
        self.assertTrue(dados[self.B.codigo]['bloqueio'])

    def test_busca_inclui_materia_de_outro_curso_sem_turma(self):
        disciplina = Disciplina.objects.create(codigo='LET9999', nome='Optativa de Letras', creditos=4)
        disciplina.cursos.add(self.outro_curso)
        dados = self.catalogo()
        self.assertIn(disciplina.codigo, dados)
        self.assertEqual(dados[disciplina.codigo]['nome'], 'Optativa de Letras')
        self.assertIn('Sem turma', dados[disciplina.codigo]['bloqueio'])
        self.assertEqual(dados[disciplina.codigo]['turmas'], [])

    def catalogo(self):
        resposta = self.client.get(reverse('simulacao'))
        return {d['codigo']: d for d in resposta.context['dados_simulador']}

    def test_todas_visiveis_com_turmas_e_motivo_do_bloqueio(self):
        dados = self.catalogo()
        self.assertEqual(set(dados), {d.codigo for d in (self.A, self.B, self.C, self.D, self.E, self.F, self.G, self.X)})
        self.assertIn(self.A.codigo, dados[self.B.codigo]['bloqueio'])
        self.assertEqual(dados[self.B.codigo]['turmas'][0]['id'], self.B1.pk)
        self.assertEqual(dados[self.B.codigo]['turmas'][0]['horarios'][0]['inicio'], 540)
        self.assertIn('Sem turma', dados[self.E.codigo]['bloqueio'])
        self.assertFalse(dados[self.X.codigo]['bloqueio'])

    def test_optativa_fora_do_curriculo_pode_ser_salva_e_reaberta(self):
        self.salvar([self.X1])
        plano = PlanejamentoSalvo.objects.get(usuario=self.ana)
        resposta = self.client.get(reverse('simulacao'), {'planejamento': plano.pk})
        self.assertEqual(resposta.context['selecao_inicial'], [self.X1.pk])

    def test_pre_requisito_pendente_bloqueia_post_e_concluido_libera(self):
        self.salvar([self.B1])
        self.assertFalse(PlanejamentoSalvo.objects.exists())
        HistoricoDisciplina.objects.create(perfil=self.perfil_ana, disciplina=self.A, status='concluida')
        self.assertFalse(self.catalogo()[self.B.codigo]['bloqueio'])
        self.salvar([self.B1])
        self.assertTrue(PlanejamentoSalvo.objects.exists())

    def test_excel_sim_sem_detalhes_nao_e_tratado_como_sem_requisitos(self):
        self.X.pre_requisito_no_microhorario = True
        self.X.save()
        self.assertIn('a verificar', self.catalogo()[self.X.codigo]['bloqueio'])
        self.salvar([self.X1])
        self.assertFalse(PlanejamentoSalvo.objects.exists())
        grupo = GrupoPreRequisito.objects.create(disciplina=self.X)
        grupo.disciplinas.add(self.F)  # já concluída
        self.assertFalse(self.catalogo()[self.X.codigo]['bloqueio'])

    def test_exigencia_de_creditos(self):
        self.X.creditos_minimos = 10
        self.X.save()
        self.assertIn('10 créditos', self.catalogo()[self.X.codigo]['bloqueio'])
