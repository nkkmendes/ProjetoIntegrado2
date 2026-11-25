from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from .forms import NivelamentoAlunoForm
from .models import AreaNivelamento, NivelamentoAluno
from .servicos import obter_perfil


class CadastroNivelamentoTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('aluno')
        self.perfil = obter_perfil(self.user)
        self.client.force_login(self.user)

    def test_tres_campos_fixos_e_persistencia(self):
        pagina = self.client.get(reverse('historico'))
        self.assertEqual(set(pagina.context['form_nivel'].fields), set(NivelamentoAlunoForm.CAMPOS))
        self.assertNotContains(pagina, 'name="nova_area"')
        self.assertNotContains(pagina, 'name="area"')
        dados = dict(acao='nivel', matematica='1', compreensao_textual='3', interpretacao_textual='5')
        self.assertEqual(self.client.post(reverse('historico'), dados).status_code, 302)
        self.assertEqual(NivelamentoAluno.objects.filter(perfil=self.perfil).count(), 3)
        pagina = self.client.get(reverse('historico'))
        for campo in NivelamentoAlunoForm.CAMPOS:
            self.assertEqual(pagina.context['form_nivel'][campo].value(), int(dados[campo]))
        dados['matematica'] = '4'
        self.client.post(reverse('historico'), dados)
        self.assertEqual(NivelamentoAluno.objects.count(), 3)

    def test_nivel_invalido_nao_salva_nenhum(self):
        for nivel in ('0', '6', '1.5'):
            self.client.post(reverse('historico'), dict(acao='nivel', matematica=nivel, compreensao_textual='3', interpretacao_textual='5'))
        self.assertFalse(NivelamentoAluno.objects.exists())
        self.assertFalse(AreaNivelamento.objects.exists())

    def test_nao_informado_remove_apenas_nivel_do_aluno(self):
        self.client.post(reverse('historico'), dict(acao='nivel', matematica='2'))
        self.assertEqual(NivelamentoAluno.objects.count(), 1)
        self.client.post(reverse('historico'), dict(acao='nivel', matematica=''))
        self.assertFalse(NivelamentoAluno.objects.exists())
        self.assertEqual(AreaNivelamento.objects.count(), 1)
