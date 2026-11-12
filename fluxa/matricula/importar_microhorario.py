"""Importa turmas e horários do Micro-Horário da PUC-Rio para o Fluxa.

Normalmente é chamado pelo comando `python manage.py importar_dados`.
A planilha fica em matricula/dados/Horario_das_Disciplinas_05112026.xlsx e o
período (ex.: 2026.2) é lido do próprio cabeçalho dela.
"""

import re
from datetime import time
from pathlib import Path

from django.conf import settings
from django.db import transaction
from matricula.models import Disciplina, HorarioTurma, Turma


ARQUIVO = Path(settings.BASE_DIR) / 'matricula' / 'dados' / 'Horario_das_Disciplinas_05112026.xlsx'

PERIODO_NO_CABECALHO = re.compile(r'Período:\s*(\d{4}\.\d)')
DIAS = {'SEG': 0, 'TER': 1, 'QUA': 2, 'QUI': 3, 'SEX': 4, 'SAB': 5, 'SÁB': 5}
PADRAO = re.compile(
    r'\b(SEG|TER|QUA|QUI|SEX|SAB|SÁB)\s+'
    r'(\d{1,2})(?::(\d{2}))?\s*[-–]\s*'
    r'(\d{1,2})(?::(\d{2}))?(?:\s+([^\n]+))?',
    re.IGNORECASE,
)


def extrair_horarios(texto):
    """Retorna (dia, início, fim, sala) para cada encontro regular."""
    encontros = set()
    for linha in str(texto or '').splitlines():
        linha = linha.strip()
        for achado in PADRAO.finditer(linha):
            dia, hi, mi, hf, mf, sala = achado.groups()
            hi, mi, hf, mf = int(hi), int(mi or 0), int(hf), int(mf or 0)
            if hi > 23 or hf > 23 or mi > 59 or mf > 59:
                continue
            inicio, fim = time(hi, mi), time(hf, mf)
            if inicio >= fim:
                continue
            encontros.add((DIAS[dia.upper()], inicio, fim, (sala or '').strip()[:50]))
    return encontros


def importar():
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError('Instale o leitor de Excel: pip install openpyxl') from exc

    if not ARQUIVO.is_file():
        raise FileNotFoundError(f'Planilha não encontrada: {ARQUIVO}')

    planilha = load_workbook(ARQUIVO, read_only=True, data_only=True)
    try:
        aba = planilha['MicroHorario'] if 'MicroHorario' in planilha.sheetnames else planilha.active
        achado_periodo = PERIODO_NO_CABECALHO.search(str(aba['A1'].value or ''))
        if not achado_periodo:
            raise ValueError('A planilha não indica o período (esperado "Período: 2026.2" na célula A1).')
        periodo = achado_periodo.group(1)

        # A planilha tem uma linha por combinação de turma e destino/bloqueio.
        # Consolidamos esses destinos sem duplicar a mesma turma no banco.
        registros = {}
        linhas_lidas = 0
        for linha in aba.iter_rows(min_row=3, values_only=True):
            if not linha or not linha[0] or not linha[3]:
                continue
            linhas_lidas += 1
            codigo_nome = str(linha[0]).strip()
            codigo = codigo_nome.split(' - ', 1)[0].strip().upper()
            codigo_turma = str(linha[3]).strip().upper()
            chave = (codigo, codigo_turma)
            professor = str(linha[1] or '').strip()
            destino = str(linha[4] or '').strip().upper()
            vagas = linha[5]
            try:
                vagas = max(int(vagas), 0) if vagas is not None else None
            except (ValueError, TypeError):
                vagas = None

            if chave not in registros:
                registros[chave] = {
                    'professor': professor,
                    'destinos': {},
                    'horarios': set(),
                }
            registro = registros[chave]
            if not registro['professor'] and professor:
                registro['professor'] = professor
            if vagas is not None:
                # Máximo por destino previne contagem duplicada em linhas repetidas.
                registro['destinos'][destino] = max(
                    registro['destinos'].get(destino, 0), vagas
                )
            registro['horarios'].update(extrair_horarios(linha[7]))
    finally:
        planilha.close()

    # Não cadastramos todas as disciplinas da PUC: somente as que já existem
    # no banco do Fluxa (associadas ao catálogo importado das engenharias).
    codigos = {codigo for codigo, _ in registros}
    disciplinas = Disciplina.objects.in_bulk(codigos, field_name='codigo')
    criadas = atualizadas = horarios_salvos = ignoradas = 0

    with transaction.atomic():
        for (codigo, codigo_turma), registro in registros.items():
            disciplina = disciplinas.get(codigo)
            if disciplina is None:
                ignoradas += 1
                continue

            turma, criada = Turma.objects.update_or_create(
                disciplina=disciplina,
                codigo=codigo_turma,
                periodo_letivo=periodo,
                defaults={
                    'professor': registro['professor'][:150],
                    'vagas': sum(registro['destinos'].values())
                    if registro['destinos'] else None,
                },
            )
            if criada:
                criadas += 1
            else:
                atualizadas += 1

            # Substituir somente os horários desta turma neste período.
            # Reexecutar a importação não cria horários duplicados.
            turma.horarios.all().delete()
            HorarioTurma.objects.bulk_create([
                HorarioTurma(
                    turma=turma,
                    dia_semana=dia,
                    hora_inicio=inicio,
                    hora_fim=fim,
                    sala=sala,
                )
                for dia, inicio, fim, sala in sorted(registro['horarios'])
            ])
            horarios_salvos += len(registro['horarios'])

    return {
        'periodo': periodo,
        'linhas': linhas_lidas,
        'disciplinas_no_banco': len(disciplinas),
        'turmas_criadas': criadas,
        'turmas_atualizadas': atualizadas,
        'horarios': horarios_salvos,
        'turmas_ignoradas': ignoradas,
    }
