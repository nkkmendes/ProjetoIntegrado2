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

Os dados dos cursos ficam no banco (editáveis pelo `/admin/`); a aplicação não
lê planilhas nem JSON enquanto roda.

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
