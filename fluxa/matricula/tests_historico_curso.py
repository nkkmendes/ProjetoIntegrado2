from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Curso, Disciplina, HistoricoDisciplina
from .servicos import obter_perfil


class HistoricoCursoTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('aluno')
        self.perfil = obter_perfil(self.user)
        self.curso = Curso.objects.create(nome='Engenharia de Produção')
        self.perfil.curso = self.curso
        self.perfil.save()
        self.materia = Disciplina.objects.create(codigo='ENG1000', nome='Engenharia', creditos=4)
        self.materia.cursos.add(self.curso)
        self.outra = Disciplina.objects.create(codigo='LET1000', nome='Letras', creditos=4)
        self.client.force_login(self.user)

    def test_lista_e_salva_somente_disciplinas_do_curso(self):
        resposta = self.client.get(reverse('historico'))
        self.assertEqual(list(resposta.context['form'].fields['disciplina'].queryset), [self.materia])
        resposta = self.client.post(reverse('historico'), {
            'acao': 'historico', 'disciplina': self.outra.pk, 'status': 'concluida',
        })
        self.assertTrue(resposta.context['form'].errors.get('disciplina'))
        self.assertFalse(HistoricoDisciplina.objects.exists())
        resposta = self.client.post(reverse('historico'), {
            'acao': 'historico', 'disciplina': self.materia.pk, 'status': 'concluida',
        })
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(HistoricoDisciplina.objects.get().disciplina, self.materia)

    def test_sem_curso_nao_lista_catalogo_inteiro(self):
        self.perfil.curso = None
        self.perfil.save()
        resposta = self.client.get(reverse('historico'))
        self.assertFalse(resposta.context['form'].fields['disciplina'].queryset.exists())
