"""Gera um CSV no formato provavel do RNTRC - Dados de Veiculos (ANTT).

ATENCAO: o esquema real da ANTT nao esta documentado de forma estavel. Este
arquivo serve para testar o pipeline (leitura em blocos, agregacao, diagnostico
de acoplamento), NAO para validar nomes de coluna. Use --inspecionar no arquivo
verdadeiro antes de confiar no mapa.
"""

import csv
import random
from pathlib import Path

random.seed(23)

N_VEICULOS = 120_000

UFS = ["SP", "MG", "PR", "RS", "SC", "GO", "MT", "BA", "SP", "PR", "MG", "SP"]

TIPOS = {
    "CAMINHAO TRATOR": 0.17,
    "SEMI-REBOQUE": 0.33,
    "CAMINHAO": 0.40,
    "REBOQUE": 0.06,
    "CAMINHONETE": 0.04,
}

TRANSPORTADORES = {"TAC": 0.50, "ETC": 0.45, "CTC": 0.05}


def sorteia(pesos: dict) -> str:
    return random.choices(list(pesos), weights=list(pesos.values()))[0]


def main() -> None:
    destino = Path(__file__).parent / "rntrc_veiculos_sintetico.csv"
    with open(destino, "w", encoding="latin-1", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["PLACA", "UF PLACA", "TIPO VEICULO", "ANO FABRICACAO",
                    "TIPO TRANSPORTADOR", "SITUACAO"])
        for i in range(N_VEICULOS):
            placa = f"ABC{i % 10000:04d}"
            ano = random.choices(
                range(1995, 2025),
                weights=[1] * 10 + [2] * 10 + [4] * 10,  # frota mais nova pesa mais
            )[0]
            w.writerow([placa, random.choice(UFS), sorteia(TIPOS), ano,
                        sorteia(TRANSPORTADORES), "ATIVO"])
    print(f"criado: {destino} ({N_VEICULOS:,} linhas)")


if __name__ == "__main__":
    main()
