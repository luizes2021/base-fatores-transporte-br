"""Gera CSVs no formato das vendas de derivados da ANP, nos DOIS layouts.

  anp_vendas_sintetico.csv        layout LONGO (uma linha por mes)
  anp_vendas_largo_sintetico.csv  layout LARGO — o das series historicas:
      COMBUSTIVEL | ANO | REGIAO | ESTADO | UNIDADE | JANEIRO..DEZEMBRO | TOTAL

Reproduz as armadilhas do arquivo real: separador ';', decimal ',', milhar '.',
encoding latin-1, UF por extenso, mes por nome, e a coluna TOTAL que duplicaria
o volume se entrasse na soma.

Os dois arquivos contem os MESMOS numeros, entao os dois devem produzir o mesmo
total extraido. Se divergirem, ha bug no tratamento de um dos layouts.
"""

import csv
import random
from pathlib import Path

random.seed(11)

UFS = {
    "ACRE": ("NORTE", 0.3), "ALAGOAS": ("NORDESTE", 0.8),
    "AMAPA": ("NORTE", 0.2), "AMAZONAS": ("NORTE", 1.0),
    "BAHIA": ("NORDESTE", 4.5), "CEARA": ("NORDESTE", 2.6),
    "DISTRITO FEDERAL": ("CENTRO-OESTE", 1.0), "ESPIRITO SANTO": ("SUDESTE", 1.8),
    "GOIAS": ("CENTRO-OESTE", 4.8), "MARANHAO": ("NORDESTE", 2.2),
    "MATO GROSSO": ("CENTRO-OESTE", 5.5), "MATO GROSSO DO SUL": ("CENTRO-OESTE", 2.6),
    "MINAS GERAIS": ("SUDESTE", 9.5), "PARA": ("NORTE", 2.8),
    "PARAIBA": ("NORDESTE", 1.1), "PARANA": ("SUL", 6.2),
    "PERNAMBUCO": ("NORDESTE", 2.6), "PIAUI": ("NORDESTE", 1.1),
    "RIO DE JANEIRO": ("SUDESTE", 3.6), "RIO GRANDE DO NORTE": ("NORDESTE", 1.0),
    "RIO GRANDE DO SUL": ("SUL", 6.0), "RONDONIA": ("NORTE", 1.1),
    "RORAIMA": ("NORTE", 0.2), "SANTA CATARINA": ("SUL", 4.2),
    "SAO PAULO": ("SUDESTE", 17.0), "SERGIPE": ("NORDESTE", 0.7),
    "TOCANTINS": ("NORTE", 1.2),
}

MESES = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO",
         "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]

PRODUTOS = {
    "ÓLEO DIESEL S-10": 0.60,
    "ÓLEO DIESEL S-500": 0.40,
    "ÓLEO DIESEL MARÍTIMO": 0.012,
    "GASOLINA C": 0.0,   # entra para testar o filtro de produto
}

TOTAL_M3 = 61_000_000  # ~61 bilhoes de litros/ano


def br(valor: float) -> str:
    """1234567.89 -> '1.234.567,89'"""
    return f"{valor:,.3f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def gera_valores() -> dict:
    """{(produto, uf): [12 valores]} — a mesma matriz alimenta os dois layouts."""
    peso_total = sum(p for _, p in UFS.values())
    dados = {}
    for produto, share in PRODUTOS.items():
        for uf, (_, peso) in UFS.items():
            fatia = 0.5 if produto == "GASOLINA C" else share
            base = TOTAL_M3 * fatia / 12 * (peso / peso_total)
            dados[(produto, uf)] = [base * random.uniform(0.88, 1.12)
                                    for _ in range(12)]
    return dados


def escreve_longo(dados: dict, destino: Path) -> None:
    with open(destino, "w", encoding="latin-1", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["ANO", "MES", "UNIDADE DA FEDERACAO", "PRODUTO", "VENDAS M3"])
        for i, mes in enumerate(MESES):
            for (produto, uf), valores in dados.items():
                w.writerow([2024, mes, uf, produto, br(valores[i])])


def escreve_largo(dados: dict, destino: Path) -> None:
    with open(destino, "w", encoding="latin-1", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["COMBUSTÍVEL", "ANO", "REGIÃO", "ESTADO", "UNIDADE"]
                   + MESES + ["TOTAL"])
        for (produto, uf), valores in dados.items():
            regiao = UFS[uf][0]
            w.writerow([produto, 2024, regiao, uf, "m3"]
                       + [br(v) for v in valores] + [br(sum(valores))])


def main() -> None:
    aqui = Path(__file__).parent
    dados = gera_valores()

    longo = aqui / "anp_vendas_sintetico.csv"
    largo = aqui / "anp_vendas_largo_sintetico.csv"
    escreve_longo(dados, longo)
    escreve_largo(dados, largo)

    diesel = sum(sum(v) for (p, _), v in dados.items() if "DIESEL" in p)
    print(f"criado: {longo}")
    print(f"criado: {largo}")
    print(f"diesel esperado nos dois: {diesel * 1000 / 1e9:.1f} bilhoes de litros")


if __name__ == "__main__":
    main()
