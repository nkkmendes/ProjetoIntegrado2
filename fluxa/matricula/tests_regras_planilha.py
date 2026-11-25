from django.test import SimpleTestCase, TestCase
from django.contrib.auth.models import User
from django.urls import reverse

from .models import AreaNivelamento, Curso, Disciplina, GrupoPreRequisito, HistoricoDisciplina, NivelamentoAluno, Turma
from .regras_planilha import RegrasAluno, correquisitos_cumpridos
from .servicos import obter_perfil, disciplinas_disponiveis, validar_selecao


class RegrasExpressoesTest(SimpleTestCase):
    def aluno(self, grupos=None, adicionais=''):
        aluno = RegrasAluno.__new__(RegrasAluno)
        aluno.regras = {'ALV1000': {'grupos': grupos or [], 'adicionais': adicionais}}
        aluno.opcoes = {}
        aluno.concluidas = set()
        aluno.em_curso = set()
        aluno.creditos = 0
        aluno.niveis = {}
        return aluno

    def test_e_dentro_do_grupo_ou_entre_alternativas(self):
        a = self.aluno([['AAA1000', 'BBB1000'], ['CCC1000']])
        a.concluidas = {'AAA1000'}
        self.assertTrue(a.bloqueio('ALV1000'))
        a.concluidas.add('BBB1000')
        self.assertFalse(a.bloqueio('ALV1000'))
        a.concluidas = {'CCC1000'}
        self.assertFalse(a.bloqueio('ALV1000'))

    def test_ctc_matematica_e_portugues_exige_ambos(self):
        a = self.aluno(adicionais='CTC (nivel 2) | MATEMÁTICA (nivel 2)')
        self.assertTrue(a.bloqueio('ALV1000'))
        a.niveis['matematica'] = 2
        self.assertFalse(a.bloqueio('ALV1000'))
        a.regras['ALV1000']['adicionais'] = '160 créditos + PORTUGUÊS (nivel 3)'
        a.creditos = 160
        a.niveis['compreensao textual'] = 3
        a.niveis['interpretacao textual'] = 2
        self.assertTrue(a.bloqueio('ALV1000'))
        a.niveis['interpretacao textual'] = 3
        self.assertFalse(a.bloqueio('ALV1000'))
        a.creditos = 159
        self.assertTrue(a.bloqueio('ALV1000'))

    def test_creditos_so_na_alternativa_indicada(self):
        a = self.aluno([['ENG4004'], ['ENG4782']], 'só na alternativa ENG4004: 140 créditos')
        a.concluidas = {'ENG4004'}
        self.assertTrue(a.bloqueio('ALV1000'))
        a.concluidas = {'ENG4782'}
        self.assertFalse(a.bloqueio('ALV1000'))

    def test_nivelamento_como_alternativa_a_disciplina(self):
        a = self.aluno([['CTC4001']], 'ou, sem disciplina: CTC (nivel 2)')
        a.niveis['matematica'] = 2
        self.assertFalse(a.bloqueio('ALV1000'))

    def test_requisitos_textuais_dentro_da_ementa_da_optativa(self):
        a = self.aluno([['AAA1000', '100 CRÉDITOS'], ['CTC (NIVEL 2)']])
        a.concluidas = {'AAA1000'}
        a.creditos = 99
        self.assertTrue(a.bloqueio('ALV1000'))
        a.creditos = 100
        self.assertFalse(a.bloqueio('ALV1000'))

    def test_grupo_optativo_exige_creditos_e_corequisitos_preservam_ou(self):
        a = self.aluno([['GRP1000']])
        a.regras['GRP1000'] = {'creditos': 4}
        a.opcoes['GRP1000'] = {'OPT1000': 2, 'OPT2000': 2}
        a.concluidas = {'OPT1000'}
        self.assertTrue(a.bloqueio('ALV1000'))
        a.concluidas.add('OPT2000')
        self.assertFalse(a.bloqueio('ALV1000'))
        a.concluidas = {'OPT1000'}
        a.regras['ALV1000']['co_grupos'] = [['GRP1000', 'AAA1000'], ['BBB1000']]
        grupos = a.correquisitos('ALV1000')
        self.assertFalse(correquisitos_cumpridos(grupos, {'OPT2000'}))
        self.assertTrue(correquisitos_cumpridos(grupos, {'OPT2000', 'AAA1000'}))
        self.assertTrue(correquisitos_cumpridos(grupos, {'BBB1000'}))


class RegrasPlanilhaIntegracaoTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('aluno')
        self.perfil = obter_perfil(self.user)
        self.curso = Curso.objects.create(nome='Engenharia de Produção')
        self.perfil.curso = self.curso
        self.perfil.save()
        self.discs = {}
        for codigo, creditos in [('ENG4501', 4), ('INF1037', 4), ('MAT4161', 6), ('MAT4200', 4), ('ENG4010', 4)]:
            d = Disciplina.objects.create(codigo=codigo, nome=codigo, creditos=creditos)
            d.cursos.add(self.curso)
            self.discs[codigo] = d
            Turma.objects.create(disciplina=d, codigo='A', periodo_letivo='2026.2')
        self.client.force_login(self.user)

    def test_nivelamento_ordem_e_regras_do_curso_prevalecem_sobre_banco(self):
        antigo = GrupoPreRequisito.objects.create(disciplina=self.discs['MAT4161'])
        antigo.disciplinas.add(self.discs['ENG4501'])
        r = disciplinas_disponiveis(self.perfil, '2026.2')
        self.assertNotIn('MAT4161', {d.codigo for d in r['disciplinas']})
        area = AreaNivelamento.objects.create(nome='Matemática')
        NivelamentoAluno.objects.create(perfil=self.perfil, area=area, nivel=2)
        r = disciplinas_disponiveis(self.perfil, '2026.2')
        self.assertIn('MAT4161', {d.codigo for d in r['disciplinas']})
        self.assertEqual([d.periodo_grade for d in r['catalogo']], [1, 2, 3, 4, 0])
        grafo = self.client.get(reverse('grafo_fluxograma')).json()
        self.assertEqual(grafo['grafo']['MAT4161'], [])
        self.assertEqual(grafo['grafo']['ENG4501'], [['INF0307', 'MAT4161']])
        self.assertEqual(set(grafo['co_requisitos']['ENG4021']), {'EMP1320', 'INF0307'})

    def test_optativa_concluida_cumpre_grupo_e_requisito_e_validado_no_post(self):
        turma = Turma.objects.get(disciplina=self.discs['ENG4501'])
        self.assertTrue(validar_selecao(self.perfil, '2026.2', [turma.pk])[1])
        for codigo in ('INF1037', 'MAT4161'):
            HistoricoDisciplina.objects.create(perfil=self.perfil, disciplina=self.discs[codigo], status='concluida')
        self.assertFalse(validar_selecao(self.perfil, '2026.2', [turma.pk])[1])
