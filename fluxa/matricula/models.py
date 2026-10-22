from django.db import models


class CalendarioMatricula(models.Model):
    periodo = models.CharField(max_length=10)
    inicio_matricula = models.DateField()
    fim_matricula = models.DateField()
    inicio_aulas = models.DateField()
    inicio_ajuste = models.DateField()
    fim_ajuste = models.DateField()