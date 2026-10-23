from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Curso",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=3)),
                ("nome", models.CharField(max_length=256)),
                ("ano_curriculo", models.DecimalField(max_digits=4, decimal_places=0)),
            ],
            options={"db_table": "curso"},
        ),
        migrations.CreateModel(
            name="Materia",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=8)),
                ("nome", models.CharField(max_length=256)),
                ("creditos", models.IntegerField()),
                ("horas", models.IntegerField()),
                ("horas_extras", models.IntegerField(blank=True, null=True)),
            ],
            options={"db_table": "materia"},
        ),
        migrations.CreateModel(
            name="Professor",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=256)),
            ],
            options={"db_table": "professor"},
        ),
        migrations.CreateModel(
            name="Turma",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=3)),
                ("periodo", models.DecimalField(max_digits=5, decimal_places=0)),
                ("vagas_totais", models.IntegerField()),
                ("vagas_ocupadas", models.IntegerField(default=0)),
                ("materia", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="fluxa.materia")),
                ("professor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="fluxa.professor")),
            ],
            options={"db_table": "turma"},
        ),
        migrations.CreateModel(
            name="Aluno",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=256)),
                ("numero_matricula", models.DecimalField(max_digits=7, decimal_places=0)),
                ("cr", models.DecimalField(blank=True, null=True, max_digits=3, decimal_places=1)),
                ("curso", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="fluxa.curso")),
            ],
            options={"db_table": "aluno"},
        ),
        migrations.CreateModel(
            name="Grade",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=80)),
                ("aluno", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="fluxa.aluno")),
            ],
            options={"db_table": "grade"},
        ),
        migrations.CreateModel(
            name="GrupoRequisito",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo_requisito", models.CharField(max_length=1)),
                ("materia", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="fluxa.materia")),
            ],
            options={"db_table": "grupo_requisito"},
        ),
        migrations.CreateModel(
            name="Historico",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("periodo", models.DecimalField(max_digits=5, decimal_places=0)),
                ("cursando", models.BooleanField(default=False)),
                ("aprovado", models.BooleanField(default=False)),
                ("nota", models.DecimalField(blank=True, null=True, max_digits=3, decimal_places=1)),
                ("numero_de_oportunidades", models.IntegerField(blank=True, null=True)),
                ("aluno", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="fluxa.aluno")),
                ("materia", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="fluxa.materia")),
                ("turma", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="fluxa.turma")),
            ],
            options={"db_table": "historico"},
        ),
        migrations.CreateModel(
            name="HorarioTurma",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("dia_semana", models.IntegerField()),
                ("hora_inicio", models.TimeField()),
                ("hora_fim", models.TimeField()),
                ("turma", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="fluxa.turma")),
            ],
            options={"db_table": "horario_turma"},
        ),
        migrations.CreateModel(
            name="Requisito",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("materia", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="fluxa.materia")),
                ("grupo_requisito", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="fluxa.gruporequisito")),
            ],
            options={"db_table": "requisito"},
        ),
        migrations.CreateModel(
            name="TurmaGrade",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("grade", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="fluxa.grade")),
                ("turma", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="fluxa.turma")),
            ],
            options={"db_table": "turma_grade"},
        ),
    ]
