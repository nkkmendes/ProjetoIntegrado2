from django.contrib import admin
from .models import (
    Curso, Disciplina, GrupoPreRequisito, PerfilAluno, DisciplinaCursada,
    PlanejamentoSalvo, SimulacaoSalva, NivelamentoSalvo, CalendarioMatricula,
)


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)


class GrupoPreRequisitoInline(admin.TabularInline):
    model = GrupoPreRequisito
    fk_name = 'disciplina'
    extra = 0
    filter_horizontal = ('disciplinas',)


@admin.register(Disciplina)
class DisciplinaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'creditos', 'creditos_minimos', 'curso')
    list_filter = ('curso',)
    search_fields = ('codigo', 'nome')
    filter_horizontal = ('co_requisitos',)
    inlines = [GrupoPreRequisitoInline]


@admin.register(GrupoPreRequisito)
class GrupoPreRequisitoAdmin(admin.ModelAdmin):
    list_display = ('__str__',)
    search_fields = ('disciplina__codigo',)
    filter_horizontal = ('disciplinas',)


@admin.register(PerfilAluno)
class PerfilAlunoAdmin(admin.ModelAdmin):
    list_display = ('user', 'curso')
    list_filter = ('curso',)


@admin.register(DisciplinaCursada)
class DisciplinaCursadaAdmin(admin.ModelAdmin):
    list_display = ('user', 'disciplina', 'status')
    list_filter = ('status',)


admin.site.register(CalendarioMatricula)
admin.site.register(PlanejamentoSalvo)
admin.site.register(SimulacaoSalva)
admin.site.register(NivelamentoSalvo)