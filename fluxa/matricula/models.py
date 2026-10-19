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
