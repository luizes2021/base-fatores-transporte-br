"""Gera um xlsx no formato REAL do SENATRAN (Frota por UF e Tipo).

Reproduz as armadilhas verificadas no arquivo de Dez/2023, porque uma fixture
que nao as reproduz faz o CI passar sem testar nada:

  - duas linhas de titulo antes do cabecalho
  - o titulo contem "Unidades da Federacao", igual ao rotulo da coluna —
    quem detecta o cabecalho por busca de texto cai no titulo
  - o rotulo da coluna tem QUEBRA DE LINHA dentro da celula
  - UFs por extenso, ACENTUADAS e com espacos sobrando
  - linhas de agregado (Brasil, Norte, Nordeste...) misturadas as de UF
  - coluna TOTAL, que e a soma da linha
  - uma SEGUNDA TABELA abaixo, com percentuais
  - linha de fonte no rodape
"""

import random
from pathlib import Path

import openpyxl

random.seed(7)

TIPOS = ["AUTOMÓVEL", "BONDE", "CAMINHÃO", "CAMINHÃO TRATOR", "CAMINHONETE",
         "CAMIONETA", "CHASSI PLATAFORMA", "CICLOMOTOR", "MICROÔNIBUS",
         "MOTOCICLETA", "MOTONETA", "ÔNIBUS", "QUADRICICLO", "REBOQUE",
         "SEMI-REBOQUE", "SIDE-CAR", "OUTROS", "TRATOR ESTEIRA",
         "TRATOR RODAS", "TRICICLO", "UTILITÁRIO"]

# Pesos por tipo, proporcionais a frota nacional real de Dez/2023.
PESO = {
    "AUTOMÓVEL": 61803, "BONDE": 0.04, "CAMINHÃO": 3088, "CAMINHÃO TRATOR": 893,
    "CAMINHONETE": 9524, "CAMIONETA": 4341, "CHASSI PLATAFORMA": 60,
    "CICLOMOTOR": 390, "MICROÔNIBUS": 420, "MOTOCICLETA": 23000,
    "MOTONETA": 7400, "ÔNIBUS": 700, "QUADRICICLO": 7, "REBOQUE": 2259,
    "SEMI-REBOQUE": 1306, "SIDE-CAR": 2, "OUTROS": 120,
    "TRATOR ESTEIRA": 10, "TRATOR RODAS": 29, "TRICICLO": 12,
    "UTILITÁRIO": 1581,
}

REGIOES = {
    "Norte": ["Acre ", "Amapá ", "Amazonas", "Pará ", "Rondônia ", "Roraima",
              "Tocantins"],
    "Nordeste": ["Alagoas", "Bahia", "Ceará", "Maranhão ", "Paraíba ",
                 "Pernambuco ", "Piauí", "Rio Grande do Norte ", "Sergipe"],
    "Sudeste": ["Espírito Santo", "Minas Gerais ", "Rio de Janeiro",
                "São Paulo "],
    "Sul": ["Paraná", "Rio Grande do Sul ", "Santa Catarina"],
    "Centro-Oeste": ["Distrito Federal", "Goiás", "Mato Grosso",
                     "Mato Grosso do Sul"],
}

PESO_UF = {
    "Acre ": 0.3, "Amapá ": 0.2, "Amazonas": 1.0, "Pará ": 2.3, "Rondônia ": 1.0,
    "Roraima": 0.24, "Tocantins": 0.75, "Alagoas": 1.0, "Bahia": 4.3,
    "Ceará": 3.0, "Maranhão ": 1.6, "Paraíba ": 1.3, "Pernambuco ": 3.0,
    "Piauí": 1.1, "Rio Grande do Norte ": 1.2, "Sergipe": 0.8,
    "Espírito Santo": 1.9, "Minas Gerais ": 12.0, "Rio de Janeiro": 7.0,
    "São Paulo ": 32.0, "Paraná": 8.5, "Rio Grande do Sul ": 7.5,
    "Santa Catarina": 5.5, "Distrito Federal": 2.0, "Goiás": 4.5,
    "Mato Grosso": 2.6, "Mato Grosso do Sul": 1.6,
}


def main() -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "MES_ANO"

    ws.append(["Frota de veículos, por tipo e com placa, segundo as Grandes "
               "Regiões e Unidades da Federação - DEZ/2023"])
    ws.append([])
    ws.append(["Grandes Regiões e\nUnidades da Federação", "TOTAL"] + TIPOS)

    peso_total = sum(PESO_UF.values())
    por_uf = {}
    for uf, peso in PESO_UF.items():
        fatia = peso / peso_total
        linha = {}
        for t in TIPOS:
            v = PESO[t] * 1000 * fatia * random.uniform(0.85, 1.15)
            linha[t] = int(round(v))
        por_uf[uf] = linha

    def total_de(ufs):
        return {t: sum(por_uf[u][t] for u in ufs) for t in TIPOS}

    todas = list(PESO_UF)
    br = total_de(todas)
    ws.append(["Brasil", sum(br.values())] + [br[t] for t in TIPOS])

    for regiao, ufs in REGIOES.items():
        reg = total_de(ufs)
        ws.append([regiao, sum(reg.values())] + [reg[t] for t in TIPOS])
        for uf in ufs:
            linha = por_uf[uf]
            ws.append([uf, sum(linha.values())] + [linha[t] for t in TIPOS])

    # segunda tabela, com percentuais — nao pode entrar na contagem
    ws.append([])
    ws.append([])
    ws.append(["Tabela 2 - Percentagem de veículos, por tipo segundo o Brasil "
               "- DEZ/2023"])
    total_br = sum(br.values())
    ws.append(["Brasil %", 100.0]
              + [round(br[t] / total_br * 100, 2) for t in TIPOS])
    ws.append([])
    ws.append(["Fonte: Ministério dos Transportes, SENATRAN - Secretaria "
               "Nacional de Trânsito, RENAVAM"])

    destino = Path(__file__).parent / "senatran_sintetico.xlsx"
    wb.save(destino)
    print(f"criado: {destino}")
    print(f"  frota Brasil: {total_br:,}")
    print(f"  razao semirreboques/cavalos: "
          f"{br['SEMI-REBOQUE'] / br['CAMINHÃO TRATOR']:.2f}")


if __name__ == "__main__":
    main()
