"""Testes do Simulador, do Planejamento e do isolamento entre alunos."""
from datetime import time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import (
    AreaNivelamento, Curso, Disciplina, GrupoPreRequisito, HistoricoDisciplina,
    HorarioTurma, NivelamentoAluno, PlanejamentoSalvo, RequisitoNivelamento, Turma,
)
from .servicos import (
    disciplinas_disponiveis, encontrar_conflitos, obter_perfil, periodo_de_oferta,
)

PERIODO = '2026.2'


def turma(disciplina, codigo, horarios, periodo=PERIODO, professor='Prof. Teste', vagas=10):
    t = Turma.objects.create(
        disciplina=disciplina, codigo=codigo, periodo_letivo=periodo,
        professor=professor, vagas=vagas,
    )
    for dia, ini, fim in horarios:
        HorarioTurma.objects.create(
            turma=t, dia_semana=dia, hora_inicio=time(ini), hora_fim=time(fim), sala='S1'
        )
    return t


class BaseSimulador(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(nome='Curso Teste')
        self.outro_curso = Curso.objects.create(nome='Outro Curso')

        def disc(codigo, creditos=4, curso=None):
            d = Disciplina.objects.create(codigo=codigo, nome=f'Disciplina {codigo}', creditos=creditos)
            d.cursos.add(curso or self.curso)
            return d

        self.A = disc('AAA1000')            # sem pré-requisito
        self.B = disc('BBB1000')            # exige A
        self.C = disc('CCC1000')            # sem pré-requisito
        self.D = disc('DDD1000')            # exige nivelamento
        self.E = disc('EEE1000')            # sem turma no período
        self.F = disc('FFF1000')            # será concluída
        self.G = disc('GGG1000')            # em curso
        self.X = disc('XXX1000', curso=self.outro_curso)   # de outro curso

        grupo = GrupoPreRequisito.objects.create(disciplina=self.B)
        grupo.disciplinas.add(self.A)

        self.area = AreaNivelamento.objects.create(nome='Matemática')
        RequisitoNivelamento.objects.create(disciplina=self.D, area=self.area, nivel_minimo=2)

        # A: seg e qua 8-10 (A1) | ter e qui 8-10 (A2)
        self.A1 = turma(self.A, 'A1', [(0, 8, 10), (2, 8, 10)])
        self.A2 = turma(self.A, 'A2', [(1, 8, 10), (3, 8, 10)])
        # B: seg 9-11 (conflita com A1)
        self.B1 = turma(self.B, 'B1', [(0, 9, 11)])
        # C: seg 10-12 (encosta em A1, sem conflito) e ter 8-9 (conflita com A2)
        self.C1 = turma(self.C, 'C1', [(0, 10, 12)])
        self.C2 = turma(self.C, 'C2', [(1, 8, 9)])
        self.D1 = turma(self.D, 'D1', [(4, 8, 10)])
        self.F1 = turma(self.F, 'F1', [(4, 10, 12)])
        self.G1 = turma(self.G, 'G1', [(4, 14, 16)])
        self.X1 = turma(self.X, 'X1', [(4, 16, 18)])

        self.ana = User.objects.create_user('ana', password='abc123')
        self.beto = User.objects.create_user('beto', password='abc123')
        for u in (self.ana, self.beto):
            p = obter_perfil(u)
            p.curso = self.curso
            p.save()
        self.perfil_ana = obter_perfil(self.ana)
        HistoricoDisciplina.objects.create(perfil=self.perfil_ana, disciplina=self.F, status='concluida')
        HistoricoDisciplina.objects.create(perfil=self.perfil_ana, disciplina=self.G, status='em_curso')

        self.client.login(username='ana', password='abc123')

    def codigos_disponiveis(self, perfil=None):
        r = disciplinas_disponiveis(perfil or self.perfil_ana, PERIODO)
        return {d.codigo for d in r['disciplinas']}, r['ocultas']

    def salvar(self, turmas, nome='Grade A', extra=None, client=None):
        dados = {'acao': 'salvar', 'nome': nome, 'turmas': [t.pk for t in turmas]}
        dados.update(extra or {})
        return (client or self.client).post(reverse('simulacao'), dados)


class DisponibilidadeTest(BaseSimulador):
    def test_so_aparece_o_que_o_historico_permite(self):
        codigos, ocultas = self.codigos_disponiveis()
        # A e C livres; B (pré-requisito A pendente), D (nível não informado não bloqueia!),
        # E sem turma, F concluída, G em curso, X de outro curso.
        self.assertEqual(codigos, {'AAA1000', 'CCC1000', 'DDD1000'})
        self.assertEqual(ocultas, {'pre_requisito': 1, 'nivelamento': 0, 'co_requisito': 0, 'sem_turma': 1})

    def test_concluir_o_pre_requisito_libera_a_disciplina(self):
        HistoricoDisciplina.objects.create(perfil=self.perfil_ana, disciplina=self.A, status='concluida')
        codigos, _ = self.codigos_disponiveis()
        self.assertIn('BBB1000', codigos)
        self.assertNotIn('AAA1000', codigos)

    def test_pre_requisito_em_curso_ainda_nao_libera(self):
        HistoricoDisciplina.objects.create(perfil=self.perfil_ana, disciplina=self.A, status='em_curso')
        codigos, _ = self.codigos_disponiveis()
        self.assertNotIn('BBB1000', codigos)

    def test_ou_entre_grupos_e_e_dentro_do_grupo(self):
        extra = Disciplina.objects.create(codigo='HHH1000', nome='H', creditos=2)
        extra.cursos.add(self.curso)
        turma(extra, 'H1', [(5, 8, 10)])
        g1 = GrupoPreRequisito.objects.create(disciplina=extra)
        g1.disciplinas.set([self.A, self.C])      # A e C
        g2 = GrupoPreRequisito.objects.create(disciplina=extra)
        g2.disciplinas.set([self.F])              # ou F
        # F está concluída: libera pelo segundo grupo
        self.assertIn('HHH1000', self.codigos_disponiveis()[0])
        HistoricoDisciplina.objects.filter(disciplina=self.F).delete()
        HistoricoDisciplina.objects.create(perfil=self.perfil_ana, disciplina=self.A, status='concluida')
        self.assertNotIn('HHH1000', self.codigos_disponiveis()[0])   # falta C
        HistoricoDisciplina.objects.create(perfil=self.perfil_ana, disciplina=self.C, status='concluida')
        self.assertIn('HHH1000', self.codigos_disponiveis()[0])

    def test_disciplina_reprovada_pode_ser_cursada_de_novo(self):
        HistoricoDisciplina.objects.create(perfil=self.perfil_ana, disciplina=self.C, status='reprovada')
        self.assertIn('CCC1000', self.codigos_disponiveis()[0])

    def test_nivelamento_informado_abaixo_do_minimo_bloqueia(self):
        NivelamentoAluno.objects.create(perfil=self.perfil_ana, area=self.area, nivel=1)
        codigos, ocultas = self.codigos_disponiveis()
        self.assertNotIn('DDD1000', codigos)
        self.assertEqual(ocultas['nivelamento'], 1)
        NivelamentoAluno.objects.filter(perfil=self.perfil_ana).update(nivel=2)
        self.assertIn('DDD1000', self.codigos_disponiveis()[0])

    def test_periodo_de_oferta_e_o_mais_recente_importado(self):
        self.assertEqual(periodo_de_oferta(), PERIODO)
        turma(self.C, 'C9', [(2, 18, 20)], periodo='2027.1')
        self.assertEqual(periodo_de_oferta(), '2027.1')

    def test_sem_curso_nao_ha_disciplinas(self):
        p = obter_perfil(self.beto)
        p.curso = None
        p.save()
        self.assertEqual(self.codigos_disponiveis(p)[0], set())


class CoRequisitoTest(BaseSimulador):
    def nova(self, codigo, horarios, coreqs=()):
        d = Disciplina.objects.create(codigo=codigo, nome=f'Disciplina {codigo}', creditos=2)
        d.cursos.add(self.curso)
        d.co_requisitos.set(coreqs)
        return d, turma(d, f'{codigo[0]}1', horarios)

    def test_co_requisito_cursavel_junto_libera_e_pede_os_dois(self):
        k, tk = self.nova('KKK1000', [(5, 8, 10)], [self.C])
        r = disciplinas_disponiveis(self.perfil_ana, PERIODO)
        dk = next(d for d in r['disciplinas'] if d.codigo == 'KKK1000')
        self.assertEqual(dk.coreqs_juntos, ['CCC1000'])
        # sozinha não salva; com o co-requisito junto, salva
        self.assertContains(self.salvar([tk]), 'Co-requisito faltando na grade')
        self.assertEqual(PlanejamentoSalvo.objects.count(), 0)
        self.salvar([tk, self.C1])
        self.assertEqual(PlanejamentoSalvo.objects.count(), 1)

    def test_tela_envia_os_co_requisitos_pendentes(self):
        self.nova('KKK1000', [(5, 8, 10)], [self.C])
        r = self.client.get(reverse('simulacao'))
        k = next(d for d in r.context['dados_simulador'] if d['codigo'] == 'KKK1000')
        self.assertEqual(k['juntos'], ['CCC1000'])

    def test_co_requisito_ja_concluido_ou_em_curso_nao_exige_nada(self):
        self.nova('KKK1000', [(5, 8, 10)], [self.F, self.G])   # F concluída, G em curso
        r = disciplinas_disponiveis(self.perfil_ana, PERIODO)
        dk = next(d for d in r['disciplinas'] if d.codigo == 'KKK1000')
        self.assertEqual(dk.coreqs_juntos, [])

    def test_co_requisito_que_nao_pode_ser_cursado_bloqueia(self):
        # E não tem turma; B tem pré-requisito pendente; X é de outro curso
        for alvo in (self.E, self.B, self.X):
            self.nova(f'K{alvo.codigo[:2]}1000', [(5, 8, 10)], [alvo])
        codigos, ocultas = self.codigos_disponiveis()
        for c in ('KEE1000', 'KBB1000', 'KXX1000'):
            self.assertNotIn(c, codigos)
        self.assertEqual(ocultas['co_requisito'], 3)

    def test_bloqueio_em_cadeia(self):
        k, _ = self.nova('KKK1000', [(5, 8, 10)], [self.E])      # E sem turma
        self.nova('MMM1000', [(5, 10, 12)], [k])                  # M depende de K
        codigos, ocultas = self.codigos_disponiveis()
        self.assertNotIn('KKK1000', codigos)
        self.assertNotIn('MMM1000', codigos)
        self.assertEqual(ocultas['co_requisito'], 2)

    def test_nota_do_rodape_menciona_co_requisito(self):
        self.nova('KKK1000', [(5, 8, 10)], [self.E])
        r = self.client.get(reverse('simulacao'))
        self.assertIn('1 com co-requisito que não pode ser cursado agora', r.context['nota_ocultas'])


class ConflitoTest(BaseSimulador):
    def test_horario_que_apenas_encosta_nao_conflita(self):
        self.assertEqual(encontrar_conflitos([self.A1, self.C1]), [])

    def test_sobreposicao_conflita(self):
        c = encontrar_conflitos([self.A1, self.B1])
        self.assertEqual(len(c), 1)
        self.assertIn('AAA1000 e BBB1000', c[0])


class TelaSimuladorTest(BaseSimulador):
    def test_tela_so_entrega_o_que_pode_ser_cursado(self):
        r = self.client.get(reverse('simulacao'))
        self.assertEqual(r.status_code, 200)
        enviados = {d['codigo'] for d in r.context['dados_simulador']}
        self.assertEqual(enviados, {'AAA1000', 'CCC1000', 'DDD1000'})
        self.assertContains(r, 'Disciplinas que posso cursar')
        self.assertIn('1 com pré-requisito pendente', r.context['nota_ocultas'])
        self.assertIn('1 sem turma em 2026.2', r.context['nota_ocultas'])

    def test_dados_enviados_trazem_professor_vagas_e_horarios(self):
        r = self.client.get(reverse('simulacao'))
        a = next(d for d in r.context['dados_simulador'] if d['codigo'] == 'AAA1000')
        t = next(t for t in a['turmas'] if t['codigo'] == 'A1')
        self.assertEqual(t['professor'], 'Prof. Teste')
        self.assertEqual(t['vagas'], 10)
        self.assertEqual(
            sorted((h['dia'], h['inicio'], h['fim']) for h in t['horarios']),
            [(0, 480, 600), (2, 480, 600)],
        )

    def test_sem_curso_mostra_aviso(self):
        p = obter_perfil(self.ana)
        p.curso = None
        p.save()
        self.assertContains(self.client.get(reverse('simulacao')), 'ainda não escolheu um curso')

    def test_sem_turmas_importadas_mostra_aviso(self):
        Turma.objects.all().delete()
        self.assertContains(self.client.get(reverse('simulacao')), 'importar_dados')


class SalvarGradeTest(BaseSimulador):
    def test_salva_em_planejamento(self):
        r = self.salvar([self.A1, self.C1])
        plano = PlanejamentoSalvo.objects.get()
        self.assertRedirects(r, f"{reverse('simulacao')}?planejamento={plano.pk}")
        self.assertEqual(plano.usuario, self.ana)
        self.assertEqual(plano.nome, 'Grade A')
        self.assertEqual(plano.periodo_letivo, PERIODO)
        self.assertEqual(set(plano.turmas.all()), {self.A1, self.C1})

    def test_conflito_e_barrado_no_servidor(self):
        r = self.salvar([self.A1, self.C2, self.A2])      # duas turmas da mesma disciplina
        self.assertContains(r, 'no máximo uma turma por disciplina')
        r = self.salvar([self.A2, self.C2])               # A2 (ter 8-10) x C2 (ter 8-9)
        self.assertContains(r, 'Conflito de horário')
        self.assertEqual(PlanejamentoSalvo.objects.count(), 0)

    def test_turma_de_disciplina_indisponivel_e_barrada(self):
        for indisponivel in (self.B1, self.F1, self.G1, self.X1):
            r = self.salvar([indisponivel])
            self.assertContains(r, 'não estão disponíveis', msg_prefix=indisponivel.codigo)
        self.assertEqual(PlanejamentoSalvo.objects.count(), 0)

    def test_turma_de_outro_periodo_e_barrada(self):
        antiga = turma(self.C, 'C0', [(3, 14, 16)], periodo='2025.2')
        self.assertContains(self.salvar([antiga]), 'não estão disponíveis')

    def test_exige_turma_e_nome(self):
        self.assertContains(self.salvar([]), 'ao menos uma turma')
        self.assertContains(self.salvar([self.A1], nome='   '), 'Dê um nome')
        self.assertContains(self.salvar([self.A1], extra={'turmas': ['abc']}), 'Seleção inválida')
        self.assertEqual(PlanejamentoSalvo.objects.count(), 0)

    def test_nome_repetido_do_mesmo_aluno_e_barrado(self):
        self.salvar([self.A1])
        self.assertContains(self.salvar([self.C1]), 'já tem uma grade com esse nome')
        self.assertEqual(PlanejamentoSalvo.objects.count(), 1)

    def test_editar_atualiza_a_mesma_grade(self):
        self.salvar([self.A1])
        plano = PlanejamentoSalvo.objects.get()
        tela = self.client.get(f"{reverse('simulacao')}?planejamento={plano.pk}")
        self.assertEqual(tela.context['selecao_inicial'], [self.A1.pk])
        self.assertContains(tela, 'Editando a grade')
        self.salvar([self.A2, self.C1], nome='Grade A2', extra={'planejamento_id': plano.pk})
        plano.refresh_from_db()
        self.assertEqual(PlanejamentoSalvo.objects.count(), 1)
        self.assertEqual(plano.nome, 'Grade A2')
        self.assertEqual(set(plano.turmas.all()), {self.A2, self.C1})

    def test_grade_com_turma_que_deixou_de_estar_disponivel(self):
        self.salvar([self.A1, self.C1])
        plano = PlanejamentoSalvo.objects.get()
        HistoricoDisciplina.objects.create(perfil=self.perfil_ana, disciplina=self.A, status='concluida')
        tela = self.client.get(f"{reverse('simulacao')}?planejamento={plano.pk}")
        self.assertEqual(tela.context['selecao_inicial'], [self.C1.pk])
        self.assertContains(tela, 'AAA1000 (A1): você já a concluiu no Histórico.')


class PlanejamentoTest(BaseSimulador):
    def setUp(self):
        super().setUp()
        self.salvar([self.A1, self.C1], nome='Grade A')
        self.plano = PlanejamentoSalvo.objects.get()

    def test_lista_com_resumo(self):
        r = self.client.get(reverse('planejamento'))
        self.assertEqual(r.status_code, 200)
        g = r.context['grades'][0]
        self.assertEqual(g['creditos'], 8)
        self.assertEqual(g['n_disciplinas'], 2)
        self.assertContains(r, 'Grade A')
        self.assertContains(r, f"{reverse('simulacao')}?planejamento={self.plano.pk}")

    def test_renomear(self):
        self.client.post(reverse('planejamento'), {
            'acao': 'renomear', 'planejamento_id': self.plano.pk, 'nome': 'Minha grade'})
        self.plano.refresh_from_db()
        self.assertEqual(self.plano.nome, 'Minha grade')

    def test_renomear_para_nome_repetido_ou_vazio_e_barrado(self):
        outro = PlanejamentoSalvo.objects.create(usuario=self.ana, nome='Outra')
        r = self.client.post(reverse('planejamento'), {
            'acao': 'renomear', 'planejamento_id': outro.pk, 'nome': 'Grade A'}, follow=True)
        self.assertContains(r, 'já tem uma grade com esse nome')
        r = self.client.post(reverse('planejamento'), {
            'acao': 'renomear', 'planejamento_id': outro.pk, 'nome': ' '}, follow=True)
        self.assertContains(r, 'não pode ficar vazio')
        outro.refresh_from_db()
        self.assertEqual(outro.nome, 'Outra')

    def test_excluir(self):
        self.client.post(reverse('planejamento'), {'acao': 'excluir', 'planejamento_id': self.plano.pk})
        self.assertEqual(PlanejamentoSalvo.objects.count(), 0)
        self.assertTrue(Turma.objects.filter(pk=self.A1.pk).exists())   # a turma em si não é apagada

    def test_id_invalido_nao_quebra(self):
        r = self.client.post(reverse('planejamento'), {'acao': 'excluir', 'planejamento_id': 'x'})
        self.assertEqual(r.status_code, 404)


class PrivacidadeTest(BaseSimulador):
    """Cada aluno só enxerga e altera as próprias grades."""

    def setUp(self):
        super().setUp()
        self.salvar([self.A1], nome='SEGREDO_DA_ANA')
        self.plano_ana = PlanejamentoSalvo.objects.get()
        self.bob = self.client_class()
        self.bob.login(username='beto', password='abc123')

    def test_outro_aluno_nao_ve_a_grade_na_lista(self):
        self.assertNotContains(self.bob.get(reverse('planejamento')), 'SEGREDO_DA_ANA')
        self.assertNotContains(self.bob.get(reverse('simulacao')), 'SEGREDO_DA_ANA')

    def test_outro_aluno_nao_abre_a_grade_no_simulador(self):
        r = self.bob.get(f"{reverse('simulacao')}?planejamento={self.plano_ana.pk}")
        self.assertEqual(r.status_code, 404)

    def test_outro_aluno_nao_edita_nem_renomeia_nem_exclui(self):
        r = self.salvar([self.C1], nome='Invadida', extra={'planejamento_id': self.plano_ana.pk}, client=self.bob)
        self.assertEqual(r.status_code, 404)
        for acao in ('renomear', 'excluir'):
            r = self.bob.post(reverse('planejamento'), {
                'acao': acao, 'planejamento_id': self.plano_ana.pk, 'nome': 'Invadida'})
            self.assertEqual(r.status_code, 404)
        self.plano_ana.refresh_from_db()
        self.assertEqual(self.plano_ana.nome, 'SEGREDO_DA_ANA')
        self.assertEqual(set(self.plano_ana.turmas.all()), {self.A1})

    def test_mesmo_nome_em_alunos_diferentes_e_permitido(self):
        self.salvar([self.A1], nome='Grade 1', client=self.bob)
        self.assertEqual(self.salvar([self.A1], nome='Grade 1').status_code, 302)
        self.assertEqual(PlanejamentoSalvo.objects.filter(nome='Grade 1').count(), 2)

    def test_telas_exigem_login(self):
        anonimo = self.client_class()
        for nome in ('simulacao', 'planejamento', 'historico', 'fluxograma'):
            r = anonimo.get(reverse(nome))
            self.assertEqual(r.status_code, 302, nome)
            self.assertIn('login', r['Location'], nome)
