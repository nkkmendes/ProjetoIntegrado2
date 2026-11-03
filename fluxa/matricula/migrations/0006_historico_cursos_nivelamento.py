import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def copiar_dados(apps, schema_editor):
    """Leva os dados do modelo antigo para o novo antes de apagar as tabelas antigas."""
    Disciplina = apps.get_model('matricula', 'Disciplina')
    PerfilAluno = apps.get_model('matricula', 'PerfilAluno')
    Historico = apps.get_model('matricula', 'HistoricoDisciplina')
    DisciplinaCursada = apps.get_model('matricula', 'DisciplinaCursada')
    CreditosAluno = apps.get_model('matricula', 'CreditosAluno')
    GrauAluno = apps.get_model('matricula', 'GrauAluno')

    # 1) Disciplina.curso (um só) -> Disciplina.cursos (vários)
    for disciplina in Disciplina.objects.exclude(curso=None):
        disciplina.cursos.add(disciplina.curso_id)

    # 2) O histórico agora pertence ao perfil; quem não tinha perfil ganha um
    def perfil_de(user_id):
        perfil, _ = PerfilAluno.objects.get_or_create(user_id=user_id)
        return perfil

    # 3a) Contagem de créditos: só o que estava marcado como concluído
    for c in CreditosAluno.objects.filter(concluida=True):
        Historico.objects.get_or_create(
            perfil=perfil_de(c.aluno_id),
            disciplina_id=c.disciplina_id,
            defaults={'status': 'concluida'},
        )

    # 3b) Marcadas como concluídas no fluxograma
    for c in DisciplinaCursada.objects.all():
        Historico.objects.update_or_create(
            perfil=perfil_de(c.user_id),
            disciplina_id=c.disciplina_id,
            defaults={'status': 'concluida' if c.status == 'concluida' else 'em_curso'},
        )

    # 3c) Consulta de graus: traz as notas; o registro mais recente de cada disciplina vence
    situacoes = {'Aprovado': 'concluida', 'Reprovado': 'reprovada'}
    for g in GrauAluno.objects.order_by('periodo_letivo', 'id'):
        novo_status = situacoes.get(g.situacao, 'em_curso')
        registro, criado = Historico.objects.get_or_create(
            perfil=perfil_de(g.aluno_id),
            disciplina_id=g.disciplina_id,
            defaults={'status': novo_status},
        )
        # "Em curso" nunca rebaixa uma disciplina que já estava concluída
        if criado or novo_status != 'em_curso':
            registro.status = novo_status
        registro.periodo_letivo = g.periodo_letivo
        registro.turma = '' if g.turma == '-' else g.turma
        registro.g1, registro.g2, registro.g3, registro.media = g.g1, g.g2, g.g3, g.media
        registro.save()


class Migration(migrations.Migration):

    dependencies = [
        ('matricula', '0005_curso_grupos_cursadas'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # --- Parte 1: cria o que é novo -----------------------------------
        migrations.CreateModel(
            name='AreaNivelamento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100, unique=True)),
            ],
            options={'ordering': ['nome']},
        ),
        migrations.CreateModel(
            name='HistoricoDisciplina',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[('concluida', 'Concluída'), ('em_curso', 'Em curso'), ('reprovada', 'Reprovada')],
                    default='concluida', max_length=10)),
                ('periodo_letivo', models.CharField(blank=True, default='', max_length=10)),
                ('turma', models.CharField(blank=True, default='', max_length=10)),
                ('g1', models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True)),
                ('g2', models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True)),
                ('g3', models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True)),
                ('media', models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True)),
                ('disciplina', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='historico', to='matricula.disciplina')),
                ('perfil', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='historico', to='matricula.perfilaluno')),
            ],
            options={'ordering': ['-periodo_letivo', 'disciplina__codigo']},
        ),
        migrations.CreateModel(
            name='NivelamentoAluno',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nivel', models.PositiveSmallIntegerField()),
                ('area', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='niveis_de_alunos', to='matricula.areanivelamento')),
                ('perfil', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='niveis', to='matricula.perfilaluno')),
            ],
            options={'ordering': ['area__nome']},
        ),
        migrations.CreateModel(
            name='RequisitoNivelamento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nivel_minimo', models.PositiveSmallIntegerField()),
                ('area', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='requisitos', to='matricula.areanivelamento')),
                ('disciplina', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='requisitos_nivelamento', to='matricula.disciplina')),
            ],
            options={'ordering': ['disciplina__codigo', 'area__nome']},
        ),
        migrations.AddConstraint(
            model_name='historicodisciplina',
            constraint=models.UniqueConstraint(
                fields=('perfil', 'disciplina'),
                name='historico_unico_por_aluno_e_disciplina'),
        ),
        migrations.AddConstraint(
            model_name='nivelamentoaluno',
            constraint=models.UniqueConstraint(
                fields=('perfil', 'area'),
                name='nivel_unico_por_aluno_e_area'),
        ),
        migrations.AddConstraint(
            model_name='requisitonivelamento',
            constraint=models.UniqueConstraint(
                fields=('disciplina', 'area'),
                name='requisito_nivel_unico_por_disciplina_e_area'),
        ),
        migrations.AddField(
            model_name='disciplina',
            name='cursos',
            field=models.ManyToManyField(blank=True, related_name='disciplinas', to='matricula.curso'),
        ),

        # --- Parte 2: leva os dados antigos para o modelo novo --------------
        migrations.RunPython(copiar_dados, migrations.RunPython.noop),

        # --- Parte 3: apaga o que ficou obsoleto -----------------------------
        migrations.RemoveField(model_name='disciplina', name='curso'),
        migrations.DeleteModel(name='DisciplinaCursada'),
        migrations.DeleteModel(name='CreditosAluno'),
        migrations.DeleteModel(name='GrauAluno'),
        migrations.DeleteModel(name='NivelamentoSalvo'),
    ]
