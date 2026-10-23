# Cada classe abaixo que herda de models.Model se torna uma TABELA no
# banco; cada instancia dela e uma LINHA. Os atributos de classe (ex:
# "codigo = models.CharField(...)") sao as COLUNAS. O Django traduz tudo
# isso pra SQL automaticamente via migrations (makemigrations/migrate).
from django.db import models


class Curso(models.Model):
    codigo = models.CharField(max_length=3)
    nome = models.CharField(max_length=256)
    # DecimalField em vez de float/int: numero exato, sem erro de
    # arredondamento (max_digits=4, decimal_places=0 -> ex: 2024).
    ano_curriculo = models.DecimalField(max_digits=4, decimal_places=0)

    class Meta:
        # Nome real da tabela no banco. Sem isso o Django usaria um nome
        # automatico (ex: "fluxa_curso").
        db_table = "curso"


class Materia(models.Model):
    codigo = models.CharField(max_length=8)
    nome = models.CharField(max_length=256)
    creditos = models.IntegerField()
    horas = models.IntegerField()
    # null=True -> coluna pode ser NULL no banco.
    # blank=True -> campo pode ficar vazio em formularios/admin.
    # Os dois juntos = campo de verdade opcional (nem todo mundo tem
    # horas extras).
    horas_extras = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "materia"


class Professor(models.Model):
    nome = models.CharField(max_length=256)

    class Meta:
        db_table = "professor"


class Turma(models.Model):
    # ForeignKey = guarda o id de uma Materia nesta linha (coluna
    # "materia_id" por baixo); turma.materia resolve pro objeto inteiro.
    materia = models.ForeignKey(Materia, on_delete=models.PROTECT)
    codigo = models.CharField(max_length=3)
    periodo = models.DecimalField(max_digits=5, decimal_places=0)
    vagas_totais = models.IntegerField()
    vagas_ocupadas = models.IntegerField(default=0)
    # on_delete=PROTECT -> impede apagar o Professor se ele estiver
    # referenciado por alguma Turma (levanta erro em vez de apagar em
    # cascata ou deixar nulo).
    # null=True, blank=True -> turma pode nao ter professor definido ainda.
    professor = models.ForeignKey(Professor, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        db_table = "turma"


class Aluno(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.PROTECT)
    nome = models.CharField(max_length=256)
    numero_matricula = models.DecimalField(max_digits=7, decimal_places=0)
    # nullable: aluno pode ainda nao ter CR calculado (ex: calouro).
    cr = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)

    class Meta:
        db_table = "aluno"


class Grade(models.Model):
    # A grade curricular de um aluno especifico.
    nome = models.CharField(max_length=80)
    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT)

    class Meta:
        db_table = "grade"


class GrupoRequisito(models.Model):
    """
    Um grupo de requisitos representa um conjunto de ALTERNATIVAS (OU)
    que, juntas, atendem a uma exigencia de 'materia'. Cada linha de
    Requisito ligada a este grupo e uma alternativa valida; basta
    cumprir uma delas.

    Se 'materia' tiver mais de um grupo, as exigencias dos grupos se
    somam (E entre grupos, OU dentro de cada grupo). Exemplo: se
    ENG4021 exige (ENG1000 ou ENG1127 ou ENG4010) e tambem
    (EMP1320 e (INF1037 ou INF1026 ou INF1007)), isso vira 3 grupos:
      - grupo 1 (tipo R): alternativas ENG1000, ENG1127, ENG4010
      - grupo 2 (tipo C): alternativa unica EMP1320
      - grupo 3 (tipo C): alternativas INF1037, INF1026, INF1007
    """
    # "Enum" dentro de um CharField: a coluna continua sendo CHAR(1)
    # guardando "R"/"C", mas 'choices' faz o Django mostrar rotulos
    # legiveis no admin/formularios e validar que só esses valores
    # sao aceitos.
    TIPO_REQUISITO = "R"
    TIPO_COREQUISITO = "C"
    TIPO_REQUISITO_CHOICES = [
        (TIPO_REQUISITO, "Requisito (pre-requisito)"),
        (TIPO_COREQUISITO, "Co-requisito"),
    ]

    tipo_requisito = models.CharField(max_length=1, choices=TIPO_REQUISITO_CHOICES)
    # A materia que TEM a exigencia (ex: ENG4021 no exemplo acima).
    materia = models.ForeignKey(Materia, on_delete=models.PROTECT)

    class Meta:
        db_table = "grupo_requisito"


class Historico(models.Model):
    # Um registro de "aluno cursou/cursa materia X, na turma Y, em tal
    # periodo". cursando/aprovado/nota juntos contam a situacao atual.
    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT)
    materia = models.ForeignKey(Materia, on_delete=models.PROTECT)
    periodo = models.DecimalField(max_digits=5, decimal_places=0)
    cursando = models.BooleanField(default=False)
    turma = models.ForeignKey(Turma, on_delete=models.PROTECT)
    aprovado = models.BooleanField(default=False)
    # nota fica None enquanto o aluno ainda esta cursando (sem nota final).
    nota = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    numero_de_oportunidades = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "historico"


class HorarioTurma(models.Model):
    # Uma turma pode ter varios horarios (ex: seg e qua); por isso isso
    # e uma tabela separada em vez de colunas na Turma.
    turma = models.ForeignKey(Turma, on_delete=models.PROTECT)
    dia_semana = models.IntegerField()
    hora_inicio = models.TimeField()
    hora_fim = models.TimeField()

    class Meta:
        db_table = "horario_turma"


class Requisito(models.Model):
    """
    Uma alternativa dentro de um GrupoRequisito. 'materia' aqui e a
    materia que, se cumprida, satisfaz o grupo (uma das opcoes do OU).
    """
    materia = models.ForeignKey(Materia, on_delete=models.PROTECT)
    grupo_requisito = models.ForeignKey(GrupoRequisito, on_delete=models.PROTECT)

    class Meta:
        db_table = "requisito"


class TurmaGrade(models.Model):
    # Vincula uma turma escolhida a grade curricular de um aluno
    # (tabela de associacao muitos-pra-muitos feita a mao, em vez de
    # ManyToManyField, pra poder ter metadados/consultas proprias depois).
    grade = models.ForeignKey(Grade, on_delete=models.PROTECT)
    turma = models.ForeignKey(Turma, on_delete=models.PROTECT)

    class Meta:
        db_table = "turma_grade"
