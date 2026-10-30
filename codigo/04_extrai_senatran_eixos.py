"""
04_extrai_senatran_eixos.py — camada 00_brutos -> 10_extraidos

Le "Frota por UF, Municipio, Tipo, Especie e Eixos" (SENATRAN) e devolve:

    ano_ref | mes_ref | uf | tipo | especie | eixos | n_veiculos

POR QUE ESTE ARQUIVO IMPORTA
Ele traz a CONTAGEM DE EIXOS, que nenhuma outra fonte publica brasileira
oferece de graca. Com ela:

  - os caminhoes rigidos se separam sozinhos: 2 eixos (toco/VUC),
    3 (truck), 4 (bitruck). Isso era o que dependia do Sindipecas em PDF.
  - os semirreboques se separam por eixos, o que da ao modelo de acoplamento
    DUAS restricoes em vez de uma:
        semis de 2 eixos = carreta5 + 2 x bitrem
        semis de 3 eixos = carreta6 + 2 x rodotrem
    Uma equacao com cinco incognitas vira um sistema bem mais identificavel.

LIMITE QUE PRECISA SER DECLARADO
Parte da frota tem EIXOS = 0, que e 'nao informado', nao 'zero eixos'. Em
Dez/2023 isso era ~30% dos caminhoes e ~18% dos semirreboques. Supor que os
nao informados seguem a mesma distribuicao dos informados e uma HIPOTESE, nao
um dado — provavelmente os registros antigos concentram a omissao. O script
calcula e publica essa fracao para que a hipotese fique visivel.

Ha tambem valores impossiveis (eixos negativos, ou 20, 30, 99). Sao erro de
cadastro. O script os separa em vez de descartar em silencio.

RECONCILIACAO COM O ARQUIVO 'FROTA POR UF E TIPO'
Depois de descartar as linhas com UF 'Nao Identificado'/'Sem Informacao'
(~2,66 milhoes em Dez/2023), os dois arquivos batem: 119.227.654 aqui contra
119.227.657 la — 3 veiculos de diferenca em 119 milhoes. Vale conferir isso a
cada atualizacao: e a validacao cruzada mais forte disponivel entre dois
arquivos independentes da mesma fonte.

Uso:
    python codigo/04_extrai_senatran_eixos.py <arquivo.xlsx> 2023 --mes 12
    python codigo/04_extrai_senatran_eixos.py <arquivo.xlsx> --inspecionar
"""

import argparse
import hashlib
import sys
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "dados" / "10_extraidos"

UF_POR_NOME = {
    "ACRE": "AC", "ALAGOAS": "AL", "AMAPA": "AP", "AMAZONAS": "AM",
    "BAHIA": "BA", "CEARA": "CE", "DISTRITO FEDERAL": "DF",
    "ESPIRITO SANTO": "ES", "GOIAS": "GO", "MARANHAO": "MA",
    "MATO GROSSO": "MT", "MATO GROSSO DO SUL": "MS", "MINAS GERAIS": "MG",
    "PARA": "PA", "PARAIBA": "PB", "PARANA": "PR", "PERNAMBUCO": "PE",
    "PIAUI": "PI", "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN",
    "RIO GRANDE DO SUL": "RS", "RONDONIA": "RO", "RORAIMA": "RR",
    "SANTA CATARINA": "SC", "SAO PAULO": "SP", "SERGIPE": "SE",
    "TOCANTINS": "TO",
}
SIGLAS = set(UF_POR_NOME.values())

# EIXOS = 0 significa 'nao informado'. Acima de 9 e erro de cadastro:
# nenhuma CVC rodoviaria brasileira passa de 9 eixos.
EIXOS_MAX_PLAUSIVEL = 9

TIPOS_CARGA = {"CAMINHAO", "CAMINHAO TRATOR", "SEMI REBOQUE", "REBOQUE",
               "UTILITARIO"}

PAPEIS = {
    "uf": ("UF",),
    "municipio": ("MUNICIPIO",),
    "tipo": ("TIPO VEICULO", "TIPO DO VEICULO", "TIPO"),
    "especie": ("ESPECIE VEICULO", "ESPECIE DO VEICULO", "ESPECIE"),
    "eixos": ("EIXOS", "QTD EIXOS", "NUMERO DE EIXOS"),
    "qtd": ("QTD VEICULOS", "QUANTIDADE", "QTD", "QUANTIDADE DE VEICULOS"),
}


