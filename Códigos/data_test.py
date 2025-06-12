import time
import cv2
from time import sleep
from ultralytics import YOLO
import matplotlib.pyplot as plt
import networkx as nx
import heapq

# ------------------ CONFIGURACAO DETECCAO ------------------
CLASSES = ['Direita', 'Esquerda', 'Pare', 'Reto']
CONFIDENCE_THRESHOLD = 0.75
modelo = YOLO('best.pt')
camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 640)

# ------------------ MAPA E CONEXÕES FIXAS ------------------
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

# Gerar conexões bidirecionais para facilitar uso
for (a, b) in list(PESOS.keys()):
    PESOS[(b, a)] = PESOS[(a, b)]

for idx, nome in enumerate(letras):
    row, col = divmod(idx, 5)
    vizinhos = {}
    if row > 0:
        vizinhos['Norte'] = letras[idx - 5]
    if row < 3:
        vizinhos['Sul'] = letras[idx + 5]
    if col > 0:
        vizinhos['Oeste'] = letras[idx - 1]
    if col < 4:
        vizinhos['Leste'] = letras[idx + 1]
    DIRECOES[nome] = vizinhos

ROTACOES = {
    'Norte': {'Esquerda': 'Oeste', 'Direita': 'Leste'},
    'Sul': {'Esquerda': 'Leste', 'Direita': 'Oeste'},
    'Leste': {'Esquerda': 'Norte', 'Direita': 'Sul'},
    'Oeste': {'Esquerda': 'Sul', 'Direita': 'Norte'}
}

SETAS = {
    'Norte': (0, 0.25),
    'Sul': (0, -0.25),
    'Leste': (0.25, 0),
    'Oeste': (-0.25, 0)
}

# ------------------ DIJKSTRA ------------------
def dijkstra(origem, destino):
    grafo = {}
    for atual, vizinhos in DIRECOES.items():
        grafo[atual] = {
            vizinho: PESOS.get((atual, vizinho), 3)
            for direcao, vizinho in vizinhos.items()
        }

    fila = [(0, origem)]
    caminhos = {origem: (None, 0)}
    visitados = set()

    while fila:
        custo, atual = heapq.heappop(fila)
        if atual in visitados:
            continue
        visitados.add(atual)
        for vizinho, peso in grafo[atual].items():
            novo_custo = custo + peso
            if vizinho not in caminhos or novo_custo < caminhos[vizinho][1]:
                caminhos[vizinho] = (atual, novo_custo)
                heapq.heappush(fila, (novo_custo, vizinho))

    caminho = []
    atual = destino
    while atual:
        caminho.insert(0, atual)
        atual = caminhos[atual][0]
    return caminho

# ------------------ SIMULAR ------------------
def simular_movimento(origem, destino):
    tempo = PESOS.get((origem, destino), 3)
    print(f"Movendo de {origem} para {destino} (Reto) por {tempo}s")
    sleep(tempo)
    return tempo

def simular_rotacao(direcao):
    print(f"Virando {direcao} (1.5s)")
    sleep(1.5)
    return 1.5

# ------------------ MAPA VISUAL ------------------
def inicializar_mapa():
    G = nx.Graph()
    pos = {}
    for idx, nome in enumerate(letras):
        row, col = divmod(idx, 5)
        pos[nome] = (col, 3 - row)
        for direcao in DIRECOES[nome]:
            destino = DIRECOES[nome][direcao]
            peso = PESOS.get((nome, destino), 3)
            G.add_edge(nome, destino, weight=peso)
    return G, pos

