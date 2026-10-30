from django.conf import settings
from django.db import models

class PlanejamentoSalvo(models.Model):
    nome = models.CharField(max_length=100)
    periodo = models.IntegerField()
    disciplinas = models.TextField()

class SimulacaoSalva(models.Model):
    nome = models.CharField(max_length=100)
    disciplinas = models.TextField()

class NivelamentoSalvo(models.Model):
    nome = models.CharField(max_length=100)
    area = models.CharField(max_length=100)
    resultado = models.CharField(max_length=100)

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
    curso = models.ForeignKey(
        Curso,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
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
        codigos = ' + '.join(d.codigo for d in self.disciplinas.order_by('codigo'))
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


class DisciplinaCursada(models.Model):
    CONCLUIDA = 'concluida'
    EM_CURSO = 'em_curso'
    STATUS = [
        (CONCLUIDA, 'Concluída'),
        (EM_CURSO, 'Em curso'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='disciplinas_cursadas'
    )
    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.CASCADE,
        related_name='cursadas'
    )
    status = models.CharField(max_length=10, choices=STATUS, default=CONCLUIDA)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'disciplina'],
                name='disciplina_cursada_unica_por_aluno'
            )
        ]

    def __str__(self):
        return f'{self.user} — {self.disciplina.codigo} ({self.get_status_display()})'