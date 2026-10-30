"""
03_extrai_rntrc.py — camada 00_brutos -> 10_extraidos

Le o arquivo "RNTRC - Dados de Veiculos" (ANTT) e agrega para:

    ano_ref | uf | tipo_rntrc | ano_fabricacao | tipo_transportador | n_veiculos

Por que a RNTRC importa: ela e a melhor aproximacao publica de FROTA ATIVA
de carga. O SENATRAN nao tem baixa obrigatoria efetiva e esta inflado nas
faixas antigas. A RNTRC so inclui transportadores com situacao ATIVO — o que
corrige o vies para baixo, mas introduz outro: frota propria (carga privada,
nao remunerada) fica de fora. Nenhuma das duas e a verdade; a combinacao e.

O arquivo e grande (uma linha por veiculo). O script le em blocos e nunca
carrega tudo em memoria.

DESCOBERTA DE ESQUEMA
O layout da ANTT nao esta documentado de forma estavel. Em vez de adivinhar
nomes de coluna, rode primeiro:

    python codigo/03_extrai_rntrc.py <arquivo.csv> --inspecionar

Isso imprime as colunas reais e valores de exemplo. Depois preencha
crosswalk/rntrc_colunas.csv mapeando as colunas do arquivo para os papeis
canonicos e rode a extracao normal.

Uso:
    python codigo/03_extrai_rntrc.py <arquivo.csv> --inspecionar
    python codigo/03_extrai_rntrc.py <arquivo.csv> --ano 2024
"""

import argparse
import hashlib
import sys
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "dados" / "10_extraidos"
MAPA_COLUNAS = RAIZ / "crosswalk" / "rntrc_colunas.csv"

BLOCO = 200_000

PAPEIS = ["uf", "tipo_rntrc", "ano_fabricacao", "tipo_transportador"]

# Palpites iniciais. Servem so para o modo --inspecionar sugerir um mapa;
# a extracao usa o CSV do crosswalk, nunca estes palpites.
PALPITES = {
    "uf": ["UF", "UF PLACA", "UF VEICULO", "SIGLA UF", "ESTADO"],
    "tipo_rntrc": ["TIPO VEICULO", "TIPO DE VEICULO", "DESCRICAO TIPO VEICULO",
                   "CARROCERIA", "TIPO"],
    "ano_fabricacao": ["ANO FABRICACAO", "ANO DE FABRICACAO", "ANO FABRIC",
                       "ANO MODELO"],
    "tipo_transportador": ["TIPO TRANSPORTADOR", "TIPO DE TRANSPORTADOR",
                           "CATEGORIA", "TIPO RNTRC"],
}

UF_VALIDAS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
}

# Tipos que representam unidade tratora (o cavalo) no vocabulario da ANTT.
# Usado so para o diagnostico de acoplamento; nao decide classe canonica.
MARCA_TRATORA = ("TRATOR", "CAVALO")
MARCA_REBOCADA = ("SEMI", "REBOQUE")


def normaliza(texto) -> str:
    if pd.isna(texto):
        return ""
    s = unicodedata.normalize("NFKD", str(texto))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.upper().replace("-", " ").replace(".", " ").replace("_", " ")
    s = "".join(c for c in s if c.isalnum() or c.isspace())
    return " ".join(s.split())


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def detecta_dialeto(caminho: Path):
    """Descobre encoding e separador lendo so as primeiras linhas."""
    for enc in ("latin-1", "utf-8-sig", "cp1252"):
        for sep in (";", ",", "|", "\t"):
            try:
                amostra = pd.read_csv(caminho, sep=sep, encoding=enc,
                                      dtype=str, nrows=50)
                if amostra.shape[1] >= 3:
                    return enc, sep
            except Exception:  # noqa: BLE001
                continue
    raise ValueError("nao foi possivel detectar encoding/separador do arquivo")


def inspeciona(caminho: Path) -> None:
    enc, sep = detecta_dialeto(caminho)
    amostra = pd.read_csv(caminho, sep=sep, encoding=enc, dtype=str, nrows=2000)
    print(f"encoding={enc}  separador='{sep}'  colunas={amostra.shape[1]}\n")

    normalizadas = {c: normaliza(c) for c in amostra.columns}
    print(f"{'COLUNA NO ARQUIVO':<38} {'VALORES DISTINTOS (amostra)':<46} PAPEL?")
    print("-" * 110)

    sugestoes = {}
    for col, norm in normalizadas.items():
        distintos = amostra[col].dropna().unique()[:4]
        exemplo = " | ".join(str(v)[:18] for v in distintos)
        papel = ""
        for p, nomes in PALPITES.items():
            if norm in nomes and p not in sugestoes:
                papel, sugestoes[p] = p, col
                break
        print(f"{col[:37]:<38} {exemplo[:45]:<46} {papel}")

    print("\nSugestao para crosswalk/rntrc_colunas.csv:")
    print("papel,coluna_arquivo")
    for p in PAPEIS:
        print(f"{p},{sugestoes.get(p, '<PREENCHER>')}")
    faltando = [p for p in PAPEIS if p not in sugestoes]
    if faltando:
        print(f"\nAVISO: papeis sem palpite: {faltando}. Escolha a coluna na "
              "tabela acima e preencha a mao.", file=sys.stderr)