# ------------------ DETECCAO ------------------
def detectar_e_executar():
    atual = 'A'
    destino_final = 'T'
    orientacao = 'Leste'
    G_mapa, pos = inicializar_mapa()
    caminho = dijkstra(atual, destino_final)
    print(f"Caminho ideal inicial: {caminho}\n")

    plt.ion()
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor('#f7f7f7')
    ax.set_facecolor('#e9e9e9')

    tempo_debounce = 0
    log = []
    caminho_real = [atual]

    while atual != destino_final:
        agora = time.time()
        if tempo_debounce > agora:
            print("Aguardando fim do tempo de debounce...")
            sleep(0.5)
            continue

        ret, frame = camera.read()
        if not ret:
            print("Erro ao capturar frame")
            break

        resultados = modelo(frame)
        placa_detectada = None
        confianca_detectada = 0.0

        for resultado in resultados[0].boxes:
            conf, classe = resultado.conf[0], int(resultado.cls[0])
            if conf > CONFIDENCE_THRESHOLD and classe < len(CLASSES):
                placa_detectada = CLASSES[classe]
                confianca_detectada = float(conf)
                break

        if placa_detectada:
            log.append({
                "hora": time.strftime('%H:%M:%S'),
                "placa": placa_detectada,
                "posicao": atual,
                "orientacao": orientacao,
                "confianca": round(confianca_detectada, 2)
            })
            if placa_detectada in ['Esquerda', 'Direita']:
                orientacao = ROTACOES[orientacao][placa_detectada]
                duracao = simular_rotacao(placa_detectada)
                tempo_debounce = time.time() + duracao + 2.0
            elif placa_detectada == 'Reto':
                if orientacao in DIRECOES[atual]:
                    proximo = DIRECOES[atual][orientacao]
                    duracao = simular_movimento(atual, proximo)
                    atual = proximo
                    caminho_real.append(atual)
                    tempo_debounce = time.time() + duracao + 1.0
                    print(f"Nova posição: {atual}, orientação: {orientacao}")
                    if atual not in caminho:
                        caminho = dijkstra(atual, destino_final)
                        print(f"Novo caminho ideal: {caminho}\n")
                else:
                    print(f"Não há caminho Reto ({orientacao}) a partir de {atual}")
            elif placa_detectada == 'Pare':
                print("Parando...")
                break
        else:
            print("Nenhuma placa detectada. Aguardando...")
            sleep(0.7)

        ax.clear()
        edge_labels = nx.get_edge_attributes(G_mapa, 'weight')
        nx.draw(G_mapa, pos, with_labels=True, node_color='#d0e1f9', node_size=1000, font_size=9, font_weight='bold', font_color='black', ax=ax)
        nx.draw_networkx_nodes(G_mapa, pos, nodelist=[atual], node_color='orange', node_size=1300, ax=ax)
        nx.draw_networkx_edge_labels(G_mapa, pos, edge_labels=edge_labels, font_size=6, ax=ax)

        if len(caminho) > 1:
            edges = [(caminho[i], caminho[i+1]) for i in range(len(caminho)-1)]
            nx.draw_networkx_edges(G_mapa, pos, edgelist=edges, edge_color='green', width=2, ax=ax)

        x, y = pos[atual]
        dx, dy = SETAS[orientacao]
        ax.annotate('', xy=(x+dx, y+dy), xytext=(x, y), arrowprops=dict(arrowstyle="->", color='red', lw=2))

        ax.set_title(f"Mapa do Robô\nPosição: {atual} | Orientação: {orientacao}", fontsize=13, weight='bold')
        ax.set_xlim(-1, 5)
        ax.set_ylim(-1, 4.5)
        ax.axis('off')
        plt.pause(0.1)

        cv2.putText(frame, f"Atual: {atual} | {orientacao}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
        cv2.imshow("Visao Robo", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    camera.release()
    cv2.destroyAllWindows()
    plt.ioff()
    plt.show()

    print("\n===== LOG DE DETECÇÕES =====")
    for item in log:
        print(f"[{item['hora']}] Placa: {item['placa']:<8} | Confiança: {item['confianca']:<4} | Local: {item['posicao']} | Orientação: {item['orientacao']}")

    print("\n===== CAMINHO REAL PERCORRIDO =====")
    print(" -> ".join(caminho_real))

if __name__ == "__main__":
    detectar_e_executar()