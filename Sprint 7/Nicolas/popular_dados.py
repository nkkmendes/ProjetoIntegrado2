"""
Comando de management para popular o banco com dados fake, usando a
biblioteca Faker. Util para desenvolvimento/testes do trabalho de escola.

Uso:
    python manage.py popular_dados
    python manage.py popular_dados --clear
    python manage.py popular_dados --cursos 5 --materias 20 --alunos 60
"""
import random
from datetime import time

from django.core.management.base import BaseCommand
from django.db import transaction

from faker import Faker

from fluxa.models import (
    Aluno,
    Curso,
    Grade,
    GrupoRequisito,
    Historico,
    HorarioTurma,
    Materia,
    Professor,
    Requisito,
    Turma,
    TurmaGrade,
)

# Instancia unica do gerador de dados fake, com locale pt_BR (nomes
# brasileiros em vez de nomes em ingles por padrao).
fake = Faker("pt_BR")

# Pool fixo de cursos reais pra sortear - evita gerar nomes de curso
# sem sentido via Faker.
CURSOS_BASE = [
    ("CIC", "Ciencia da Computacao"),
    ("ENG", "Engenharia de Software"),
    ("ADM", "Administracao"),
    ("DIR", "Direito"),
    ("MED", "Medicina"),
    ("ARQ", "Arquitetura e Urbanismo"),
]