def normaliza(texto) -> str:
    if pd.isna(texto):
        return ""
    s = unicodedata.normalize("NFKD", str(texto))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.upper().replace("-", " ").replace("/", " ").replace(".", " ")
    s = "".join(c if (c.isalnum() or c.isspace()) else " " for c in s)
    return " ".join(s.split())


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def mapeia_colunas(cols) -> dict:
    norm = {normaliza(c): c for c in cols}
    mapa = {}
    for papel, nomes in PAPEIS.items():
        for n in nomes:
            if n in norm:
                mapa[papel] = norm[n]
                break
    faltando = set(PAPEIS) - set(mapa) - {"municipio"}
    if faltando:
        raise ValueError(
            f"colunas nao encontradas: {sorted(faltando)}. "
            f"Vistas: {sorted(norm)}"
        )
    return mapa


def inspeciona(caminho: Path) -> None:
    xl = pd.ExcelFile(caminho)
    print(f"  abas: {xl.sheet_names}")
    d = pd.read_excel(caminho, sheet_name=xl.sheet_names[0], dtype=object)
    print(f"  {len(d):,} linhas x {len(d.columns)} colunas")
    print(f"  colunas: {list(d.columns)}\n")
    try:
        mapa = mapeia_colunas(d.columns)
        print(f"  mapeamento: {mapa}\n")
    except ValueError as e:
        print(f"  {e}", file=sys.stderr)
        return
    for papel in ("tipo", "especie"):
        vals = sorted({normaliza(v) for v in d[mapa[papel]].dropna().unique()})
        print(f"  {papel} ({len(vals)}): {vals[:30]}")
    eixos = pd.to_numeric(d[mapa["eixos"]], errors="coerce").dropna()
    print(f"\n  eixos: min={int(eixos.min())} max={int(eixos.max())} "
          f"distintos={eixos.nunique()}")


def extrai(caminho: Path, ano_ref: int, mes_ref=None) -> pd.DataFrame:
    xl = pd.ExcelFile(caminho)
    d = pd.read_excel(caminho, sheet_name=xl.sheet_names[0], dtype=object)
    print(f"  {len(d):,} linhas lidas da aba '{xl.sheet_names[0]}'")

    mapa = mapeia_colunas(d.columns)
    d = d.rename(columns={v: k for k, v in mapa.items()})

    d["uf_norm"] = d["uf"].map(normaliza)
    d["uf"] = d["uf_norm"].map(UF_POR_NOME)
    d.loc[d["uf_norm"].isin(SIGLAS), "uf"] = d["uf_norm"]

    d["qtd"] = pd.to_numeric(d["qtd"], errors="coerce").fillna(0)
    fora = d[d["uf"].isna()]
    if len(fora):
        rotulos = sorted({r for r in fora["uf_norm"] if r})
        print(f"  {int(fora['qtd'].sum()):,} veiculos em UF nao identificada "
              f"({rotulos}) — descartados")
    d = d[d["uf"].notna()].copy()

    d["tipo"] = d["tipo"].map(normaliza)
    d["especie"] = d["especie"].map(normaliza)
    d["eixos"] = pd.to_numeric(d["eixos"], errors="coerce").astype("Int64")

    # eixos impossiveis viram <NA>, mas o volume e reportado
    impossivel = (d["eixos"] < 0) | (d["eixos"] > EIXOS_MAX_PLAUSIVEL)
    n_imp = int(d.loc[impossivel, "qtd"].sum())
    if n_imp:
        vistos = sorted(d.loc[impossivel, "eixos"].dropna().unique())
        print(f"  {n_imp:,} veiculos com eixos impossiveis {vistos[:8]} "
              f"-> marcados como nao informado")
    d.loc[impossivel, "eixos"] = pd.NA

    # 0 = nao informado, nao 'zero eixos'
    n_zero = int(d.loc[d["eixos"] == 0, "qtd"].sum())
    d.loc[d["eixos"] == 0, "eixos"] = pd.NA
    print(f"  {n_zero:,} veiculos com eixos=0 (nao informado)")

    g = (d.groupby(["uf", "tipo", "especie", "eixos"], dropna=False)["qtd"]
         .sum().reset_index().rename(columns={"qtd": "n_veiculos"}))
    g["n_veiculos"] = g["n_veiculos"].astype("int64")
    g = g[g["n_veiculos"] > 0]

    g["ano_ref"] = int(ano_ref)
    g["mes_ref"] = int(mes_ref) if mes_ref else pd.NA
    g["id_fonte"] = "senatran_tipo_especie_eixos"
    g["sha256_origem"] = sha256(caminho)

    cols = ["ano_ref", "mes_ref", "uf", "tipo", "especie", "eixos",
            "n_veiculos", "id_fonte", "sha256_origem"]
    return g[cols].sort_values(["uf", "tipo", "especie", "eixos"],
                               ignore_index=True)


