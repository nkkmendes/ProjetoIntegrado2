"""Testes da importação dos dados dos cursos e do fluxograma de todos os cursos."""
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .importacao_engenharias import importar_tudo
from .models import Curso, Disciplina, GrupoPreRequisito, HorarioTurma, Turma
from .servicos import obter_perfil


class ImportacaoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.primeira = importar_tudo()
        cls.contagens = {
            'disciplinas': Disciplina.objects.count(),
            'grupos': GrupoPreRequisito.objects.count(),
            'turmas': Turma.objects.count(),
            'horarios': HorarioTurma.objects.count(),
        }

    def test_cria_os_nove_cursos_com_disciplinas(self):
        for nome in ('Engenharia de Computação', 'Engenharia de Produção',
                     'Engenharia de Controle e Automação', 'Engenharia Elétrica',
                     'Engenharia Química', 'Engenharia Civil', 'Engenharia Mecânica',
                     'Engenharia de Materiais e Nanotecnologia', 'Engenharia Ambiental'):
            curso = Curso.objects.get(nome=nome)
            self.assertGreater(curso.disciplinas.count(), 40, nome)

    def test_importa_micro_horario_com_periodo_da_planilha(self):
        self.assertGreater(Turma.objects.count(), 100)
        self.assertEqual(set(Turma.objects.values_list('periodo_letivo', flat=True)), {'2026.2'})

    def test_importar_de_novo_nao_duplica_nem_altera_nada(self):
        segunda = importar_tudo()
        self.assertEqual(self.contagens, {
            'disciplinas': Disciplina.objects.count(),
            'grupos': GrupoPreRequisito.objects.count(),
            'turmas': Turma.objects.count(),
            'horarios': HorarioTurma.objects.count(),
        })
        rel = segunda
        for chave in ('disciplinas_novas', 'vinculos_novos', 'pre_requisitos_novos', 'co_requisitos_novos'):
            self.assertEqual(rel[chave], 0, chave)

    def test_nao_sobrescreve_o_que_ja_existe(self):
        d = Disciplina.objects.get(codigo='ENG1000') if Disciplina.objects.filter(codigo='ENG1000').exists() \
            else Disciplina.objects.filter(cursos__nome='Engenharia de Produção').first()
        d.nome = 'Nome editado pelo admin'
        d.save()
        importar_tudo()
        d.refresh_from_db()
        self.assertEqual(d.nome, 'Nome editado pelo admin')

    def test_disciplina_compartilhada_e_uma_so_com_pre_requisitos_globais(self):
        """Disciplinas de vários cursos existem uma única vez; os pré-requisitos
        pertencem à disciplina, não ao curso."""
        comp = Curso.objects.get(nome='Engenharia de Computação')
        prod = Curso.objects.get(nome='Engenharia de Produção')
        comuns = Disciplina.objects.filter(cursos=comp).filter(cursos=prod).distinct()
        self.assertGreater(comuns.count(), 5)
        self.assertEqual(Disciplina.objects.count(),
                         Disciplina.objects.values('codigo').distinct().count())
        com_requisito = [d for d in comuns if d.grupos_pre_requisito.exists()]
        self.assertTrue(com_requisito)

    def test_comando_importar_dados_roda_e_e_idempotente(self):
        out = StringIO()
        call_command('importar_dados', '--sem-horarios', stdout=out)
        call_command('sincronizar_grade_fluxa', '--sem-horarios', stdout=out)
        self.assertEqual(Disciplina.objects.count(), self.contagens['disciplinas'])


class FluxogramaTodosOsCursosTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        importar_tudo(com_horarios=False)

    def test_fluxograma_renderiza_para_cada_curso(self):
        for curso in Curso.objects.all():
            user = User.objects.create_user(f'u{curso.pk}', password='abc123')
            p = obter_perfil(user)
            p.curso = curso
            p.save()
            self.client.login(username=f'u{curso.pk}', password='abc123')
            r = self.client.get(reverse('fluxograma'))
            self.assertEqual(r.status_code, 200, curso.nome)
            self.assertContains(r, '<svg', msg_prefix=curso.nome)
            self.assertNotContains(r, '<script', msg_prefix=curso.nome)   # sem JS
            self.client.logout()

    def test_aviso_de_requisitos_incompletos_aparece_so_quando_faltam(self):
        casos = {}
        for curso in Curso.objects.all():
            user = User.objects.create_user(f'v{curso.pk}', password='abc123')
            p = obter_perfil(user)
            p.curso = curso
            p.save()
            self.client.login(username=f'v{curso.pk}', password='abc123')
            casos[curso.nome] = self.client.get(reverse('fluxograma')).context['requisitos_incompletos']
            self.client.logout()
        self.assertEqual(len(casos), 9)
        self.assertFalse(casos['Engenharia de Computação'])
        self.assertFalse(casos['Engenharia Civil'])
        self.assertFalse(casos['Engenharia Mecânica'])
