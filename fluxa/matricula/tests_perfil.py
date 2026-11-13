"""Testes da sincronização do perfil (curso do aluno) com as outras telas."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Curso, Disciplina, HistoricoDisciplina, PerfilAluno, PlanejamentoSalvo
from .servicos import grades_fora_do_curso, obter_perfil
from .tests_simulador import turma


class BasePerfil(TestCase):
    def setUp(self):
        self.comp = Curso.objects.create(nome='Engenharia de Computação')
        self.prod = Curso.objects.create(nome='Engenharia de Produção')

        def disc(codigo, *cursos):
            d = Disciplina.objects.create(codigo=codigo, nome=f'Disciplina {codigo}', creditos=4)
            d.cursos.add(*cursos)
            return d

        self.comum = disc('MAT4161', self.comp, self.prod)   # dos dois cursos
        self.so_comp = disc('INF1010', self.comp)
        self.so_prod = disc('ENG1700', self.prod)

        self.ana = User.objects.create_user(
            'ana@fluxa.com', email='ana@fluxa.com', password='abc123', first_name='Ana'
        )
        self.perfil = obter_perfil(self.ana)
        self.perfil.curso = self.comp
        self.perfil.save()
        self.client.login(username='ana@fluxa.com', password='abc123')

    def salvar_grade(self, nome, *disciplinas):
        plano = PlanejamentoSalvo.objects.create(usuario=self.ana, nome=nome)
        turmas = []
        for d in disciplinas:
            existente = d.turmas.first()
            turmas.append(existente or turma(d, f'T{d.codigo}', [(0, 8, 10)]))
        plano.turmas.set(turmas)
        return plano

    def trocar_curso(self, curso, confirmar=False):
        dados = {'acao': 'curso', 'curso': curso.pk}
        if confirmar:
            dados['confirmar'] = '1'
        return self.client.post(reverse('perfil'), dados, follow=True)


class CadastroComCursoTest(BasePerfil):
    def dados(self, **extra):
        base = {
            'nome': 'Beto Lima', 'email': 'beto@fluxa.com',
            'senha': 'abc123', 'confirmar_senha': 'abc123',
        }
        base.update(extra)
        return base

    def test_cadastro_sem_curso_da_erro(self):
        r = self.client.post(reverse('criarConta'), self.dados())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Escolha o seu curso.')
        self.assertFalse(User.objects.filter(username='beto@fluxa.com').exists())

    def test_cadastro_salva_o_curso_escolhido(self):
        self.client.logout()
        r = self.client.post(reverse('criarConta'), self.dados(curso=self.prod.pk))
        self.assertRedirects(r, reverse('telaInicio'))
        beto = User.objects.get(username='beto@fluxa.com')
        self.assertEqual(beto.perfil_aluno.curso, self.prod)

    def test_perfil_criado_sem_cadastro_nao_ganha_curso_sozinho(self):
        # Ex.: usuário criado pelo createsuperuser.
        admin = User.objects.create_user('admin', password='abc123')
        self.assertIsNone(obter_perfil(admin).curso)


class TrocaDeCursoTest(BasePerfil):
    def test_grades_fora_do_curso_lista_so_as_afetadas(self):
        self.salvar_grade('Só comum', self.comum)
        self.salvar_grade('Com INF', self.comum, self.so_comp)
        afetadas = grades_fora_do_curso(self.ana, self.prod)
        self.assertEqual([g['plano'].nome for g in afetadas], ['Com INF'])
        self.assertEqual(afetadas[0]['codigos'], ['INF1010'])

    def test_troca_sem_grade_afetada_nao_pede_confirmacao(self):
        self.salvar_grade('Só comum', self.comum)
        r = self.trocar_curso(self.prod)
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.curso, self.prod)
        self.assertContains(r, 'Curso alterado para Engenharia de Produção')

    def test_troca_com_grade_afetada_pede_confirmacao(self):
        self.salvar_grade('Com INF', self.so_comp)
        r = self.trocar_curso(self.prod)
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.curso, self.comp)     # ainda não trocou
        self.assertContains(r, 'Confirmar a troca para Engenharia de Produção?')
        self.assertContains(r, 'Com INF: INF1010')
        # O menu continua mostrando o curso atual enquanto não confirma.
        self.assertContains(r, 'PUC-Rio · Engenharia de Computação')

    def test_confirmar_troca_salva_e_avisa_as_grades(self):
        self.salvar_grade('Com INF', self.so_comp)
        r = self.trocar_curso(self.prod, confirmar=True)
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.curso, self.prod)
        self.assertContains(r, 'Estas grades têm disciplinas fora do novo curso: “Com INF”')
        self.assertTrue(PlanejamentoSalvo.objects.filter(nome='Com INF').exists())

    def test_planejamento_marca_disciplina_fora_do_curso(self):
        self.salvar_grade('Mista', self.comum, self.so_prod)
        r = self.client.get(reverse('planejamento'))
        disponibilidade = {
            d['codigo']: d['situacao'] for d in r.context['grades'][0]['disponibilidade']
        }
        self.assertEqual(disponibilidade['ENG1700'], 'Fora do seu curso')
        self.assertNotEqual(disponibilidade['MAT4161'], 'Fora do seu curso')
        self.assertContains(r, 'Fora do seu curso')

    def test_depois_da_troca_as_telas_usam_o_novo_curso(self):
        HistoricoDisciplina.objects.create(perfil=self.perfil, disciplina=self.so_comp, status='concluida')
        self.trocar_curso(self.prod)
        perfil = PerfilAluno.objects.get(user=self.ana)
        # Fluxograma e Simulador passam a usar o novo curso.
        self.assertEqual(self.client.get(reverse('fluxograma')).context['curso'], self.prod)
        self.assertEqual(self.client.get(reverse('simulacao')).context['curso'], self.prod)
        # Créditos: INF1010 (Computação) passa a contar como fora do curso.
        r = self.client.get(reverse('perfil'))
        self.assertEqual(r.context['resumo']['fora_do_curso'], 4)
        self.assertEqual(r.context['resumo']['cumpridos_no_curso'], 0)
        self.assertEqual(perfil.curso, self.prod)


class InicioComPerfilTest(BasePerfil):
    def test_inicio_mostra_curso_e_creditos(self):
        HistoricoDisciplina.objects.create(perfil=self.perfil, disciplina=self.comum, status='concluida')
        r = self.client.get(reverse('telaInicio'))
        self.assertContains(r, 'Olá, Ana')
        self.assertContains(r, 'Engenharia de Computação')
        self.assertContains(r, '4 de 8 (50%)')

    def test_aluno_sem_curso_ve_aviso_e_nenhuma_tela_quebra(self):
        self.perfil.curso = None
        self.perfil.save()
        r = self.client.get(reverse('telaInicio'))
        self.assertContains(r, 'Você ainda não escolheu o seu curso.')
        for nome in ('perfil', 'fluxograma', 'simulacao', 'planejamento', 'historico'):
            self.assertEqual(self.client.get(reverse(nome)).status_code, 200, nome)
        r = self.client.get(reverse('perfil'))
        self.assertContains(r, 'Escolha o seu curso para o fluxograma')
