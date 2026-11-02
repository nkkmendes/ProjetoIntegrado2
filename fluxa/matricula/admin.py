from django.contrib import admin

from .models import (
    CalendarioMatricula,
    PlanejamentoSalvo,
    NivelamentoSalvo,
    Disciplina,
    GrupoPreRequisito
)

@admin.register(CalendarioMatricula)
class CalendarioMatriculaAdmin(admin.ModelAdmin):
    list_display = (
        'periodo',
        'inicio_matricula',
        'fim_matricula',
        'inicio_aulas'
    )
    search_fields = ('periodo',)

@admin.register(PlanejamentoSalvo)
class PlanejamentoSalvoAdmin(admin.ModelAdmin):
    list_display = (
        'nome',
        'usuario',
        'periodo'
    )
    search_fields = (
        'nome',
        'usuario__username'
    )
    list_filter = ('periodo',)

@admin.register(NivelamentoSalvo)
class NivelamentoSalvoAdmin(admin.ModelAdmin):
    list_display = (
        'nome',
        'area',
        'resultado'
    )
    search_fields = ('nome', 'area')
    list_filter = ('area',)

class GrupoPreRequisitoInline(admin.TabularInline):
    model = GrupoPreRequisito
    fk_name = 'disciplina'
    extra = 0
    filter_horizontal = ('disciplinas',)

@admin.register(Disciplina)
class DisciplinaAdmin(admin.ModelAdmin):
    list_display = (
        'codigo',
        'nome',
        'creditos'
    )
    search_fields = ('codigo', 'nome')
    filter_horizontal = (
        'co_requisitos',
    )
    inlines = [GrupoPreRequisitoInline]