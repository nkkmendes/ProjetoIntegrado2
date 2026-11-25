from django.test import SimpleTestCase
from unittest.mock import patch

from .ementas_oficiais import extrair_regras
from .regras_planilha import RegrasAluno, catalogo_regras, correquisitos_cumpridos


class ParserEmentaTest(SimpleTestCase):
    def html(self, pre, co='Nenhum co-requisito encontrado para ENG4021'):
        return (f'<fieldset id="prerequisito"><legend>Pré-requisitos</legend>{pre}</fieldset>'
                f'<fieldset id="corequisito"><legend>Co-requisitos</legend>{co}</fieldset>')

    def test_nenhum_requisito_com_e_sem_acento(self):
        for prefixo in ('pre', 'pré'):
            with self.subTest(prefixo=prefixo):
                regra = extrair_regras(self.html(f'Nenhum {prefixo}-requisito encontrado para ENG4021'), 'ENG4021')
                self.assertEqual(regra, {'grupos': [], 'co_grupos': []})

    def test_preserva_alternativas_e_conjuncoes_de_links(self):
        html = self.html('<a>eng1000</a><p>ou</p><a>ENG4010</a>',
                         '<a>EMP1320</a><span>e</span><a>INF1037</a><p>ou</p>'
                         '<a>EMP1320</a><span>e</span><a>INF1026</a>')
        self.assertEqual(extrair_regras(html, 'ENG4021'), {
            'grupos': [['ENG1000'], ['ENG4010']],
            'co_grupos': [['EMP1320', 'INF1037'], ['EMP1320', 'INF1026']],
        })

    def test_pagina_incompleta_ou_texto_inesperado_nao_vira_sem_requisito(self):
        for html in ('<html>Erro</html>', self.html(''),
                     self.html('Nenhum pre-requisito encontrado para ENG40210'),
                     self.html('Nenhum pre-requisito encontrado para ENG4021 indisponível')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                extrair_regras(html, 'ENG4021')


class RegrasOficiaisTest(SimpleTestCase):
    def aluno(self, grupos, co=None):
        aluno = RegrasAluno.__new__(RegrasAluno)
        aluno.regras = {'ENG4021': {'grupos': grupos, 'co_grupos': co or [], 'adicionais': ''}}
        aluno.opcoes = {}
        aluno.concluidas = set()
        aluno.em_curso = set()
        aluno.creditos = 0
        aluno.niveis = {}
        return aluno

    def test_ctc_e_matematica_mesmo_nivel_e_portugues_exige_duas_areas(self):
        aluno = self.aluno([['CTC (nivel 2)'], ['MATEMÁTICA (nivel 2)']])
        self.assertTrue(aluno.bloqueio('ENG4021'))
        aluno.niveis['matematica'] = 2
        self.assertFalse(aluno.bloqueio('ENG4021'))
        aluno.regras['ENG4021']['grupos'] = [['PORTUGUÊS (nivel 3)', '160 créditos']]
        aluno.creditos = 160
        aluno.niveis.update({'compreensao textual': 3, 'interpretacao textual': 2})
        self.assertTrue(aluno.bloqueio('ENG4021'))
        aluno.niveis['interpretacao textual'] = 3
        self.assertFalse(aluno.bloqueio('ENG4021'))
        aluno.creditos = 159
        self.assertTrue(aluno.bloqueio('ENG4021'))

    def test_correquisito_oficial_nao_pode_ser_substituido_por_grupo_de_creditos(self):
        aluno = self.aluno([['ENG1000'], ['ENG1127'], ['ENG4010']],
                           [['EMP1320', 'INF1037'], ['EMP1320', 'INF1026'], ['EMP1320', 'INF1007']])
        aluno.regras['INF0307'] = {'creditos': 4}
        aluno.opcoes['INF0307'] = {'INF1037': 4, 'INF9999': 4}
        aluno.concluidas = {'ENG4010', 'INF9999'}
        self.assertFalse(aluno.bloqueio('ENG4021'))
        pendentes = aluno.correquisitos('ENG4021')
        self.assertFalse(correquisitos_cumpridos(pendentes, {'EMP1320'}))
        self.assertTrue(correquisitos_cumpridos(pendentes, {'EMP1320', 'INF1037'}))
        aluno.em_curso = {'EMP1320', 'INF1007'}
        self.assertEqual(aluno.correquisitos('ENG4021'), [])

    def test_pre_requisito_em_curso_nao_libera_materia(self):
        aluno = self.aluno([['ENG4010']])
        aluno.em_curso = {'ENG4010'}
        self.assertTrue(aluno.bloqueio('ENG4021'))
        aluno.concluidas = {'ENG4010'}
        self.assertFalse(aluno.bloqueio('ENG4021'))

    def test_ementa_ausente_e_planilha_vazia_nao_libera_optativa(self):
        aluno = self.aluno([])
        aluno.regras['ENG4021'].update({'verificacao': '', 'grupo_optativa': False})
        with patch('matricula.regras_planilha.relacoes_do_curso', return_value=aluno.regras), \
                patch('matricula.regras_planilha._linhas', return_value=[]), \
                patch('matricula.regras_planilha.regras_oficiais', return_value={}), \
                patch('matricula.regras_planilha.falhas_oficiais', return_value={'ENG4021'}):
            aluno.regras, aluno.opcoes = catalogo_regras('Curso')
        self.assertIn('não verificados', aluno.bloqueio('ENG4021'))
