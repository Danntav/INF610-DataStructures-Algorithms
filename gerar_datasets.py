"""Gera os grafos sintéticos do benchmark e os salva em formato DOT.

Este script NÃO precisa ser executado para reproduzir o trabalho: os arquivos gerados já estão no
repositório (data/synthetic/ e data/optimal/). Ele está aqui para mostrar como os grafos foram feitos.

Uso:  python gerar_datasets.py

Saída:
    data/synthetic/  DAGs em camadas, parecidos com DFGs: 7 tamanhos (64 a 4096 nós) × 5 grafos = 35 arquivos
    data/optimal/    grafos com posicionamento ótimo conhecido: 5 tamanhos (6×6 a 20×20) × 10 grafos = 50 arquivos

Cada grafo é gerado a partir de uma semente fixa. A mesma semente produz sempre o mesmo grafo, em
qualquer computador, porque o gerador de números pseudoaleatórios do Python (random.Random) é
determinístico. Por isso, rodar este script de novo recria exatamente os mesmos arquivos.

Só usa a biblioteca padrão do Python.
"""
from __future__ import annotations

import random
from pathlib import Path

PASTA = Path(__file__).resolve().parent / "data"

# Parâmetros (os mesmos descritos na Seção 6 do relatório)
TAMANHOS_SINTETICOS = [64, 128, 256, 512, 1024, 2048, 4096]
GRAFOS_POR_TAMANHO_SINTETICO = 5
LADOS_OTIMOS = [6, 8, 10, 14, 20]
GRAFOS_POR_TAMANHO_OTIMO = 10


# ---------------------------------------------------------------------------------------------
# Union-find: usado para saber se dois nós já estão no mesmo componente
# ---------------------------------------------------------------------------------------------
class UnionFind:
    def __init__(self, n):
        self.pai = list(range(n))

    def raiz(self, x):
        while self.pai[x] != x:
            self.pai[x] = self.pai[self.pai[x]]
            x = self.pai[x]
        return x

    def unir(self, a, b):
        """Une os componentes de a e b. Devolve False se já estavam juntos."""
        a, b = self.raiz(a), self.raiz(b)
        if a == b:
            return False
        self.pai[a] = b
        return True


