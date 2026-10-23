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


class Disciplina(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=200)
    periodo = models.IntegerField(null=True, blank=True)
    creditos = models.IntegerField()

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

    creditos_minimos = models.IntegerField(default=0)

    def __str__(self):
        return self.nome
