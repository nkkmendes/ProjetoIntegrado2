from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .catalogos_fluxa import consultar_catalogo_optativas
from .models import Curso
from .servicos import obter_perfil


@login_required
def consultar_optativas(request):
    perfil = obter_perfil(request.user)
    curso = perfil.curso
    cursos = Curso.objects.order_by('nome')
    selecionado = request.GET.get('curso', '').strip()
    if selecionado:
        curso = cursos.filter(nome=selecionado).first() or curso

    grupos, opcoes, erro = [], [], ''
    if curso:
        try:
            grupos, opcoes = consultar_catalogo_optativas(curso.nome)
        except (OSError, ValueError, ImportError, KeyError) as exc:
            erro = str(exc)

    return render(request, 'consultar_optativas.html', {
        'curso': curso,
        'cursos': cursos,
        'grupos': grupos,
        'opcoes': opcoes,
        'erro': erro,
    })
