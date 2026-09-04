def multiplicar(a, b):
    return a * b

def dividir(a, b):
    if b != 0:
        return a / b
    else:
        return "Não é possível dividir por zero"

def divisaoInteiraComResto(a,b):
    if b != 0:
        x=a//b
        y=a%b
        return(x,y)
    else:
        return "Não é possível dividir por zero"

def percentual(a,b):
    if b != 0:
        x=a/b
        x=x*100
        return(x)
    else:
        return "Não é possível fazer este percentual"
