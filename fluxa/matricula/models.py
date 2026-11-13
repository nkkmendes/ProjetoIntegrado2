
from django.conf import settings
from django.db import models


class PlanejamentoSalvo(models.Model):
    """Uma grade de horários guardada pelo aluno: um conjunto de turmas reais
    do micro-horário, com um nome. É criada no Simulador ("Salvar em
    planejamento") e pode ser reaberta lá para edição."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='planejamentos'
    )
    nome = models.CharField(max_length=100)
    periodo_letivo = models.CharField(max_length=10, blank=True, default='')
    turmas = models.ManyToManyField(
        'Turma',
        blank=True,
        related_name='planejamentos'
    )
    horarios_salvos = models.JSONField(
        default=list,
        blank=True
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-atualizado_em']
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'nome'],
                name='planejamento_nome_unico_por_aluno'
            )
        ]

    def __str__(self):
        return f'{self.nome} ({self.usuario})'


class CalendarioMatricula(models.Model):
    periodo = models.CharField(max_length=10)
    inicio_matricula = models.DateField()
    fim_matricula = models.DateField()
    inicio_aulas = models.DateField()
    inicio_ajuste = models.DateField()
    fim_ajuste = models.DateField()


class CursoManager(models.Manager):
    def get_by_natural_key(self, nome):
        return self.get(nome=nome)


class Curso(models.Model):
    nome = models.CharField(max_length=100, unique=True)

    objects = CursoManager()

    def natural_key(self):
        return (self.nome,)

    def __str__(self):
        return self.nome


class DisciplinaManager(models.Manager):
    def get_by_natural_key(self, codigo):
        return self.get(codigo=codigo)


class Disciplina(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=200)
    creditos = models.IntegerField()
    cursos = models.ManyToManyField(
        Curso,
        blank=True,
        related_name='disciplinas'
    )

    co_requisitos = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name='associadas'
    )

    creditos_minimos = models.IntegerField(default=0)

    objects = DisciplinaManager()

    def natural_key(self):
        return (self.codigo,)

    def __str__(self):
        return self.nome

    @property
    def pre_requisitos(self):
        return Disciplina.objects.filter(
            usada_em_grupos__disciplina=self
        ).distinct().order_by('codigo')

    @property
    def dependentes(self):
        return Disciplina.objects.filter(
            grupos_pre_requisito__disciplinas=self
        ).distinct().order_by('codigo')


class GrupoPreRequisito(models.Model):
    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.CASCADE,
        related_name='grupos_pre_requisito'
    )
    disciplinas = models.ManyToManyField(
        Disciplina,
        related_name='usada_em_grupos'
    )

    def __str__(self):
        codigos = ' + '.join(
            d.codigo for d in self.disciplinas.order_by('codigo')
        )
        return f'{self.disciplina.codigo} ← {codigos}'


class PerfilAluno(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='perfil_aluno'
    )
    curso = models.ForeignKey(
        Curso,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='alunos'
    )

    def __str__(self):
        return str(self.user)


class HistoricoDisciplina(models.Model):
    """Uma disciplina que o aluno já cursou (ou está cursando), com as notas.

    Substitui DisciplinaCursada, CreditosAluno e GrauAluno: o mesmo registro
    diz se foi concluída, em que período, e com quais graus.
    """

    CONCLUIDA = 'concluida'
    EM_CURSO = 'em_curso'
    REPROVADA = 'reprovada'

    STATUS = [
        (CONCLUIDA, 'Concluída'),
        (EM_CURSO, 'Em curso'),
        (REPROVADA, 'Reprovada'),
    ]

    perfil = models.ForeignKey(
        PerfilAluno,
        on_delete=models.CASCADE,
        related_name='historico'
    )
    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.CASCADE,
        related_name='historico'
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS,
        default=CONCLUIDA
    )
    periodo_letivo = models.CharField(max_length=10, blank=True, default='')
    turma = models.CharField(max_length=10, blank=True, default='')
    g1 = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )
    g2 = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )
    g3 = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )
    media = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )

    class Meta:
        ordering = ['-periodo_letivo', 'disciplina__codigo']
        constraints = [
            models.UniqueConstraint(
                fields=['perfil', 'disciplina'],
                name='historico_unico_por_aluno_e_disciplina'
            )
        ]

    @property
    def tem_notas(self):
        return any(
            n is not None
            for n in (self.g1, self.g2, self.g3, self.media)
        )

    def __str__(self):
        return (
            f'{self.perfil} — {self.disciplina.codigo} '
            f'({self.get_status_display()})'
        )


class AreaNivelamentoManager(models.Manager):
    def get_by_natural_key(self, nome):
        return self.get(nome=nome)


class AreaNivelamento(models.Model):
    """Uma área em que o aluno faz nivelamento (ex.: Matemática, Inglês)."""

    nome = models.CharField(max_length=100, unique=True)

    objects = AreaNivelamentoManager()

    class Meta:
        ordering = ['nome']

    def natural_key(self):
        return (self.nome,)

    def __str__(self):
        return self.nome


class NivelamentoAluno(models.Model):
    """O nível numérico do aluno numa área. Sem registro = não informado."""

    perfil = models.ForeignKey(
        PerfilAluno,
        on_delete=models.CASCADE,
        related_name='niveis'
    )
    area = models.ForeignKey(
        AreaNivelamento,
        on_delete=models.CASCADE,
        related_name='niveis_de_alunos'
    )
    nivel = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ['area__nome']
        constraints = [
            models.UniqueConstraint(
                fields=['perfil', 'area'],
                name='nivel_unico_por_aluno_e_area'
            )
        ]

    def __str__(self):
        return f'{self.perfil} — {self.area}: nível {self.nivel}'


class RequisitoNivelamento(models.Model):
    """Nível mínimo numa área para poder cursar uma disciplina.

    Vale para todos os cursos, como os pré-requisitos.
    """

    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.CASCADE,
        related_name='requisitos_nivelamento'
    )
    area = models.ForeignKey(
        AreaNivelamento,
        on_delete=models.CASCADE,
        related_name='requisitos'
    )
    nivel_minimo = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ['disciplina__codigo', 'area__nome']
        constraints = [
            models.UniqueConstraint(
                fields=['disciplina', 'area'],
                name='requisito_nivel_unico_por_disciplina_e_area'
            )
        ]

    def __str__(self):
        return (
            f'{self.disciplina.codigo} exige '
            f'{self.area} ≥ {self.nivel_minimo}'
        )


# NOVOS MODELOS - SPRINT 9

class Turma(models.Model):
    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.CASCADE,
        related_name='turmas'
    )
    codigo = models.CharField(max_length=20)
    periodo_letivo = models.CharField(max_length=10)
    professor = models.CharField(max_length=150, blank=True)
    vagas = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['disciplina', 'codigo', 'periodo_letivo'],
                name='turma_unica_por_disciplina_periodo'
            )
        ]

    def __str__(self):
        return (
            f'{self.disciplina.codigo} - '
            f'Turma {self.codigo} ({self.periodo_letivo})'
        )


class HorarioTurma(models.Model):
    DIAS = [
        (0, 'Segunda-feira'),
        (1, 'Terça-feira'),
        (2, 'Quarta-feira'),
        (3, 'Quinta-feira'),
        (4, 'Sexta-feira'),
        (5, 'Sábado'),
    ]

    turma = models.ForeignKey(
        Turma,
        on_delete=models.CASCADE,
        related_name='horarios'
    )
    dia_semana = models.IntegerField(choices=DIAS)
    hora_inicio = models.TimeField()
    hora_fim = models.TimeField()
    sala = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return (
            f'{self.turma} - '
            f'{self.get_dia_semana_display()} '
            f'{self.hora_inicio} às {self.hora_fim}'
        )
