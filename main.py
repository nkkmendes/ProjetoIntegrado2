def calcula_adicao(x,y):
    return x + y

def calcula_subtracao(x,y):
    return x - y
    
def calcula_radificacao(x,y):
    return x ** (1/y)

def calcula_exponenciacao(x,y):
    return x **y

def calcula_multiplicacao(a, b):
    return a * b

def calcula_divisao(a, b):
    if b != 0:
        return a / b
    else:
        return "Não é possível dividir por zero"

def calcula_divisaoInteiraComResto(a,b):
    if b != 0:
        x=a//b
        y=a%b
        return(x,y)
    else:
        return "Não é possível dividir por zero"

def calcula_percentual(a,b):
    if b != 0:
        x=a/b
        x=x*100
        return(x)
    else:
        return "Não é possível fazer este percentual"

a = int(input("""Escolha uma das opções abaixo:

1 - Adição
2 - Subtração
3 - Mulitplicação
4 - Divisão
5 - Radificação
6 - Exponenciação
7 - Divisão inteira com resto
8 - Percentual
0 - Sair do programa
"""))

if a != 0:
    x = int(input("Primeiro valor: "))
    y = int(input("Segundo valor: "))
    if a == 1:
        r = calcula_adicao(x,y)
    elif a == 2:
        r = calcula_subtracao(x, y)
    elif a == 3:
        r = calcula_multiplicacao(x, y)
    elif a == 4:
        r = calcula_divisao(x, y)
    elif a == 5:
        r = calcula_radificacao(x, y)
    elif a == 6:
        r = calcula_exponenciacao(x, y)
    elif a == 7:
        r = calcula_divisaoInteiraComResto(x, y)
    elif a == 8:
        r = calcula_percentual(x, y)
    print("Resultado:"+str(r))
