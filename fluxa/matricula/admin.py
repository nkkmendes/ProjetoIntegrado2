from django.contrib import admin, messages

from .importacao_engenharias import importar_grades

from .models import (
    AreaNivelamento,
    CalendarioMatricula,
    Curso,
    Disciplina,
    GrupoPreRequisito,
    HistoricoDisciplina,
    NivelamentoAluno,
    PerfilAluno,
    PlanejamentoSalvo,
    RequisitoNivelamento,
    Turma,
)


# INÍCIO
@admin.register(CalendarioMatricula)
class CalendarioMatriculaAdmin(admin.ModelAdmin):
    list_display = (
        'periodo',
        'inicio_matricula',
        'fim_matricula',
        'inicio_aulas'
    )
    search_fields = ('periodo',)


# PLANEJAMENTO (grades salvas pelos alunos)
@admin.register(PlanejamentoSalvo)
class PlanejamentoSalvoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'usuario', 'periodo_letivo', 'atualizado_em')
    search_fields = ('nome', 'usuario__username')
    list_filter = ('periodo_letivo',)
    filter_horizontal = ('turmas',)


@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ('disciplina', 'codigo', 'periodo_letivo', 'professor', 'vagas')
    search_fields = ('disciplina__codigo', 'disciplina__nome', 'professor')
    list_filter = ('periodo_letivo',)


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'total_disciplinas')
    search_fields = ('nome',)
    actions = ['importar_grades_das_engenharias']

    @admin.display(description='Disciplinas')
    def total_disciplinas(self, curso):
        return curso.disciplinas.count()

    @admin.action(description='Importar as grades da planilha (sem apagar nada)')
    def importar_grades_das_engenharias(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(
                request,
                'Somente o administrador principal pode importar.',
                level=messages.ERROR,
            )
            return
        try:
            r = importar_grades()
        except (OSError, ValueError, ImportError) as erro:
            self.message_user(request, f'Erro ao importar: {erro}', level=messages.ERROR)
            return
        self.message_user(
            request,
            f"Importação concluída: {r['disciplinas_novas']} disciplinas novas, "
            f"{r['vinculos_novos']} vínculos com cursos, "
            f"{r['pre_requisitos_novos']} pré-requisitos novos.",
            level=messages.SUCCESS,
        )
        if r['pre_requisitos_diferentes'] or r['dados_diferentes']:
            self.message_user(
                request,
                'Há diferenças entre o banco e a planilha; os valores do banco foram '
                'mantidos. Rode "python manage.py importar_dados" para ver a lista.',
                level=messages.WARNING,
            )


class GrupoPreRequisitoInline(admin.TabularInline):
    model = GrupoPreRequisito
    fk_name = 'disciplina'
    extra = 0
    filter_horizontal = ('disciplinas',)


class RequisitoNivelamentoInline(admin.TabularInline):
    model = RequisitoNivelamento
    extra = 0


@admin.register(Disciplina)
class DisciplinaAdmin(admin.ModelAdmin):
    list_display = (
        'codigo',
        'nome',
        'creditos',
        'lista_cursos',
    )
    search_fields = ('codigo', 'nome')
    list_filter = ('cursos',)
    filter_horizontal = (
        'cursos',
        'co_requisitos',
    )
    inlines = [GrupoPreRequisitoInline, RequisitoNivelamentoInline]

    @admin.display(description='Cursos')
    def lista_cursos(self, disciplina):
        return ', '.join(c.nome for c in disciplina.cursos.all())

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('cursos')


# NIVELAMENTO
@admin.register(AreaNivelamento)
class AreaNivelamentoAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)


# ALUNOS
class HistoricoDisciplinaInline(admin.TabularInline):
    model = HistoricoDisciplina
    extra = 0
    autocomplete_fields = ('disciplina',)


class NivelamentoAlunoInline(admin.TabularInline):
    model = NivelamentoAluno
    extra = 0


@admin.register(PerfilAluno)
class PerfilAlunoAdmin(admin.ModelAdmin):
    list_display = ('user', 'curso')
    list_filter = ('curso',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    inlines = [NivelamentoAlunoInline, HistoricoDisciplinaInline]
