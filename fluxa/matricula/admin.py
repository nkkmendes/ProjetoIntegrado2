from django.contrib import admin

from .models import (
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


# Inline = ao abrir o "pai" no admin (Turma / GrupoRequisito), os
# registros relacionados abaixo aparecem editaveis na mesma pagina,
# como uma tabela dentro do formulario.
class RequisitoInline(admin.TabularInline):
    model = Requisito
    extra = 1  # quantas linhas vazias extras mostrar pra adicionar novas


class HorarioTurmaInline(admin.TabularInline):
    model = HorarioTurma
    extra = 1


# @admin.register(Curso) e um decorator: equivale a escrever, no final
# do arquivo, admin.site.register(Curso, CursoAdmin). A classe abaixo
# nunca e instanciada por nos - o Django só le seus atributos de classe
# (list_display, search_fields, etc.) pra montar a tela.
@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "ano_curriculo")  # colunas da listagem
    search_fields = ("codigo", "nome")                   # habilita a busca
    list_filter = ("ano_curriculo",)                      # filtro na lateral
    ordering = ("codigo",)


@admin.register(Materia)
class MateriaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "creditos", "horas", "horas_extras")
    search_fields = ("codigo", "nome")
    ordering = ("codigo",)


@admin.register(Professor)
class ProfessorAdmin(admin.ModelAdmin):
    list_display = ("nome",)
    search_fields = ("nome",)
    ordering = ("nome",)


@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ("materia", "codigo", "periodo", "professor", "vagas_ocupadas", "vagas_totais")
    list_filter = ("periodo",)
    search_fields = ("codigo", "materia__codigo", "materia__nome")
    # Troca o <select> (que ficaria gigante com muitos registros) por um
    # campo de busca via AJAX. Só funciona porque MateriaAdmin e
    # ProfessorAdmin, acima, tem search_fields definido.
    autocomplete_fields = ("materia", "professor")
    inlines = [HorarioTurmaInline]


@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    list_display = ("numero_matricula", "nome", "curso", "cr")
    search_fields = ("nome", "numero_matricula")
    list_filter = ("curso",)
    autocomplete_fields = ("curso",)


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ("nome", "aluno")
    search_fields = ("nome", "aluno__nome")
    autocomplete_fields = ("aluno",)


@admin.register(GrupoRequisito)
class GrupoRequisitoAdmin(admin.ModelAdmin):
    list_display = ("materia", "tipo_requisito")
    list_filter = ("tipo_requisito",)
    search_fields = ("materia__codigo", "materia__nome")
    autocomplete_fields = ("materia",)
    # Edita as alternativas (Requisito) do grupo direto nesta mesma tela.
    inlines = [RequisitoInline]


@admin.register(Historico)
class HistoricoAdmin(admin.ModelAdmin):
    list_display = ("aluno", "materia", "turma", "periodo", "cursando", "aprovado", "nota")
    list_filter = ("cursando", "aprovado", "periodo")
    search_fields = ("aluno__nome", "materia__codigo", "materia__nome")
    autocomplete_fields = ("aluno", "materia", "turma")


@admin.register(HorarioTurma)
class HorarioTurmaAdmin(admin.ModelAdmin):
    list_display = ("turma", "dia_semana", "hora_inicio", "hora_fim")
    list_filter = ("dia_semana",)
    autocomplete_fields = ("turma",)


@admin.register(Requisito)
class RequisitoAdmin(admin.ModelAdmin):
    list_display = ("grupo_requisito", "materia")
    autocomplete_fields = ("materia", "grupo_requisito")


@admin.register(TurmaGrade)
class TurmaGradeAdmin(admin.ModelAdmin):
    list_display = ("grade", "turma")
    autocomplete_fields = ("grade", "turma")



from .models import (
    CalendarioMatricula,
    PlanejamentoSalvo,
    NivelamentoSalvo,
    Disciplina,
    DisciplinaProducao
)


# TELA DE INICIO
@admin.register(CalendarioMatricula)
class CalendarioMatriculaAdmin(admin.ModelAdmin):
    list_display = (
        'periodo',
        'inicio_matricula',
        'fim_matricula',
        'inicio_aulas'
    )
    search_fields = ('periodo',)


# TELA DE PLANEJAMENTO
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


# TELA DE NIVELAMENTO
@admin.register(NivelamentoSalvo)
class NivelamentoSalvoAdmin(admin.ModelAdmin):
    list_display = (
        'nome',
        'area',
        'resultado'
    )
    search_fields = ('nome', 'area')
    list_filter = ('area',)


# FLUXOGRAMA DE ENGENHARIA DE COMPUTACAO
@admin.register(Disciplina)
class DisciplinaAdmin(admin.ModelAdmin):
    list_display = (
        'codigo',
        'nome',
        'periodo',
        'creditos'
    )
    search_fields = ('codigo', 'nome')
    list_filter = ('periodo',)
    filter_horizontal = (
        'pre_requisitos',
        'co_requisitos'
    )


# FLUXOGRAMA DE ENGENHARIA DE PRODUCAO
@admin.register(DisciplinaProducao)
class DisciplinaProducaoAdmin(admin.ModelAdmin):
    list_display = (
        'codigo',
        'nome',
        'periodo',
        'creditos'
    )
    search_fields = ('codigo', 'nome')
    list_filter = ('periodo',)
    filter_horizontal = (
        'pre_requisitos',
        'co_requisitos'
    )
