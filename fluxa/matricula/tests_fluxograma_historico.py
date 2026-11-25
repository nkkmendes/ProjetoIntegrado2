"""Testes do fluxograma atualizado pelo histórico do aluno.

Usa o currículo real de Engenharia de Computação (planilha do fluxograma):
Pré-requisitos, correquisitos e nivelamento são avaliados no Django.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .catalogos_fluxograma import ABAS, linhas_do_curso, relacoes_do_curso
from .models import AreaNivelamento, Curso, Disciplina, HistoricoDisciplina, GrupoPreRequisito, NivelamentoAluno
from .servicos import obter_perfil

CURSO = 'Engenharia de Computação'


class FluxogramaPeloHistoricoTest(TestCase):
    def test_todos_os_cursos_mostram_curriculo_inteiro(self):
        for nome in ABAS:
            with self.subTest(curso=nome):
                curso, _ = Curso.objects.get_or_create(nome=nome)
                self.perfil.curso = curso
                self.perfil.save()
                resposta = self.client.get(reverse('fluxograma'))
                esperadas = linhas_do_curso(nome)
                cartas = resposta.context['disciplinas_curso']
                self.assertEqual(len(cartas), len(esperadas))
                self.assertEqual({c.codigo for c in cartas}, {d['codigo'] for d in esperadas})
                self.assertEqual(resposta.context['progresso']['total'], len({d['codigo'] for d in esperadas}))
                self.assertContains(resposta, 'Ver curso completo')
                self.assertContains(resposta, 'Lista completa de')
                self.assertNotContains(resposta, 'fluxograma_setas.js')
                self.assertTrue(resposta.context['setas'])
                relacoes = relacoes_do_curso(nome)
                ligacoes = {(s['origem'], s['destino'], s['co']) for s in resposta.context['setas']}
                esperadas_ligacoes = set()
                for codigo, regra in relacoes.items():
                    for grupo in regra['grupos']:
                        esperadas_ligacoes.update((r, codigo, False) for r in grupo if r in relacoes and r != codigo)
                    esperadas_ligacoes.update((r, codigo, True) for r in regra['co'] if r in relacoes and r != codigo)
                self.assertEqual(ligacoes, esperadas_ligacoes)
                for seta in resposta.context['setas']:
                    self.assertContains(resposta, f'd="{seta["caminho"]}"')
                if nome == 'Engenharia de Produção':
                    self.assertEqual(len(cartas), 69)
                    self.assertEqual(len({c.codigo for c in cartas}), 66)

    def test_cadeia_ate_primeiro_periodo_respeita_planilha_em_vez_de_regra_antiga(self):
        externo = Disciplina.objects.create(codigo='EXT1000', nome='Base externa', creditos=2)
        raiz = Disciplina.objects.create(codigo='EXT0001', nome='Base inicial', creditos=2)
        grupo = GrupoPreRequisito.objects.create(disciplina=self.disc['ENG4010'])
        grupo.disciplinas.add(externo)
        grupo = GrupoPreRequisito.objects.create(disciplina=externo)
        grupo.disciplinas.add(raiz)
        # Ciclo de correquisitos não pode provocar recursão infinita.
        externo.co_requisitos.add(raiz)
        raiz.co_requisitos.add(externo)
        antes = self.client.get(reverse('fluxograma')).context['progresso']['total']
        resposta = self.client.get(reverse('fluxograma'), {'foco': 'ENG4030'})
        cartas = {c.codigo: c for c in resposta.context['cartas']}
        for codigo in ('ENG4021', 'ENG4010'):
            self.assertIn(cartas[codigo].classe, ('cadeia', 'co'))
        self.assertNotIn('EXT1000', cartas)
        self.assertEqual(cartas['ENG4010'].periodo, 1)
        self.assertEqual(resposta.context['progresso']['total'], antes)
        grafo = self.client.get(reverse('grafo_fluxograma')).json()
        self.assertEqual(grafo['grafo']['ENG4030'], [['ENG4021']])
        self.assertEqual(grafo['grafo']['ENG4010'], [])
        self.assertEqual(set(grafo['co_requisitos']['ENG4010']), {'EMP1310', 'ENG4025'})
        self.assertContains(resposta, 'Ver cadeia completa')
        self.assertNotContains(resposta, 'Requisitos adicionais')
        self.assertNotContains(resposta, 'Requisito pendente:')
        self.assertNotContains(resposta, '<h3>')
        setas = resposta.context['setas']
        self.assertTrue(any(s['origem'] == 'ENG4010' and s['destino'] == 'ENG4021' and s['destaque'] for s in setas))
        self.assertEqual(set(cartas), set(relacoes_do_curso(CURSO)))

    def setUp(self):
        self.curso = Curso.objects.create(nome=CURSO)
        self.disc = {
            codigo: Disciplina.objects.create(codigo=codigo, nome=codigo, creditos=4)
            for codigo in ('ENG4010', 'ENG4021', 'ENG4030')
        }
        self.user = User.objects.create_user('ana@fluxa.com', password='abc123')
        self.perfil = obter_perfil(self.user)
        self.perfil.curso = self.curso
        self.perfil.save()
        self.client.login(username='ana@fluxa.com', password='abc123')

    def historico(self, codigo, status=HistoricoDisciplina.CONCLUIDA):
        disciplina, _ = Disciplina.objects.get_or_create(codigo=codigo, defaults={'nome': codigo, 'creditos': 4})
        HistoricoDisciplina.objects.create(
            perfil=self.perfil, disciplina=disciplina, status=status
        )

    def cartas(self):
        r = self.client.get(reverse('fluxograma'))
        self.assertEqual(r.status_code, 200)
        return r, {d.codigo: d for d in r.context['cartas']}

    def test_sem_historico_requisitos_e_correquisitos_impedem_liberacao(self):
        r, cartas = self.cartas()
        self.assertFalse(cartas['ENG4010'].liberada)  # Correquisitos ainda pendentes.
        self.assertFalse(cartas['ENG4021'].liberada)
        self.assertFalse(cartas['MAT4161'].liberada)  # Excel exige nivelamento 2.
        self.assertFalse(cartas['MAT4200'].liberada)
        self.assertEqual(r.context['progresso']['concluidas'], 0)

    def test_concluir_libera_as_proximas(self):
        self.historico('ENG4010')
        r, cartas = self.cartas()
        self.assertTrue(cartas['ENG4010'].concluida)
        self.assertFalse(cartas['ENG4010'].liberada)
        self.assertFalse(cartas['ENG4021'].liberada)  # Só pré-requisito não basta.
        self.historico('EMP1320', HistoricoDisciplina.EM_CURSO)
        self.historico('INF1037', HistoricoDisciplina.EM_CURSO)
        r, cartas = self.cartas()
        self.assertTrue(cartas['ENG4021'].liberada)
        self.assertFalse(cartas['ENG4030'].liberada)   # ainda falta ENG4021
        self.assertContains(r, 'id="c-ENG4021-P2-1"')
        self.assertIn(' liberada', r.content.decode().split('id="c-ENG4021-P2-1"')[0].rsplit('<a', 1)[1])

    def test_em_curso_aparece_no_cartao_e_nao_libera_as_seguintes(self):
        self.historico('ENG4010')
        self.historico('ENG4021', HistoricoDisciplina.EM_CURSO)
        r, cartas = self.cartas()
        self.assertTrue(cartas['ENG4021'].em_curso)
        self.assertFalse(cartas['ENG4021'].liberada)
        self.assertFalse(cartas['ENG4030'].liberada)
        self.assertContains(r, 'tag-cursando')
        self.assertEqual(r.context['progresso']['em_curso'], 1)

    def test_progresso_conta_as_concluidas(self):
        self.historico('ENG4010')
        self.historico('ENG4021')
        r, cartas = self.cartas()
        p = r.context['progresso']
        self.assertEqual(p['concluidas'], 2)
        self.assertEqual(p['total'], len(cartas))
        self.assertEqual(p['percentual'], round(200 / len(cartas)))
        self.assertFalse(cartas['ENG4030'].liberada)  # Correquisitos não informados.
        self.assertContains(r, f'2 de {len(cartas)}')

    def test_marcar_como_concluida_atualiza_o_desenho(self):
        self.historico('EMP1320', HistoricoDisciplina.EM_CURSO)
        self.historico('INF1037', HistoricoDisciplina.EM_CURSO)
        url = reverse('marcar_concluida', args=['ENG4010'])
        self.client.post(url, {'acao': 'concluir'})
        _, cartas = self.cartas()
        self.assertTrue(cartas['ENG4021'].liberada)
        # Desfazer volta ao estado inicial.
        self.client.post(url, {'acao': 'desfazer'})
        _, cartas = self.cartas()
        self.assertFalse(cartas['ENG4010'].liberada)
        self.assertFalse(cartas['ENG4021'].liberada)

    def test_aluno_sem_curso_nao_quebra(self):
        self.perfil.curso = None
        self.perfil.save()
        self.assertEqual(self.client.get(reverse('fluxograma')).status_code, 200)

    def test_grupo_computacao_mostra_so_suas_opcoes_sem_expandir_grade(self):
        resposta = self.client.get(reverse('fluxograma'), {'foco': 'ENG0425'})
        painel = resposta.context['painel']
        self.assertTrue(painel['grupo_optativa'])
        self.assertEqual([d['codigo'] for d in painel['opcoes']], ['ENG4418', 'ENG4431'])
        self.assertTrue(all(d['nome'] and d['creditos'] for d in painel['opcoes']))
        self.assertEqual({c.codigo for c in resposta.context['cartas']}, set(relacoes_do_curso(CURSO)))
        self.assertTrue(next(c for c in resposta.context['cartas'] if c.codigo == 'ENG0425').grupo_optativa)

    def test_grupo_producao_opcoes_respeitam_historico_e_nivelamento(self):
        self.perfil.curso = Curso.objects.create(nome='Engenharia de Produção')
        self.perfil.save()
        resposta = self.client.get(reverse('fluxograma'), {'foco': 'INF0307'})
        opcoes = resposta.context['painel']['opcoes']
        self.assertEqual([d['codigo'] for d in opcoes], ['INF1006', 'INF1007', 'INF1026', 'INF1037'])
        inf1037 = next(d for d in opcoes if d['codigo'] == 'INF1037')
        self.assertTrue(inf1037['tem_requisitos'])
        self.assertTrue(inf1037['bloqueada'])
        self.assertIn('CTC4002', inf1037['pre_requisitos'])
        self.historico('CTC4002')
        self.historico('INF1006')
        self.historico('INF1007', HistoricoDisciplina.EM_CURSO)
        resposta = self.client.get(reverse('fluxograma'), {'foco': 'INF0307'})
        opcoes = {d['codigo']: d for d in resposta.context['painel']['opcoes']}
        self.assertFalse(opcoes['INF1037']['bloqueada'])
        self.assertTrue(opcoes['INF1006']['concluida'])
        self.assertFalse(opcoes['INF1006']['bloqueada'])
        self.assertTrue(opcoes['INF1007']['em_curso'])
        resposta = self.client.get(reverse('fluxograma'), {'foco': 'ENG0563'})
        quimica = next(d for d in resposta.context['painel']['opcoes'] if d['codigo'] == 'QUI4740')
        self.assertTrue(quimica['bloqueada'])
        self.assertIn('CTC (nivel 2)', quimica['pre_requisitos'])
        area = AreaNivelamento.objects.create(nome='Matemática')
        NivelamentoAluno.objects.create(perfil=self.perfil, area=area, nivel=2)
        resposta = self.client.get(reverse('fluxograma'), {'foco': 'ENG0563'})
        quimica = next(d for d in resposta.context['painel']['opcoes'] if d['codigo'] == 'QUI4740')
        self.assertFalse(quimica['bloqueada'])

    def test_disciplina_regular_nao_exibe_lista_de_optativas(self):
        resposta = self.client.get(reverse('fluxograma'), {'foco': 'MAT4161'})
        self.assertFalse(resposta.context['painel']['grupo_optativa'])
        self.assertEqual(resposta.context['painel']['opcoes'], [])
