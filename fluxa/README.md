# Fluxa

Aplicação Django para planejar a matrícula na PUC-Rio: histórico (com importação
do SAU), fluxograma do curso, simulador de matrícula e planejamento de grades.
Cursos incluídos: Engenharia de Computação, Produção, Controle e Automação,
Elétrica, Química, Civil, Mecânica, Materiais e Nanotecnologia e Ambiental.

## Instalação (Windows / PowerShell)

Abra o terminal **dentro da pasta `fluxa`** (a que contém o `manage.py`):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py importar_dados
python manage.py runserver
```

Depois abra http://127.0.0.1:8000/ e crie uma conta.

`python manage.py importar_dados` carrega, uma única vez, as disciplinas, os
pré-requisitos e as turmas do micro-horário. Ele pode ser repetido sem risco:
não apaga nem sobrescreve nada que já esteja no banco. Use `--sem-horarios`
para importar só as grades dos cursos. Quando sair um novo micro-horário,
atualize a planilha e rode o comando de novo: o período letivo vem da célula A1
da planilha.

Os períodos e as setas de cada engenharia usam
`matricula/dados/FLUXA_grade_curricular_A_engenharias.xlsx`, incluindo a aba
`OPTATIVAS`. O fluxograma é renderizado pelo Django, inclusive as setas SVG,
sem depender de JavaScript e sem aplicar zoom. A seleção destaca a cadeia
na própria grade; o painel abaixo contém somente identificação e ações.

Na validação, o cache `matricula/dados/requisitos_oficiais_puc.json` tem
prioridade para as disciplinas consultadas nas ementas oficiais. Ele preserva
alternativas de disciplinas, créditos e níveis sem substituir códigos exatos
por grupos de optativas. Para atualizar, execute
`python manage.py sincronizar_ementas_puc`; o comando registra fonte, data
e falhas de consulta. As matérias sem consulta bem-sucedida usam a planilha.

Essas regras prevalecem sobre regras antigas do banco: `+` exige
todos os itens e `|` permite alternativas. Créditos mínimos e nivelamento
também são conferidos ao salvar a grade. CTC corresponde a Matemática;
Português exige o nível indicado em Compreensão textual e Interpretação textual.
No fluxograma, uma matéria só aparece com requisitos cumpridos quando os
pré-requisitos e os correquisitos estiverem atendidos no histórico; no simulador,
correquisitos também podem ser selecionados juntos na mesma matrícula.

Depois de substituir a planilha, rode `python manage.py sincronizar_catalogo_planilha`
para cadastrar disciplinas novas sem alterar históricos. Esse passo também
faz parte de `importar_dados`. Matérias sem regras nessa planilha continuam
usando os requisitos cadastrados; exigências não verificadas ficam bloqueadas.

## Importação do histórico (SAU)

Na tela **Histórico**, envie o PDF do histórico do SAU. O arquivo é lido na hora
e apagado do servidor em seguida; nada além do que você confirmar é guardado.
Se o PDF for uma imagem (sem texto), é preciso instalar o OCR (opcional):

```powershell
python -m pip install -r requirements-ocr.txt
```

e instalar o programa [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
com o idioma português (ou definir a variável `TESSERACT_CMD`).

## Testes

```powershell
python manage.py test matricula
```
