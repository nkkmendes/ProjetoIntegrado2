# Uma "view" e so uma funcao Python: recebe um objeto "request" e
# devolve um objeto de resposta HTTP. Nada magico - e o ponto em que
# decidimos o que fazer com a requisicao.
from django.contrib import messages
from django.shortcuts import redirect, render

from .forms import DisciplinaConcluidaForm


def registrar_disciplina_concluida(request):
    # request.method diz se foi GET (so pediu pra ver a pagina) ou
    # POST (o usuario enviou o formulario).
    if request.method == "POST":
        # Form "vinculado": criado ja com os dados enviados, prontos
        # pra validar (diferente de DisciplinaConcluidaForm() vazio).
        form = DisciplinaConcluidaForm(request.POST)
        if form.is_valid():
            # Dispara clean() de cada campo + o clean() customizado do
            # forms.py, preenche cleaned_data/errors, e aqui ja grava
            # no banco via o save() sobrescrito.
            historico = form.save()
            # Mensagem guardada na sessao do usuario, exibida na
            # PROXIMA pagina renderizada (nao nesta resposta aqui).
            messages.success(
                request,
                f"Disciplina {historico.materia.nome} registrada para {historico.aluno.nome}.",
            )
            # Redirect (HTTP 302) em vez de render: faz o navegador
            # pedir a pagina de novo via GET, evitando reenviar o
            # mesmo formulario se o usuario apertar F5 (padrao
            # POST/redirect/GET).
            return redirect("registrar_disciplina_concluida")
        # Se o form for invalido, cai pro render() no final com os
        # erros ja anexados, pra mostrar na tela.
    else:
        # GET: formulario vazio, sem dados.
        form = DisciplinaConcluidaForm()

    # Pega o template, injeta {"form": form} nele e devolve o HTML
    # final como resposta.
    return render(request, "fluxa/registrar_disciplina_concluida.html", {"form": form})