def le_mapa() -> dict:
    if not MAPA_COLUNAS.exists():
        sys.exit(
            f"mapa de colunas ausente: {MAPA_COLUNAS}\n"
            "Rode primeiro com --inspecionar e salve a sugestao nesse arquivo."
        )
    mapa_df = pd.read_csv(MAPA_COLUNAS)
    mapa = dict(zip(mapa_df["papel"], mapa_df["coluna_arquivo"]))
    pendentes = [p for p, c in mapa.items() if str(c).startswith("<")]
    if pendentes:
        sys.exit(f"papeis ainda nao preenchidos no mapa: {pendentes}")
    if "uf" not in mapa or "tipo_rntrc" not in mapa:
        sys.exit("o mapa precisa ao menos de 'uf' e 'tipo_rntrc'")
    return mapa


def extrai(caminho: Path, ano_ref: int) -> pd.DataFrame:
    mapa = le_mapa()
    enc, sep = detecta_dialeto(caminho)
    print(f"  encoding={enc} separador='{sep}'")

    cabecalho = pd.read_csv(caminho, sep=sep, encoding=enc, dtype=str, nrows=0)
    por_norm = {normaliza(c): c for c in cabecalho.columns}

    usar, renomear = [], {}
    for papel, col in mapa.items():
        real = col if col in cabecalho.columns else por_norm.get(normaliza(col))
        if real is None:
            sys.exit(f"coluna '{col}' (papel {papel}) nao existe no arquivo")
        usar.append(real)
        renomear[real] = papel

    acumulado, total_lido = [], 0
    for bloco in pd.read_csv(caminho, sep=sep, encoding=enc, dtype=str,
                             usecols=usar, chunksize=BLOCO):
        total_lido += len(bloco)
        bloco = bloco.rename(columns=renomear)

        bloco["uf"] = bloco["uf"].map(normaliza).str[-2:]
        bloco = bloco[bloco["uf"].isin(UF_VALIDAS)]
        bloco["tipo_rntrc"] = bloco["tipo_rntrc"].map(normaliza)

        if "ano_fabricacao" in bloco.columns:
            bloco["ano_fabricacao"] = pd.to_numeric(
                bloco["ano_fabricacao"], errors="coerce").astype("Int64")
            bloco.loc[~bloco["ano_fabricacao"].between(1950, 2100),
                      "ano_fabricacao"] = pd.NA
        else:
            bloco["ano_fabricacao"] = pd.NA

        if "tipo_transportador" in bloco.columns:
            bloco["tipo_transportador"] = bloco["tipo_transportador"].map(normaliza)
        else:
            bloco["tipo_transportador"] = "NAO INFORMADO"

        chaves = ["uf", "tipo_rntrc", "ano_fabricacao", "tipo_transportador"]
        acumulado.append(
            bloco.groupby(chaves, dropna=False).size().rename("n_veiculos")
        )
        print(f"    {total_lido:,} linhas lidas", end="\r")

    print()
    if not acumulado:
        raise ValueError("nenhuma linha valida lida")

    df = (pd.concat(acumulado).groupby(level=[0, 1, 2, 3]).sum()
          .reset_index().sort_values("n_veiculos", ascending=False,
                                     ignore_index=True))
    df["ano_ref"] = int(ano_ref)
    df["id_fonte"] = "antt_rntrc_veiculos"
    df["sha256_origem"] = sha256(caminho)
    return df


def valida(df: pd.DataFrame) -> None:
    total = int(df["n_veiculos"].sum())
    print(f"  total de veiculos: {total:,}")
    print(f"  UFs: {df['uf'].nunique()}  tipos distintos: {df['tipo_rntrc'].nunique()}")

    tipos = df.groupby("tipo_rntrc")["n_veiculos"].sum().sort_values(ascending=False)
    print("\n  tipos mais frequentes:")
    print(tipos.head(12).to_string())

    tratores = tipos[[any(m in t for m in MARCA_TRATORA) for t in tipos.index]].sum()
    rebocadas = tipos[[any(m in t for m in MARCA_REBOCADA) for t in tipos.index]].sum()
    if tratores and rebocadas:
        print(f"\n  unidades tratoras: {tratores:,}")
        print(f"  unidades rebocadas: {rebocadas:,}")
        print(f"  razao rebocadas/tratoras = {rebocadas / tratores:.2f}")
        print("  -> insumo do modelo de acoplamento (etapa 20); a razao sozinha")
        print("     nao distingue carreta de bitrem/rodotrem.")
    else:
        print("\n  AVISO: nao identifiquei tratoras e/ou rebocadas pelo nome do "
              "tipo. Revise o vocabulario em MARCA_TRATORA/MARCA_REBOCADA.",
              file=sys.stderr)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("arquivo", type=Path)
    p.add_argument("--inspecionar", action="store_true",
                   help="imprime colunas e valores de exemplo, sem extrair")
    p.add_argument("--ano", type=int, default=None)
    a = p.parse_args()

    if not a.arquivo.exists():
        sys.exit(f"arquivo nao encontrado: {a.arquivo}")

    if a.inspecionar:
        inspeciona(a.arquivo)
        return

    if not a.ano:
        sys.exit("informe --ano (a RNTRC e um retrato na data da extracao)")

    df = extrai(a.arquivo, a.ano)
    valida(df)

    SAIDA.mkdir(parents=True, exist_ok=True)
    destino = SAIDA / f"rntrc_veiculos_{a.ano}.parquet"
    df.to_parquet(destino, index=False)
    print(f"\n  {len(df)} linhas agregadas -> {destino}")


if __name__ == "__main__":
    main()
