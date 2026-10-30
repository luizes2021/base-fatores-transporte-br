"""Gera um xlsx no formato REAL do arquivo de tipo/especie/eixos do SENATRAN.

Reproduz as armadilhas verificadas em Dez/2023:
  - linhas com UF 'Nao Identificado', 'Sem Informacao', 'Nao se Aplica'
  - EIXOS = 0 significando 'nao informado', nao 'zero eixos'
  - valores de eixos impossiveis (negativos, acima de 9)
  - granularidade municipal, com muitas linhas por UF
As proporcoes de eixos seguem as reais, para que o modelo de acoplamento
tenha entrada plausivel.

NOTA: esta fixture e a de 'Frota por UF e Tipo' sao geradas de forma
independente, entao NAO reconciliam entre si. A reconciliacao so faz sentido
com os arquivos reais, onde os dois saem do mesmo RENAVAM — e la bate: em
Dez/2023, 3 veiculos de diferenca em 119 milhoes.
"""

import random
from pathlib import Path

import openpyxl

random.seed(31)

# As 27 UFs, por extenso, como no arquivo real.
UFS = ["ACRE", "ALAGOAS", "AMAPA", "AMAZONAS", "BAHIA", "CEARA",
       "DISTRITO FEDERAL", "ESPIRITO SANTO", "GOIAS", "MARANHAO",
       "MATO GROSSO", "MATO GROSSO DO SUL", "MINAS GERAIS", "PARA",
       "PARAIBA", "PARANA", "PERNAMBUCO", "PIAUI", "RIO DE JANEIRO",
       "RIO GRANDE DO NORTE", "RIO GRANDE DO SUL", "RONDONIA", "RORAIMA",
       "SANTA CATARINA", "SAO PAULO", "SERGIPE", "TOCANTINS"]

MUNICIPIOS = ["CAPITAL", "INTERIOR A", "INTERIOR B", "INTERIOR C"]

# (tipo, especie, {eixos: peso}) — proporcoes proximas as reais de Dez/2023
PERFIS = [
    ("CAMINHAO", "CARGA", {0: 0.31, 1: 0.003, 2: 0.35, 3: 0.31, 4: 0.03}),
    ("CAMINHAO", "ESPECIAL", {0: 0.5, 2: 0.3, 3: 0.2}),
    ("CAMINHAO TRATOR", "TRACAO", {0: 0.20, 2: 0.13, 3: 0.66, 4: 0.01}),
    ("SEMI-REBOQUE", "CARGA", {0: 0.18, 1: 0.02, 2: 0.27, 3: 0.50, 4: 0.03}),
    ("REBOQUE", "CARGA", {0: 0.34, 1: 0.54, 2: 0.10, 3: 0.01, 4: 0.01}),
    ("AUTOMOVEL", "PASSAGEIRO", {0: 0.6, 2: 0.4}),
    ("ONIBUS", "PASSAGEIRO", {0: 0.4, 2: 0.4, 3: 0.2}),
    ("MOTOCICLETA", "PASSAGEIRO", {0: 1.0}),
]

# volume nacional aproximado por (tipo, especie), em milhares
VOLUME = {
    ("CAMINHAO", "CARGA"): 2958, ("CAMINHAO", "ESPECIAL"): 132,
    ("CAMINHAO TRATOR", "TRACAO"): 911, ("SEMI-REBOQUE", "CARGA"): 1320,
    ("REBOQUE", "CARGA"): 2425, ("AUTOMOVEL", "PASSAGEIRO"): 61803,
    ("ONIBUS", "PASSAGEIRO"): 700, ("MOTOCICLETA", "PASSAGEIRO"): 23000,
}


def main() -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Layout_G"
    ws.append(["UF", "Município", "Tipo Veículo", "Espécie Veículo", "Eixos",
               "Qtd. Veículos"])

    peso_uf = {uf: random.uniform(0.4, 3.0) for uf in UFS}
    total_peso = sum(peso_uf.values())

    for uf in UFS:
        fatia_uf = peso_uf[uf] / total_peso
        for mun in MUNICIPIOS:
            fatia = fatia_uf / len(MUNICIPIOS)
            for tipo, especie, dist in PERFIS:
                base = VOLUME[(tipo, especie)] * 1000 * fatia
                for eixos, peso in dist.items():
                    v = int(round(base * peso * random.uniform(0.85, 1.15)))
                    if v > 0:
                        ws.append([uf, mun, tipo, especie, eixos, v])

    # linhas com UF nao identificada — precisam ser descartadas
    for rotulo in ["Não Identificado", "Sem Informação", "Não se Aplica"]:
        ws.append([rotulo, "Não Identificado", "CAMINHAO", "CARGA", 0,
                   random.randint(5000, 40000)])
        ws.append([rotulo, "Não Identificado", "AUTOMOVEL", "PASSAGEIRO", 0,
                   random.randint(50000, 400000)])

    # eixos impossiveis — erro de cadastro
    ws.append(["SAO PAULO", "CAPITAL", "CAMINHAO", "CARGA", -2, 37])
    ws.append(["SAO PAULO", "CAPITAL", "CAMINHAO", "CARGA", 30, 112])
    ws.append(["PARANA", "INTERIOR A", "SEMI-REBOQUE", "CARGA", 99, 8])

    destino = Path(__file__).parent / "senatran_eixos_sintetico.xlsx"
    wb.save(destino)
    print(f"criado: {destino} ({ws.max_row - 1:,} linhas)")


if __name__ == "__main__":
    main()
