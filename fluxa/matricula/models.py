from django.db import models


from django.conf import settings


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


class Disciplina(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=200)
    periodo = models.IntegerField(null=True, blank=True)
    creditos = models.IntegerField()
    creditos_minimos = models.IntegerField(default=0)

    def __str__(self):
        return self.nome

    pre_requisitos = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name='dependentes'
    )

    co_requisitos = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name='associadas'
    )




class CreditosAluno(models.Model):
    aluno = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.CASCADE
    )
    concluida = models.BooleanField(default=False)

    class Meta:
        unique_together = ('aluno', 'disciplina')

    def __str__(self):
        return self.disciplina.nome


class GrauAluno(models.Model):
    aluno = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.CASCADE
    )
    turma = models.CharField(max_length=10, default='-')
    periodo_letivo = models.CharField(max_length=10, default='2026.2')
    g1 = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    g2 = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    g3 = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    media = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    situacao = models.CharField(max_length=30, default='Em curso')

    def __str__(self):
        return self.disciplina.nome

   
