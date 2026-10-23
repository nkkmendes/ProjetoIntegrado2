
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('matricula', '0002_disciplina'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlanejamentoSalvo',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID'
                )),
                ('nome', models.CharField(max_length=100)),
                ('periodo', models.IntegerField()),
                ('disciplinas', models.TextField()),
            ],
        ),

        migrations.CreateModel(
            name='SimulacaoSalva',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID'
                )),
                ('nome', models.CharField(max_length=100)),
                ('disciplinas', models.TextField()),
            ],
        ),

        migrations.CreateModel(
            name='NivelamentoSalvo',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID'
                )),
                ('nome', models.CharField(max_length=100)),
                ('area', models.CharField(max_length=100)),
                ('resultado', models.CharField(max_length=100)),
            ],
        ),
    ]