# Toda classe "Command" dentro de management/commands/ vira um comando
# novo de "python manage.py <nome_do_arquivo>" - e por isso que este
# arquivo se chama popular_dados.py.
class Command(BaseCommand):
    # Texto mostrado em "python manage.py help popular_dados".
    help = "Popula o banco com dados fake (cursos, materias, professores, turmas, alunos, historico, etc.)."

    def add_arguments(self, parser):
        # Cada add_argument vira uma opcao de linha de comando (ex:
        # --cursos 6), igual argparse puro - BaseCommand usa argparse
        # por baixo.
        parser.add_argument("--clear", action="store_true", help="Remove todos os dados das tabelas da app antes de popular.")
        parser.add_argument("--cursos", type=int, default=4, help="Quantidade de cursos a criar (max 6). Padrao: 4.")
        parser.add_argument("--materias", type=int, default=15, help="Quantidade de materias a criar. Padrao: 15.")
        parser.add_argument("--professores", type=int, default=8, help="Quantidade de professores a criar. Padrao: 8.")
        parser.add_argument("--alunos", type=int, default=30, help="Quantidade de alunos a criar. Padrao: 30.")
        parser.add_argument("--seed", type=int, default=None, help="Seed do random/Faker, para resultados reproduziveis.")

    def handle(self, *args, **options):
        # Ponto de entrada do comando - e o que roda quando voce chama
        # "python manage.py popular_dados ...". 'options' tem os valores
        # de cada --argumento definido acima.
        if options["seed"] is not None:
            # Com a mesma seed, random e Faker sempre sorteiam a mesma
            # sequencia - util pra reproduzir o mesmo resultado em testes.
            random.seed(options["seed"])
            Faker.seed(options["seed"])

        if options["clear"]:
            self._limpar_dados()

        # transaction.atomic(): tudo dentro do "with" ou vira UM commit
        # so no banco, ou nada vira (se algo der erro no meio, desfaz
        # tudo). Evita ficar com dados parciais/inconsistentes.
        with transaction.atomic():
            cursos = self._criar_cursos(options["cursos"])
            materias = self._criar_materias(options["materias"])
            professores = self._criar_professores(options["professores"])
            turmas = self._criar_turmas(materias, professores)
            self._criar_horarios(turmas)
            alunos = self._criar_alunos(cursos, options["alunos"])
            grades = self._criar_grades(alunos)
            self._criar_grades_turmas(grades, turmas)
            self._criar_requisitos(materias)
            self._criar_historico(alunos, materias, turmas)

        # self.stdout/self.style sao os jeitos "certos" de uma Command
        # imprimir no terminal (em vez de print()) - self.style.SUCCESS
        # colore o texto de verde quando o terminal suporta.
        self.stdout.write(self.style.SUCCESS(
            f"Dados criados: {len(cursos)} cursos, {len(materias)} materias, "
            f"{len(professores)} professores, {len(turmas)} turmas, {len(alunos)} alunos."
        ))

    def _limpar_dados(self):
        self.stdout.write("Limpando dados existentes...")
        # Ordem inversa de dependencia por causa do on_delete=PROTECT:
        # precisa apagar quem APONTA pra uma tabela antes de apagar a
        # tabela apontada (ex: Historico antes de Aluno), senao o
        # PROTECT bloqueia o delete.
        TurmaGrade.objects.all().delete()
        Historico.objects.all().delete()
        Requisito.objects.all().delete()
        GrupoRequisito.objects.all().delete()
        Grade.objects.all().delete()
        HorarioTurma.objects.all().delete()
        Turma.objects.all().delete()
        Aluno.objects.all().delete()
        Professor.objects.all().delete()
        Materia.objects.all().delete()
        Curso.objects.all().delete()

    def _criar_cursos(self, quantidade):
        # Nunca cria mais cursos do que o pool fixo tem (senao
        # random.sample levantaria erro pedindo mais itens do que existem).
        quantidade = min(quantidade, len(CURSOS_BASE))
        cursos = []
        for codigo, nome in random.sample(CURSOS_BASE, quantidade):
            cursos.append(Curso.objects.create(
                codigo=codigo,
                nome=nome,
                ano_curriculo=random.choice([2018, 2020, 2022, 2024]),
            ))
        return cursos

    def _criar_materias(self, quantidade):
        materias = []
        for i in range(quantidade):
            # Codigo sequencial (MAT000, MAT001...) garante que nunca
            # se repete, sem precisar checar unicidade manualmente.
            codigo = f"MAT{i:03d}"[:8]
            materias.append(Materia.objects.create(
                codigo=codigo,
                # fake.sentence() gera uma frase fake; vira "nome" de
                # materia removendo o ponto final e capitalizando.
                nome=fake.sentence(nb_words=3).rstrip(".").title(),
                creditos=random.choice([2, 4, 6]),
                horas=random.choice([30, 60, 90]),
                horas_extras=random.choice([None, 0, 15, 30]),
            ))
        return materias

    def _criar_professores(self, quantidade):
        return [
            Professor.objects.create(nome=fake.name())
            for _ in range(quantidade)
        ]

    def _criar_turmas(self, materias, professores):
        turmas = []
        periodos = [20241, 20242, 20251, 20252]  # ano + semestre (ex: 2024/1)
        for materia in materias:
            # Cada materia pode ganhar 1 ou 2 turmas (codigos "A"/"B"/"C").
            for codigo in random.sample(["A", "B", "C"], k=random.randint(1, 2)):
                vagas_totais = random.choice([30, 40, 50])
                turmas.append(Turma.objects.create(
                    materia=materia,
                    codigo=codigo,
                    periodo=random.choice(periodos),
                    vagas_totais=vagas_totais,
                    vagas_ocupadas=random.randint(0, vagas_totais),
                    # Pode nao ter professor sorteado se a lista vier vazia
                    # (ex: --professores 0) - campo e nullable no model.
                    professor=random.choice(professores) if professores else None,
                ))
        return turmas

    def _criar_horarios(self, turmas):
        # Blocos de horario tipicos de faculdade (manha/tarde/noite).
        blocos = [(time(8, 0), time(10, 0)), (time(10, 0), time(12, 0)),
                  (time(14, 0), time(16, 0)), (time(19, 0), time(21, 0))]
        for turma in turmas:
            # dia_semana: 1=segunda ... 5=sexta (sem aula no fim de semana
            # neste gerador). Cada turma ganha 1 ou 2 dias de aula.
            for dia in random.sample(range(1, 6), k=random.randint(1, 2)):
                inicio, fim = random.choice(blocos)
                HorarioTurma.objects.create(
                    turma=turma,
                    dia_semana=dia,
                    hora_inicio=inicio,
                    hora_fim=fim,
                )

    def _criar_alunos(self, cursos, quantidade):
        if not cursos:
            # Sem curso nenhum, nao tem como criar aluno (curso e
            # obrigatorio no model) - sai mais cedo em vez de dar erro.
            return []
        alunos = []
        matriculas_usadas = set()
        for _ in range(quantidade):
            # Sorteia numero de matricula de 7 digitos garantindo que
            # nao repete dentro desta execucao (nao ha unique=True no
            # model, mas repetir seria estranho nos dados fake).
            matricula = random.randint(1000000, 9999999)
            while matricula in matriculas_usadas:
                matricula = random.randint(1000000, 9999999)
            matriculas_usadas.add(matricula)
            alunos.append(Aluno.objects.create(
                curso=random.choice(cursos),
                nome=fake.name(),
                numero_matricula=matricula,
                # 20% dos alunos ficam sem CR ainda (ex: calouros).
                cr=round(random.uniform(0, 10), 1) if random.random() < 0.8 else None,
            ))
        return alunos

    def _criar_grades(self, alunos):
        # Uma Grade por aluno, com nome derivado do primeiro nome dele.
        return [
            Grade.objects.create(nome=f"Grade de {aluno.nome.split()[0]}", aluno=aluno)
            for aluno in alunos
        ]

    def _criar_grades_turmas(self, grades, turmas):
        if not turmas:
            return
        # Cada grade "pega" entre 3 e 6 turmas aleatorias, sem repetir
        # dentro da mesma grade (random.sample nao repete elementos).
        for grade in grades:
            for turma in random.sample(turmas, k=min(random.randint(3, 6), len(turmas))):
                TurmaGrade.objects.create(grade=grade, turma=turma)

    def _criar_requisitos(self, materias):
        """
        Cada materia pode ter varios grupos de requisito (E entre eles);
        dentro de cada grupo, varias materias alternativas que se
        substituem entre si (OU). Ex.: ENG4021 exigindo
        (ENG1000 ou ENG1127 ou ENG4010) e tambem
        (EMP1320) e (INF1037 ou INF1026 ou INF1007)
        vira 3 GrupoRequisito, cada um com suas alternativas em Requisito.
        """
        if len(materias) < 2:
            # Precisa de pelo menos 2 materias pra uma exigir a outra.
            return
        for materia in materias:
            # Qualquer outra materia pode ser "candidata" a alternativa
            # de requisito desta (nunca ela mesma).
            candidatas = [m for m in materias if m != materia]
            # Sorteia quantos GRUPOS esta materia vai ter: metade das
            # vezes nenhum, senao 1 ou 2 (pesos 50/35/15%).
            quantidade_grupos = random.choices([0, 1, 2], weights=[50, 35, 15])[0]
            for _ in range(quantidade_grupos):
                if not candidatas:
                    break
                grupo = GrupoRequisito.objects.create(
                    tipo_requisito=random.choice([
                        GrupoRequisito.TIPO_REQUISITO,
                        GrupoRequisito.TIPO_COREQUISITO,
                    ]),
                    materia=materia,
                )
                # Dentro do grupo, 1 a 3 alternativas que valem como OU
                # entre si (qualquer uma cumpre a exigencia do grupo).
                quantidade_alternativas = min(random.randint(1, 3), len(candidatas))
                for alternativa in random.sample(candidatas, k=quantidade_alternativas):
                    Requisito.objects.create(materia=alternativa, grupo_requisito=grupo)

    def _criar_historico(self, alunos, materias, turmas):
        if not turmas:
            return
        for aluno in alunos:
            # Cada aluno "cursa/cursou" entre 2 e 5 materias sorteadas.
            for materia in random.sample(materias, k=min(random.randint(2, 5), len(materias))):
                # So pode registrar historico numa turma que seja
                # realmente dessa materia (consistencia com o model).
                turmas_da_materia = [t for t in turmas if t.materia_id == materia.id]
                if not turmas_da_materia:
                    continue
                turma = random.choice(turmas_da_materia)
                aprovado = random.random() < 0.7         # 70% de chance de aprovado
                # So fica "cursando" se nao foi aprovado e sorteou true
                # de novo (30% desses casos) - aprovado e cursando nunca
                # sao True ao mesmo tempo.
                cursando = not aprovado and random.random() < 0.3
                Historico.objects.create(
                    aluno=aluno,
                    materia=materia,
                    periodo=turma.periodo,
                    cursando=cursando,
                    turma=turma,
                    aprovado=aprovado,
                    # Sem nota final enquanto ainda esta cursando.
                    nota=None if cursando else round(random.uniform(0, 10), 1),
                    numero_de_oportunidades=random.randint(1, 3),
                )
