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
    
n1 = float(input("Digite o primeiro número: "))
operacao = input("Digite a operação (+, -, *, /): ")
n2 = float(input("Digite o segundo número: "))


elif operacao == "*":
    resultado = multiplicar(n1, n2)

elif operacao == "/":
    resultado = dividir(n1, n2)

else:
    resultado = "Não vai funcionar "

print(f"Resultado: {resultado}")