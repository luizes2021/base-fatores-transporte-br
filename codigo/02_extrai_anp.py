"""
02_extrai_anp.py — camada 00_brutos -> 10_extraidos

Le as vendas de derivados da ANP e devolve formato longo:

    ano_ref | mes | uf | produto_anp | vendas_m3 | vendas_litros

Filtra apenas os produtos de oleo diesel. NAO aloca ao transporte de carga
e NAO separa fracao fossil de biogenica — isso e a etapa 30 (calibracao),
porque ambas sao decisoes de modelagem, nao de extracao.

DOIS LAYOUTS
A ANP distribui o mesmo dado em duas formas. O script detecta qual e:

  LARGO (o das series historicas por combustivel — o mais comum):
      COMBUSTIVEL | ANO | REGIAO | ESTADO | UNIDADE | JANEIRO ... DEZEMBRO | TOTAL
      Os meses sao COLUNAS. A coluna TOTAL e a soma do ano e e DESCARTADA:
      mante-la duplicaria todo o volume.

  LONGO (o de alguns paineis):
      ANO | MES | UNIDADE DA FEDERACAO | PRODUTO | VENDAS
      Uma linha por mes.

Outras armadilhas tratadas:
  - separador ';' e decimal ',' (padrao brasileiro)
  - encoding latin-1 / cp1252 (nao e utf-8)
  - nomes de coluna variam: PRODUTO x COMBUSTIVEL, ESTADO x UNIDADE DA FEDERACAO
  - 'UNIDADE' sozinha e a unidade de medida (m3), nao unidade da federacao
  - UF por extenso ("SANTA CATARINA"), nao sigla
  - mes como nome, numero ou data completa

Uso:
    python codigo/02_extrai_anp.py <arquivo.csv> [--ano 2024]
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

# A ANP usa abreviacoes de tres letras (JAN, FEV...) nos arquivos de dados e
# nomes por extenso nos de serie historica. Os dois entram.
MESES = {
    "JANEIRO": 1, "FEVEREIRO": 2, "MARCO": 3, "ABRIL": 4, "MAIO": 5,
    "JUNHO": 6, "JULHO": 7, "AGOSTO": 8, "SETEMBRO": 9, "OUTUBRO": 10,
    "NOVEMBRO": 11, "DEZEMBRO": 12,
    "JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12,
}

# So os meses por extenso viram COLUNAS no layout largo. As abreviacoes
# aparecem como valores de uma coluna MES, no layout longo.
MESES_EXTENSO = {k: v for k, v in MESES.items() if len(k) > 3}

ALIAS = {
    "ANO": "ano_ref",
    "MES": "mes",
    # 'UNIDADE' sozinha NAO entra: na ANP e a unidade de medida (m3).
    "UNIDADE DA FEDERACAO": "uf_bruto", "UNIDADES DA FEDERACAO": "uf_bruto",
    "ESTADO": "uf_bruto", "UF": "uf_bruto",
    "PRODUTO": "produto_anp", "COMBUSTIVEL": "produto_anp",
    "DERIVADO": "produto_anp", "TIPO": "produto_anp",
    "VENDAS": "vendas_m3", "VENDAS M3": "vendas_m3",
    "VENDAS DE DERIVADOS COMBUSTIVEIS M3": "vendas_m3",
    "VOLUME": "vendas_m3", "VOLUME M3": "vendas_m3",
    "SEGMENTO": "segmento",
}


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


def detecta_encoding(caminho: Path) -> str:
    """UTF-8 (com ou sem BOM) primeiro; latin-1 so como ultimo recurso.

    IMPORTANTE: latin-1 NUNCA falha — decodifica qualquer byte. Se for tentado
    primeiro, um arquivo UTF-8 e lido com acentos corrompidos e o script segue
    em frente com colunas erradas. Os arquivos da ANP sao UTF-8 com BOM, e o
    BOM vira 'ï»¿ANO' em latin-1, quebrando o reconhecimento da coluna ANO.
    """
    with open(caminho, "rb") as f:
        inicio = f.read(1 << 16)

    if inicio.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        inicio.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    return "latin-1"


def le_tabela(caminho: Path) -> pd.DataFrame:
    """Le csv ou xlsx, detectando encoding e separador."""
    if caminho.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(caminho, dtype=object)
        print("  lido como planilha")
        return df

    enc = detecta_encoding(caminho)
    ultimo = None
    for sep in (";", ",", "\t"):
        try:
            df = pd.read_csv(caminho, sep=sep, encoding=enc, dtype=str)
            if df.shape[1] >= 3:
                print(f"  lido com encoding={enc} sep='{sep}'")
                return df
        except Exception as e:  # noqa: BLE001
            ultimo = e
    raise ValueError(f"nao foi possivel ler o arquivo da ANP: {ultimo}")


def para_numero(serie: pd.Series) -> pd.Series:
    """Converte '1.234.567,89' -> 1234567.89. Aceita ja-numerico."""
    if pd.api.types.is_numeric_dtype(serie):
        return serie.astype(float)
    s = serie.astype(str).str.strip()
    s = s.str.replace(r"[^\d,.\-]", "", regex=True)
    s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


def resolve_mes(serie: pd.Series) -> pd.Series:
    bruto = serie.map(normaliza)
    como_nome = bruto.map(MESES)
    if como_nome.notna().all():
        return como_nome.astype("int64")
    como_data = pd.to_datetime(serie, errors="coerce", dayfirst=True)
    if como_data.notna().any():
        return como_data.dt.month.fillna(como_nome).astype("Int64")
    return pd.to_numeric(bruto, errors="coerce").astype("Int64")


def de_largo_para_longo(df: pd.DataFrame) -> pd.DataFrame:
    """Meses em colunas -> uma linha por mes. Descarta a coluna TOTAL."""
    cols_mes = [c for c in df.columns if c in MESES_EXTENSO]
    print(f"  layout LARGO: {len(cols_mes)} colunas de mes detectadas")

    if "TOTAL" in df.columns:
        df = df.drop(columns=["TOTAL"])
        print("  coluna TOTAL descartada (e a soma do ano — duplicaria o volume)")

    if "UNIDADE" in df.columns:
        unidades = {normaliza(u) for u in df["UNIDADE"].dropna().unique()}
        if unidades and not any("M3" in u for u in unidades):
            print(f"  AVISO: unidade de medida inesperada: {unidades}. O script "
                  "assume m3.", file=sys.stderr)
        df = df.drop(columns=["UNIDADE"])

    id_vars = [c for c in df.columns if c not in cols_mes]
    longo = df.melt(id_vars=id_vars, value_vars=cols_mes,
                    var_name="mes_nome", value_name="vendas_m3")
    longo["mes"] = longo["mes_nome"].map(MESES).astype("Int64")
    return longo.drop(columns=["mes_nome"])


def inspeciona(caminho: Path) -> None:
    """Imprime as colunas reais e valores de exemplo, sem extrair nada.

    A ANP publica varios arquivos diferentes na mesma pagina, com colunas
    diferentes. Rode isto antes de confiar no mapeamento automatico.
    """
    df = le_tabela(caminho)
    brutas = list(df.columns)
    df.columns = [normaliza(c) for c in df.columns]
    print(f"  {len(df):,} linhas x {len(df.columns)} colunas\n")

    print(f"{'COLUNA NO ARQUIVO':<34} {'NORMALIZADA':<28} "
          f"{'EXEMPLOS':<34} PAPEL")
    print("-" * 118)
    for bruta, norm in zip(brutas, df.columns):
        distintos = df[norm].dropna().unique()[:3]
        exemplo = " | ".join(str(v)[:14] for v in distintos)
        papel = ALIAS.get(norm, "mes" if norm in MESES_EXTENSO else "")
        print(f"{str(bruta)[:33]:<34} {norm[:27]:<28} {exemplo[:33]:<34} {papel}")

    n_meses = sum(1 for c in df.columns if c in MESES_EXTENSO)
    print(f"\n  layout: {'LARGO' if n_meses >= 6 else 'LONGO'}"
          f" ({n_meses} colunas de mes)")

    for alvo, rotulo in (("produto_anp", "produtos"), ("segmento", "segmentos")):
        col = next((c for c in df.columns if ALIAS.get(c) == alvo), None)
        if col:
            vals = sorted({normaliza(v) for v in df[col].dropna().unique()})
            print(f"  {rotulo}: {vals[:12]}")


def extrai(caminho: Path, ano_filtro=None, unidade="m3") -> pd.DataFrame:
    df = le_tabela(caminho)
    df.columns = [normaliza(c) for c in df.columns]
    df = df.rename(columns={c: ALIAS[c] for c in df.columns if c in ALIAS})

    # LARGO quando ha pelo menos metade dos meses como colunas
    if sum(1 for c in df.columns if c in MESES_EXTENSO) >= 6:
        df = de_largo_para_longo(df)
    else:
        print("  layout LONGO")
        if "vendas_m3" not in df.columns:
            raise ValueError(
                "nao achei a coluna de vendas nem colunas de mes. "
                f"Colunas vistas: {sorted(df.columns)[:25]}"
            )
        df["mes"] = resolve_mes(df["mes"]) if "mes" in df.columns else pd.NA

    faltando = {"uf_bruto", "produto_anp"} - set(df.columns)
    if faltando:
        raise ValueError(
            f"colunas ausentes: {sorted(faltando)}. Vistas: {sorted(df.columns)[:25]}"
        )

    uf_norm = df["uf_bruto"].map(normaliza)
    df["uf"] = uf_norm.map(UF_POR_NOME).fillna(uf_norm.where(uf_norm.isin(SIGLAS)))
    desconhecidas = sorted(set(uf_norm[df["uf"].isna()]))
    if desconhecidas:
        print(f"  aviso: UF nao reconhecida, descartada: {desconhecidas[:5]}",
              file=sys.stderr)
    df = df[df["uf"].notna()].copy()

    prod = df["produto_anp"].map(normaliza)
    df = df[prod.str.contains("DIESEL", na=False)].copy()
    if df.empty:
        raise ValueError(
            "nenhum produto diesel encontrado. A ANP publica um arquivo por "
            "combustivel — confira se baixou o de oleo diesel."
        )
    df["produto_anp"] = prod[df.index]

    bruto = para_numero(df["vendas_m3"])
    df = df[bruto.notna()].copy()
    bruto = bruto[bruto.notna()]

    # ATENCAO: nem todo arquivo da ANP vem em m3. Os de vendas ANUAIS POR
    # MUNICIPIO vem em LITROS (e asfalto/GLP/oleo combustivel em kg). Tratar
    # litro como m3 multiplica o volume por mil — e 1000x ainda "parece" um
    # numero, entao o erro passa despercebido.
    if unidade == "litros":
        df["vendas_litros"] = bruto
        df["vendas_m3"] = bruto / 1000.0
        print("  unidade de origem: LITROS")
    else:
        df["vendas_m3"] = bruto
        df["vendas_litros"] = bruto * 1000.0

    if "ano_ref" in df.columns:
        df["ano_ref"] = pd.to_numeric(df["ano_ref"], errors="coerce").astype("Int64")
    elif ano_filtro:
        df["ano_ref"] = int(ano_filtro)
    else:
        raise ValueError("sem coluna de ano no arquivo — informe --ano")

    if ano_filtro:
        df = df[df["ano_ref"] == int(ano_filtro)]
        if df.empty:
            raise ValueError(f"nenhuma linha para o ano {ano_filtro}")

    # SEGMENTO (posto revendedor / TRR / consumidor final) e canal de venda,
    # nao setor de consumo. Preservado porque limita a alocacao ao rodoviario
    # na etapa 30 — ver docs/01_guia_download.md.
    if "segmento" in df.columns:
        df["segmento"] = df["segmento"].map(normaliza)
        print(f"  dimensao SEGMENTO preservada: "
              f"{sorted(df['segmento'].unique())}")
    else:
        df["segmento"] = "NAO INFORMADO"

    df["id_fonte"] = "anp_vendas_diesel"
    df["sha256_origem"] = sha256(caminho)

    cols = ["ano_ref", "mes", "uf", "produto_anp", "segmento", "vendas_m3",
            "vendas_litros", "id_fonte", "sha256_origem"]
    return df[cols].sort_values(["ano_ref", "mes", "uf"], ignore_index=True)


def valida(df: pd.DataFrame) -> None:
    assert (df["vendas_m3"] >= 0).all(), "vendas negativas"

    n_uf = df["uf"].nunique()
    if n_uf != 27:
        print(f"  AVISO: {n_uf} UFs (esperado 27)", file=sys.stderr)

    for ano, g in df.groupby("ano_ref"):
        meses = g["mes"].dropna().nunique()
        if meses and meses != 12:
            print(f"  AVISO: {ano} tem {meses} meses — ano incompleto",
                  file=sys.stderr)
        total_bi_l = g["vendas_litros"].sum() / 1e9
        print(f"  {ano}: {total_bi_l:.1f} bilhoes de litros de diesel")
        # Ordem de grandeza nacional historica: ~50-70 bi L/ano.
        if not 30 <= total_bi_l <= 100:
            print("  AVISO: total fora da ordem de grandeza nacional esperada.",
                  file=sys.stderr)
            if total_bi_l > 1000:
                print("  >>> esta ~1000x alto: o arquivo provavelmente ja esta "
                      "em LITROS. Repita com --unidade litros (e o caso dos "
                      "arquivos de vendas anuais por municipio).",
                      file=sys.stderr)
            elif meses and meses < 12:
                print("  >>> ano incompleto, veja o aviso acima.", file=sys.stderr)
            else:
                print("  >>> confira se o arquivo e de uma UF so, ou se a "
                      "coluna TOTAL entrou junto.", file=sys.stderr)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("arquivo", type=Path)
    p.add_argument("--ano", type=int, default=None)
    p.add_argument("--inspecionar", action="store_true",
                   help="imprime colunas e valores de exemplo, sem extrair")
    p.add_argument("--unidade", choices=["m3", "litros"], default="m3",
                   help="unidade da coluna de vendas no arquivo de origem; "
                        "os arquivos ANUAIS POR MUNICIPIO vem em litros")
    a = p.parse_args()

    if not a.arquivo.exists():
        sys.exit(f"arquivo nao encontrado: {a.arquivo}")

    if a.inspecionar:
        inspeciona(a.arquivo)
        return

    df = extrai(a.arquivo, a.ano, a.unidade)
    valida(df)

    SAIDA.mkdir(parents=True, exist_ok=True)
    # O nome do destino carrega o arquivo de origem: a ANP publica varios
    # conjuntos de diesel na mesma pagina (por tipo, por segmento, por
    # municipio) e eles NAO podem se sobrescrever — cada um e uma visao
    # diferente do mesmo volume.
    origem = a.arquivo.stem.lower()
    if "segmento" in origem:
        visao = "segmento"
    elif "tipo" in origem:
        visao = "tipo"
    elif "municipio" in origem:
        visao = "municipio"
    elif "produtor" in origem:
        visao = "produtor"
    else:
        visao = "geral"

    sufixo = f"_{a.ano}" if a.ano else ""
    destino = SAIDA / f"anp_vendas_diesel_{visao}{sufixo}.parquet"
    df.to_parquet(destino, index=False)

    print(f"  {len(df)} linhas -> {destino}")
    print(df.groupby("produto_anp")["vendas_m3"].sum().sort_values(
        ascending=False).to_string())


if __name__ == "__main__":
    main()
