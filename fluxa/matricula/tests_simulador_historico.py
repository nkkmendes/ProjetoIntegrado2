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
        self.assertIn('Falta concluir AAA1000.', next(d['bloqueio'] for d in r.context['dados_simulador'] if d['codigo'] == 'BBB1000'))
        self.assertContains(r, 'dados-simulador')


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

    def test_disciplina_de_outro_curso_continua_disponivel_como_optativa(self):
        self.salvar([self.C1])
        self.C.cursos.set([self.outro_curso])
        plano = PlanejamentoSalvo.objects.get()
        r = self.client.get(f"{reverse('simulacao')}?planejamento={plano.pk}")
        self.assertIn(self.C1.pk, r.context['selecao_inicial'])


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


class IntegracaoPlanejamentoTest(BaseSimulador):
    def test_planejamento_utiliza_periodo_do_simulador(self):
        self.salvar([self.A1])
        resposta = self.client.get(reverse('planejamento'))
        simulador = self.client.get(reverse('simulacao'))

        self.assertEqual(
            resposta.context['periodo_oferta'],
            simulador.context['periodo']
        )

    def test_optativa_disponivel_no_planejamento(self):
        self.salvar([self.C1])
        self.C.cursos.set([self.outro_curso])

        resposta = self.client.get(reverse('planejamento'))
        disponibilidade = resposta.context['grades'][0]['disponibilidade']

        self.assertEqual(
            disponibilidade[0]['situacao'],
            'Disponível'
        )


class SincronizacaoHistoricoTest(BaseSimulador):
    def situacao_planejamento(self):
        resposta = self.client.get(reverse('planejamento'))
        return resposta.context['grades'][0]['disponibilidade'][0]

    def test_conclusao_atualiza_planejamento(self):
        self.salvar([self.A1])
        registro = HistoricoDisciplina.objects.create(
            perfil=self.perfil_ana,
            disciplina=self.A,
            status='concluida'
        )
        self.assertEqual(
            self.situacao_planejamento()['situacao'],
            'Conclu\u00edda'
        )
        registro.delete()
        self.assertEqual(
            self.situacao_planejamento()['situacao'],
            'Dispon\u00edvel'
        )

    def test_disciplina_em_curso_atualiza_planejamento(self):
        self.salvar([self.C1])
        HistoricoDisciplina.objects.create(
            perfil=self.perfil_ana,
            disciplina=self.C,
            status='em_curso'
        )
        self.assertEqual(
            self.situacao_planejamento()['situacao'],
            'Em curso'
        )

    def test_remocao_de_pre_requisito_atualiza_planejamento(self):
        registro = HistoricoDisciplina.objects.create(
            perfil=self.perfil_ana,
            disciplina=self.A,
            status='concluida'
        )
        self.salvar([self.B1])
        registro.delete()
        self.assertIn(
            'AAA1000',
            self.situacao_planejamento()['motivo']
        )


class DuplicacaoPlanejamentoTest(BaseSimulador):
    def test_duplicar_grade_preserva_dados(self):
        self.salvar([self.A1])
        original = PlanejamentoSalvo.objects.get()

        resposta = self.client.post(reverse('planejamento'), {
            'acao': 'duplicar',
            'planejamento_id': original.pk,
        })

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(PlanejamentoSalvo.objects.count(), 2)

        copia = PlanejamentoSalvo.objects.exclude(pk=original.pk).get()

        self.assertNotEqual(copia.nome, original.nome)
        self.assertEqual(copia.usuario, original.usuario)
        self.assertEqual(copia.periodo_letivo, original.periodo_letivo)
        self.assertEqual(copia.horarios_salvos, original.horarios_salvos)
        self.assertEqual(
            set(copia.turmas.values_list('pk', flat=True)),
            set(original.turmas.values_list('pk', flat=True))
        )

    def test_duplicacoes_possuem_nomes_distintos(self):
        self.salvar([self.A1])
        original = PlanejamentoSalvo.objects.get()

        for _ in range(2):
            self.client.post(reverse('planejamento'), {
                'acao': 'duplicar',
                'planejamento_id': original.pk,
            })

        nomes = list(
            PlanejamentoSalvo.objects.values_list('nome', flat=True)
        )
        self.assertEqual(len(nomes), 3)
        self.assertEqual(len(set(nomes)), 3)


class FiltrosHistoricoTest(BaseSimulador):
    def test_historico_exibe_controles_de_filtragem(self):
        resposta = self.client.get(reverse('historico'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'id="busca-historico"')
        self.assertContains(resposta, 'id="filtro-status"')
        self.assertContains(resposta, 'id="filtro-periodo"')
        self.assertContains(resposta, 'id="limpar-filtros"')
        self.assertContains(resposta, 'id="contador-historico"')

    def test_registro_possui_dados_para_filtragem(self):
        HistoricoDisciplina.objects.create(
            perfil=self.perfil_ana,
            disciplina=self.A,
            status='concluida',
            periodo_letivo='2026.1'
        )

        resposta = self.client.get(reverse('historico'))

        self.assertContains(resposta, 'class="registro-historico"')
        self.assertContains(resposta, 'data-status="concluida"')
        self.assertContains(resposta, 'data-periodo="2026.1"')