# ---------------------------------------------------------------------------------------------
# 1) Sintéticos em camadas (parecidos com DFGs)
# ---------------------------------------------------------------------------------------------
def gerar_sintetico(n, semente, reconvergencia=0.3, prob_duas_entradas=0.35, max_saidas=3, janela=8):
    """DAG conexo com n nós, criado em ordem topológica (cada nó só recebe arestas de nós anteriores).

    - Os primeiros n/8 nós são entradas (sem predecessores).
    - Cada nó seguinte escolhe um 1º operando entre os `janela` nós anteriores (localidade, como num DFG).
    - Com probabilidade `prob_duas_entradas`, ganha um 2º operando. Desses, uma fração `reconvergencia`
      é um "parente" do 1º operando (irmão ou pai), o que cria um caminho reconvergente curto.
    - Nenhum nó passa de `max_saidas` sucessores.
    - No fim, componentes soltos são ligados entre si para o grafo ficar conexo.
    """
    rng = random.Random(semente)
    n_entradas = max(1, n // 8)
    pred = [[] for _ in range(n)]
    succ = [[] for _ in range(n)]
    arestas = []

    def pode_alimentar(u):
        return len(succ[u]) < max_saidas

    def adicionar(u, v):
        arestas.append((u, v))
        succ[u].append(v)
        pred[v].append(u)

    for i in range(n_entradas, n):
        inicio = max(0, i - janela)
        candidatos = ([u for u in range(inicio, i) if pode_alimentar(u)]
                      or [u for u in range(i) if pode_alimentar(u)]
                      or list(range(i)))
        a = rng.choice(candidatos)
        adicionar(a, i)
        if rng.random() < prob_duas_entradas:
            b = None
            if rng.random() < reconvergencia:
                parentes = {s for p in pred[a] for s in succ[p]} | set(pred[a])
                parentes = [x for x in parentes
                            if x != a and x < i and pode_alimentar(x) and x not in pred[i]]
                if parentes:
                    b = rng.choice(parentes)
            if b is None:
                outros = [u for u in candidatos if u != a]
                if outros:
                    b = rng.choice(outros)
            if b is not None:
                adicionar(b, i)

    # liga componentes soltos (mantendo a ordem topológica: sempre do nó menor para o maior)
    uf = UnionFind(n)
    for u, v in arestas:
        uf.unir(u, v)
    componentes = {}
    for v in range(n):
        componentes.setdefault(uf.raiz(v), []).append(v)
    componentes = sorted(componentes.values(), key=min)
    for comp_a, comp_b in zip(componentes, componentes[1:]):
        u, v = min(comp_a), max(comp_b)
        if u > v:
            u, v = v, u
        adicionar(u, v)
    return arestas


# ---------------------------------------------------------------------------------------------
# 2) Grafos com ótimo conhecido
# ---------------------------------------------------------------------------------------------
def gerar_otimo(lado, semente, extra=0.3):
    """Grafo cujo melhor posicionamento é conhecido: WL ótimo = |E|.

    1. Parte de uma grade lado×lado cheia: cada célula vira um nó.
    2. Sorteia uma árvore usando só arestas entre células vizinhas (garante que o grafo é conexo).
    3. Acrescenta `extra` (30%) das arestas vizinhas que sobraram, criando reconvergências.
    4. Orienta cada aresta segundo uma ordem aleatória dos nós (garante que não há ciclo dirigido).
    5. Embaralha os rótulos, para que nenhum algoritmo "enxergue" a grade original.
    Como toda aresta liga células vizinhas, colocar cada nó de volta na sua célula original dá
    comprimento 1 para todas as arestas, e nenhum posicionamento pode ser melhor que isso.
    """
    rng = random.Random(semente)
    n = lado * lado
    malha = []
    for r in range(lado):
        for c in range(lado):
            v = r * lado + c
            if c + 1 < lado:
                malha.append((v, v + 1))          # vizinho à direita
            if r + 1 < lado:
                malha.append((v, v + lado))       # vizinho de baixo
    rng.shuffle(malha)

    uf = UnionFind(n)
    arvore, sobra = [], []
    for e in malha:
        (arvore if uf.unir(*e) else sobra).append(e)
    escolhidas = arvore + sobra[: round(extra * len(sobra))]

    ordem = list(range(n))
    rng.shuffle(ordem)
    rotulo = list(range(n))
    rng.shuffle(rotulo)
    arestas = [(rotulo[u], rotulo[v]) if ordem[u] < ordem[v] else (rotulo[v], rotulo[u])
               for u, v in escolhidas]
    return arestas


# ---------------------------------------------------------------------------------------------
# Escrita em DOT e conferências
# ---------------------------------------------------------------------------------------------
def salvar_dot(caminho, nome, n, arestas):
    linhas = [f"digraph {nome} {{"]
    linhas += [f"  n{v};" for v in range(n)]
    linhas += [f"  n{u} -> n{v};" for u, v in arestas]
    linhas.append("}")
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def conferir(n, arestas):
    """Confere que o grafo é um DAG conexo, sem laços nem arestas repetidas."""
    assert len(set(arestas)) == len(arestas), "aresta repetida"
    assert all(u != v for u, v in arestas), "laço"
    uf = UnionFind(n)
    for u, v in arestas:
        uf.unir(u, v)
    assert len({uf.raiz(v) for v in range(n)}) == 1, "grafo desconexo"
    # ordenação topológica (algoritmo de Kahn): se sobrar nó, há ciclo
    entrada = [0] * n
    succ = [[] for _ in range(n)]
    for u, v in arestas:
        succ[u].append(v)
        entrada[v] += 1
    fila = [v for v in range(n) if entrada[v] == 0]
    vistos = 0
    while fila:
        u = fila.pop()
        vistos += 1
        for v in succ[u]:
            entrada[v] -= 1
            if entrada[v] == 0:
                fila.append(v)
    assert vistos == n, "ciclo dirigido"


def main():
    pasta_sint = PASTA / "synthetic"
    pasta_otimo = PASTA / "optimal"
    pasta_sint.mkdir(parents=True, exist_ok=True)
    pasta_otimo.mkdir(parents=True, exist_ok=True)

    for n in TAMANHOS_SINTETICOS:
        for i in range(GRAFOS_POR_TAMANHO_SINTETICO):
            semente = 100 + i
            arestas = gerar_sintetico(n, semente)
            conferir(n, arestas)
            nome = f"synthetic_n{n}_s{semente}"
            salvar_dot(pasta_sint / f"{nome}.dot", nome, n, arestas)
    print(f"{len(TAMANHOS_SINTETICOS) * GRAFOS_POR_TAMANHO_SINTETICO} grafos em {pasta_sint}")

    for lado in LADOS_OTIMOS:
        for semente in range(GRAFOS_POR_TAMANHO_OTIMO):
            arestas = gerar_otimo(lado, semente)
            n = lado * lado
            conferir(n, arestas)
            nome = f"optimal_{lado}x{lado}_s{semente}"
            salvar_dot(pasta_otimo / f"{nome}.dot", nome, n, arestas)
    print(f"{len(LADOS_OTIMOS) * GRAFOS_POR_TAMANHO_OTIMO} grafos em {pasta_otimo}")


if __name__ == "__main__":
    main()