def relata(df: pd.DataFrame) -> None:
    n_uf = df["uf"].nunique()
    if n_uf != 27:
        print(f"  AVISO: {n_uf} UFs (esperado 27)", file=sys.stderr)
    total = int(df["n_veiculos"].sum())
    print(f"  {n_uf} UFs | total {total:,} veiculos")

    # Reconciliacao com o outro arquivo do SENATRAN, se houver um do MESMO
    # periodo. Comparar meses diferentes produz divergencia falsa.
    ano = int(df["ano_ref"].iloc[0])
    mes = df["mes_ref"].iloc[0]
    sufixo = f"_{ano}" + (f"_{int(mes):02d}" if pd.notna(mes) else "")
    outro = sorted(SAIDA.glob(f"senatran_frota{sufixo}.parquet"))
    if outro:
        d2 = pd.read_parquet(outro[-1])
        t2 = int(d2["frota_registrada"].sum())
        dif = abs(total - t2)
        marca = "ok" if dif / max(t2, 1) < 0.0001 else "DIVERGE"
        print(f"  'Frota por UF e Tipo' ({outro[-1].name}): {t2:,}  "
              f"[diferenca {dif:,} — {marca}]")
        if marca == "DIVERGE":
            print("  >>> os dois arquivos do SENATRAN deveriam bater depois de "
                  "descartadas as UFs nao identificadas. Confira o mes de "
                  "referencia dos dois.", file=sys.stderr)

    carga = df[(df["tipo"].isin(TIPOS_CARGA))
               & (df["especie"].isin(["CARGA", "TRACAO"]))]

    print(f"\n  DISTRIBUICAO DE EIXOS — especie CARGA/TRACAO")
    for tipo in ["CAMINHAO", "CAMINHAO TRATOR", "SEMI REBOQUE", "REBOQUE"]:
        sub = carga[carga["tipo"] == tipo]
        if sub.empty:
            continue
        total = int(sub["n_veiculos"].sum())
        conhecido = sub[sub["eixos"].notna()]
        n_conh = int(conhecido["n_veiculos"].sum())
        falta = (total - n_conh) / total * 100 if total else 0
        print(f"\n  {tipo}  total {total:,}  |  sem eixo informado: {falta:.1f}%")
        por_eixo = conhecido.groupby("eixos")["n_veiculos"].sum()
        for e, v in por_eixo.items():
            if v / max(n_conh, 1) >= 0.002:
                print(f"      {int(e)} eixos  {int(v):>10,}   "
                      f"{v / n_conh * 100:5.1f}% dos informados")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("arquivo", type=Path)
    p.add_argument("ano_ref", type=int, nargs="?", default=None)
    p.add_argument("--mes", type=int, default=None)
    p.add_argument("--inspecionar", action="store_true")
    a = p.parse_args()

    if not a.arquivo.exists():
        sys.exit(f"arquivo nao encontrado: {a.arquivo}")

    if a.inspecionar:
        inspeciona(a.arquivo)
        return
    if a.ano_ref is None:
        sys.exit("informe o ano de referencia")

    df = extrai(a.arquivo, a.ano_ref, a.mes)
    relata(df)

    SAIDA.mkdir(parents=True, exist_ok=True)
    sufixo = f"_{a.ano_ref}" + (f"_{a.mes:02d}" if a.mes else "")
    destino = SAIDA / f"senatran_eixos{sufixo}.parquet"
    df.to_parquet(destino, index=False)
    print(f"\n  {len(df)} linhas -> {destino}")


if __name__ == "__main__":
    main()
