"""Gera um CSV no formato documentado do INEAVAR (MMA).

Segue o dicionario de dados publicado: Categoria, CategoriaSucat, Motor,
Combustivel, Fase, AnoModelo, AnoCalendario, Idade, Frota, km_preliminar,
km_ajustado, L_preliminar, L_ajustado, combustivel_fracao_fossil,
combustivel_fracao_renovavel, gCH4/km, gN2O/km, gco2_*.

Reproduz: encoding UTF-8 com BOM, separador ';', decimal com virgula, e a
desagregacao por ano-modelo e idade que precisa ser agregada antes de somar.

ATENCAO: o extrator 05 ainda NAO foi validado contra o arquivo real do MMA —
esta fixture segue o dicionario publicado, nao o arquivo. Rode
`--inspecionar` no arquivo verdadeiro antes de confiar no mapeamento.
"""

import csv
import random
from pathlib import Path

random.seed(5)

# (categoria, L/km tipico, km/ano por veiculo)
CATEGORIAS = [
    ("CAMINHAO SEMILEVE", 0.17, 22000),
    ("CAMINHAO LEVE", 0.22, 28000),
    ("CAMINHAO MEDIO", 0.28, 45000),
    ("CAMINHAO SEMIPESADO", 0.34, 62000),
    ("CAMINHAO PESADO", 0.42, 95000),
    ("ONIBUS URBANO", 0.38, 58000),
    ("ONIBUS RODOVIARIO", 0.33, 72000),
]

FASES = ["P5", "P6", "P7", "P8"]
ANO_CAL = 2024
FRACAO_BIO = 0.14          # mandato de biodiesel do ano de referencia


def br(v: float, casas: int = 1) -> str:
    return f"{v:.{casas}f}".replace(".", ",")


def main() -> None:
    destino = Path(__file__).parent / "ineavar_sintetico.csv"
    with open(destino, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([
            "Categoria", "CategoriaSucat", "Motor", "Combustível", "Fase",
            "AnoModelo", "AnoCalendario", "Idade", "Frota",
            "km_preliminar", "km_ajustado", "L_preliminar", "L_ajustado",
            "combustivel_fracao_fossil", "combustivel_fracao_renovavel",
            "gCH4/km", "gN2O/km",
            "gco2_fossil", "gco2_renovavel", "gco2_total",
        ])
        for cat, lkm, km_veic in CATEGORIAS:
            sucat = "ONIBUS" if cat.startswith("ONIBUS") else "CAMINHAO"
            for fase in FASES:
                for ano_modelo in range(2014, ANO_CAL + 1):
                    idade = ANO_CAL - ano_modelo
                    frota = random.randint(8_000, 90_000)
                    # veiculo mais velho roda menos
                    km = frota * km_veic * random.uniform(.9, 1.1) * (0.97 ** idade)
                    litros = km * lkm * random.uniform(.95, 1.05)
                    fossil = litros * (1 - FRACAO_BIO)
                    renov = litros * FRACAO_BIO
                    w.writerow([
                        cat, sucat, "DIESEL", "ÓLEO DIESEL", fase,
                        ano_modelo, ANO_CAL, idade, frota,
                        br(km * 0.98), br(km), br(litros * 0.98), br(litros),
                        br(fossil), br(renov),
                        "0,006", "0,030",
                        f"{fossil * 2600:.0f}", f"{renov * 2500:.0f}",
                        f"{litros * 2580:.0f}",
                    ])
    print(f"criado: {destino}")


if __name__ == "__main__":
    main()
