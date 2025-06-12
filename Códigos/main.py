import ASUS.GPIO as GPIO
import cv2
import time
from time import sleep
from ultralytics import YOLO
import heapq

# Configuração dos motores
in1, in2, enA = 35, 36, 33
in3, in4, enB = 37, 38, 32

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)
GPIO.setup([enA, in1, in2, in3, in4, enB], GPIO.OUT)
GPIO.output([in1, in2, in3, in4], GPIO.LOW)
GPIO.output([enA, enB], GPIO.HIGH)

p_enA = GPIO.PWM(enA, 1000)
p_enB = GPIO.PWM(enB, 1000)
VEL = 25
p_enA.start(VEL)
p_enB.start(VEL)

# Configurações
CLASSES = ['Direita', 'Esquerda', 'Pare', 'Reto']
CONFIDENCE_THRESHOLD = 0.7
modelo = YOLO('best.pt') # caminho do modelo treinado

letras = 'ABCDEFGHIJKLMNOPQRST'
DIRECOES = {}
PESOS = {
    ('A', 'B'): 3, ('B', 'C'): 4, ('C', 'D'): 3, ('D', 'E'): 5,
    ('A', 'F'): 3, ('B', 'G'): 4, ('C', 'H'): 3, ('D', 'I'): 5, ('E', 'J'): 4,
    ('F', 'G'): 3, ('G', 'H'): 5, ('H', 'I'): 3, ('I', 'J'): 4,
    ('F', 'K'): 4, ('G', 'L'): 3, ('H', 'M'): 5, ('I', 'N'): 4, ('J', 'O'): 3,
    ('K', 'L'): 3, ('L', 'M'): 4, ('M', 'N'): 3, ('N', 'O'): 5,
    ('K', 'P'): 3, ('L', 'Q'): 4, ('M', 'R'): 3, ('N', 'S'): 4, ('O', 'T'): 5,
    ('P', 'Q'): 3, ('Q', 'R'): 3, ('R', 'S'): 4, ('S', 'T'): 3
}
for (a, b) in list(PESOS):
    PESOS[(b, a)] = PESOS[(a, b)]

for idx, nome in enumerate(letras):
    row, col = divmod(idx, 5)
    vizinhos = {}
    if row > 0: vizinhos['Norte'] = letras[idx - 5]
    if row < 3: vizinhos['Sul'] = letras[idx + 5]
    if col > 0: vizinhos['Oeste'] = letras[idx - 1]
    if col < 4: vizinhos['Leste'] = letras[idx + 1]
    DIRECOES[nome] = vizinhos

ROTACOES = {
    'Norte': {'Esquerda': 'Oeste', 'Direita': 'Leste'},
    'Sul': {'Esquerda': 'Leste', 'Direita': 'Oeste'},
    'Leste': {'Esquerda': 'Norte', 'Direita': 'Sul'},
    'Oeste': {'Esquerda': 'Sul', 'Direita': 'Norte'}
}

# Lógica de caminho
def dijkstra(origem, destino):
    grafo = {}
    for atual, viz in DIRECOES.items():
        grafo[atual] = {
            v: PESOS.get((atual, v), 3) for d, v in viz.items()
        }

    fila = [(0, origem)]
    caminhos = {origem: (None, 0)}
    visitados = set()

    while fila:
        custo, atual = heapq.heappop(fila)
        if atual in visitados: continue
        visitados.add(atual)
        if atual == destino: break
        for viz, peso in grafo[atual].items():
            novo = custo + peso
            if viz not in caminhos or novo < caminhos[viz][1]:
                caminhos[viz] = (atual, novo)
                heapq.heappush(fila, (novo, viz))

    caminho = []
    atual = destino
    while atual:
        caminho.insert(0, atual)
        anterior = caminhos.get(atual)
        if anterior is None: break
        atual = anterior[0]
    return caminho

def mover_robo(direcao):
    comandos = {
        "Pare": (GPIO.LOW, GPIO.LOW, GPIO.LOW, GPIO.LOW),
        "Reto": (GPIO.LOW, GPIO.HIGH, GPIO.HIGH, GPIO.LOW),
        "Esquerda": (GPIO.LOW, GPIO.LOW, GPIO.HIGH, GPIO.LOW),
        "Direita": (GPIO.LOW, GPIO.HIGH, GPIO.LOW, GPIO.LOW)
    }
    if direcao in comandos:
        GPIO.output([in1, in2, in3, in4], comandos[direcao])
        print(f"Movendo: {direcao}")

def executar_robo():
    atual = 'S'
    destino = 'F'
    orientacao = 'Leste'
    caminho = dijkstra(atual, destino)

    camera = cv2.VideoCapture(0)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 640)

    tempo_debounce = 0

    try:
        while True:
            if atual == destino:
                print(f"Destino {destino} alcançado!")
                break

            if tempo_debounce > time.time():
                sleep(0.05)
                continue

            ret, frame = camera.read()
            if not ret:
                print("Erro na câmera")
                break

            resultados = modelo(frame)
            direcao_detectada = None
            confianca = 0.0

            for resultado in resultados[0].boxes:
                conf, classe = resultado.conf[0], int(resultado.cls[0])
                if conf > CONFIDENCE_THRESHOLD and classe < len(CLASSES):
                    direcao_detectada = CLASSES[classe]
                    confianca = float(conf)
                    break

            if not direcao_detectada:
                continue

            if direcao_detectada in ['Esquerda', 'Direita']:
                nova_orientacao = ROTACOES[orientacao][direcao_detectada]
                mover_robo(direcao_detectada)
                sleep(1.5)
                mover_robo("Pare")
                orientacao = nova_orientacao
                tempo_debounce = time.time() + 0.5

            elif direcao_detectada == 'Reto':
                if orientacao in DIRECOES[atual]:
                    proximo = DIRECOES[atual][orientacao]
                    mover_robo("Reto")
                    duracao = PESOS.get((atual, proximo), 3)
                    sleep(duracao)
                    mover_robo("Pare")
                    atual = proximo
                    caminho = dijkstra(atual, destino)
                    tempo_debounce = time.time() + 0.5
                    print(f"Nova posição: {atual} | Orientação: {orientacao}")
                else:
                    print(f"Movimento Reto inválido a partir de {atual} em direção {orientacao}")

            elif direcao_detectada == 'Pare':
                mover_robo("Pare")
                print("Parando temporariamente...")
                sleep(2.0)
                tempo_debounce = time.time() + 0.5

    finally:
        camera.release()
        cv2.destroyAllWindows()
        GPIO.cleanup()
        print("Finalizado.")

if __name__ == "__main__":
    executar_robo()
