"""
01_extrai_senatran.py — camada 00_brutos -> 10_extraidos

Le "Frota por UF e Tipo de Veiculo" (SENATRAN) e devolve formato longo:

    ano_ref | mes_ref | uf | tipo_senatran | frota_registrada

NAO faz mapeamento para classe canonica. Isso e a etapa 20.

O QUE O ARQUIVO REAL TEM (verificado em Dez/2023)
  - duas linhas de titulo antes do cabecalho
  - o cabecalho da primeira coluna e "Grandes Regioes e\\nUnidades da
    Federacao" — com quebra de linha dentro da celula
  - as UFs vem POR EXTENSO e ACENTUADAS ("Para ", "Rondonia ", "Sao Paulo "),
    com espacos sobrando, e NUNCA por sigla
  - linhas de AGREGADO ("Brasil", "Norte", "Nordeste"...) se misturam as de
    UF. Soma-las as UFs duplicaria a frota inteira.
  - ha uma coluna TOTAL, que e a soma da linha
  - ha uma SEGUNDA TABELA abaixo da primeira ("Tabela 2 - Percentagem..."),
    cuja linha "Brasil %" traz PERCENTUAIS, nao contagens

Todas essas armadilhas tem o mesmo efeito se ignoradas: numero errado sem
mensagem de erro. O script trata cada uma e confere no fim que sobraram
exatamente 27 UFs.

EXTRAI TODOS OS TIPOS, nao so os de carga. Onibus e microonibus consomem
diesel no posto revendedor e importam para interpretar a alocacao (o 'alfa'
da etapa 30). Filtrar e decisao de modelagem, nao de extracao.

FORMATO: a maioria dos meses vem em .xls (formato antigo do Excel). Ler .xls
exige a biblioteca xlrd — openpyxl NAO le esse formato.

Uso:
    python codigo/01_extrai_senatran.py <arquivo.xls> <ano_ref> [--aba NOME]
    python codigo/01_extrai_senatran.py <arquivo.xls> 2023 --mes 12
"""

import argparse
import hashlib
import sys
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "dados" / "10_extraidos"

# As UFs vem por extenso. Chaves ja normalizadas (maiuscula, sem acento).
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

# Linhas que NAO sao UF e precisam sair. Nao basta confiar no mapeamento:
# listar explicitamente deixa o descarte auditavel.
AGREGADOS = {
    "BRASIL", "BRASIL %", "NORTE", "NORDESTE", "SUDESTE", "SUL",
    "CENTRO OESTE", "CENTROOESTE", "TOTAL",
}

# Colunas que nao sao tipo de veiculo.
NAO_TIPO = {"TOTAL"}

# Tipos ligados ao transporte de carga. Usado so no diagnostico impresso;
# a extracao guarda todos os tipos.
TIPOS_CARGA = {"CAMINHAO", "CAMINHAO TRATOR", "REBOQUE", "SEMI REBOQUE",
               "UTILITARIO"}


def normaliza(texto) -> str:
    """Maiuscula, sem acento, sem pontuacao, espaco simples.

    Trata tambem a quebra de linha dentro da celula do cabecalho.
    """
    if pd.isna(texto):
        return ""
    s = unicodedata.normalize("NFKD", str(texto))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.upper().replace("-", " ").replace(".", " ").replace("_", " ")
    s = "".join(c if (c.isalnum() or c.isspace()) else " " for c in s)
    return " ".join(s.split())


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def le_excel(caminho: Path, aba, **kwargs) -> pd.DataFrame:
    """read_excel com mensagem util quando falta o motor do formato."""
    try:
        return pd.read_excel(caminho, sheet_name=aba, **kwargs)
    except ImportError as e:
        ext = caminho.suffix.lower()
        motor = "xlrd" if ext == ".xls" else "openpyxl"
        sys.exit(
            f"nao consigo abrir {ext}: falta a biblioteca '{motor}'.\n"
            f"  pip install {motor}\n"
            f"(o SENATRAN publica a maioria dos meses em .xls, que o openpyxl "
            f"nao le)\n  erro original: {e}"
        )
    except ValueError as e:
        if "Worksheet" in str(e) or "sheet" in str(e).lower():
            abas = pd.ExcelFile(caminho).sheet_names
            sys.exit(f"aba '{aba}' nao existe. Abas disponiveis: {abas}")
        raise


def e_coluna_uf(celula: str) -> bool:
    """A coluna das UFs tem nome variavel entre meses.

    CUIDADO: o TITULO da planilha ("Frota de veiculos, por tipo e com placa,
    segundo as Grandes Regioes e Unidades da Federacao - DEZ/2023") tambem
    contem 'Unidades da Federacao'. Por isso o limite de tamanho: o rotulo da
    coluna e curto, o titulo e uma frase.
    """
    n = normaliza(celula)
    if n in {"UF", "UNIDADE DA FEDERACAO", "UNIDADES DA FEDERACAO"}:
        return True
    if len(n) > 60:
        return False
    return "FEDERACAO" in n and "UNIDADE" in n


def acha_cabecalho(bruto: pd.DataFrame, limite: int = 20) -> int:
    """A linha de cabecalho tem a coluna de UF E varias colunas preenchidas.

    A linha de titulo tem uma celula so; a de cabecalho tem uma por tipo de
    veiculo. Exigir as duas coisas separa as duas.
    """
    for i in range(min(limite, len(bruto))):
        linha = bruto.iloc[i].tolist()
        preenchidas = sum(1 for c in linha if normaliza(c))
        if preenchidas >= 3 and any(e_coluna_uf(c) for c in linha):
            return i
    amostra = [normaliza(c) for c in bruto.iloc[:5].values.ravel() if normaliza(c)]
    raise ValueError(
        f"cabecalho nao encontrado nas primeiras {limite} linhas. "
        f"Procuro uma celula com 'Unidades da Federacao' ou 'UF'. "
        f"Primeiras celulas vistas: {amostra[:12]}"
    )


def inspeciona(caminho: Path, aba) -> None:
    bruto = le_excel(caminho, aba, header=None, dtype=object)
    print(f"  dimensao: {bruto.shape[0]} linhas x {bruto.shape[1]} colunas\n")
    print("PRIMEIRAS 8 LINHAS, 6 PRIMEIRAS COLUNAS:")
    print(bruto.iloc[:8, :6].to_string())

    try:
        linha = acha_cabecalho(bruto)
        print(f"\n  cabecalho detectado na linha {linha}")
        cols = [normaliza(c) for c in bruto.iloc[linha] if normaliza(c)]
        print(f"  colunas: {cols}")
    except ValueError as e:
        print(f"\n  {e}", file=sys.stderr)
        return

    rotulos = [normaliza(v) for v in bruto.iloc[linha + 1:, 0]]
    ufs = [r for r in rotulos if r in UF_POR_NOME]
    outros = [r for r in rotulos if r and r not in UF_POR_NOME]
    print(f"\n  linhas de UF: {len(ufs)}")
    print(f"  linhas descartadas ({len(outros)}): {outros[:12]}")


def extrai(caminho: Path, ano_ref: int, mes_ref=None, aba=0) -> pd.DataFrame:
    bruto = le_excel(caminho, aba, header=None, dtype=object)
    linha = acha_cabecalho(bruto)
    print(f"  cabecalho na linha {linha}")

    cabecalho = [normaliza(c) for c in bruto.iloc[linha]]
    dados = bruto.iloc[linha + 1:].copy()
    dados.columns = cabecalho

    col_uf = cabecalho[0]
    dados = dados.rename(columns={col_uf: "__rotulo"})
    dados["__rotulo"] = dados["__rotulo"].map(normaliza)

    # --- separar UF de agregado, em vez de confiar so no mapeamento ---
    dados["uf"] = dados["__rotulo"].map(UF_POR_NOME)
    dados.loc[dados["__rotulo"].isin(SIGLAS), "uf"] = dados["__rotulo"]

    descartadas = sorted({r for r in dados.loc[dados["uf"].isna(), "__rotulo"] if r})
    # Rotulos longos sao prosa (titulo da segunda tabela, linha de fonte),
    # nao nome de UF. Nenhuma UF brasileira passa de 30 caracteres.
    inesperadas = [r for r in descartadas
                   if r not in AGREGADOS and len(r) <= 40]
    print(f"  linhas descartadas: {len(descartadas)} "
          f"(agregados, titulos e a segunda tabela)")
    if inesperadas:
        print(f"  AVISO: rotulos descartados que nao reconheco como agregado: "
              f"{inesperadas[:8]}", file=sys.stderr)
        print("  >>> confira se nao e uma UF escrita de forma diferente.",
              file=sys.stderr)

    dados = dados[dados["uf"].notna()].copy()
    if dados.empty:
        raise ValueError(
            "nenhuma UF reconhecida. As UFs vem por extenso neste arquivo "
            "('Sao Paulo', nao 'SP') — confira a primeira coluna."
        )

    # --- colunas de tipo: tudo menos TOTAL e colunas sem nome ---
    cols_tipo = [c for c in dados.columns
                 if c and c not in NAO_TIPO and c not in {"__rotulo", "uf"}]
    if "TOTAL" in dados.columns:
        print("  coluna TOTAL descartada (e a soma da linha)")

    longo = dados.melt(id_vars="uf", value_vars=cols_tipo,
                       var_name="tipo_senatran", value_name="frota_registrada")
    longo["frota_registrada"] = pd.to_numeric(
        longo["frota_registrada"], errors="coerce")

    perdidas = int(longo["frota_registrada"].isna().sum())
    if perdidas:
        print(f"  {perdidas} celula(s) nao numericas viraram zero")
    longo["frota_registrada"] = longo["frota_registrada"].fillna(0).astype("int64")

    longo["ano_ref"] = int(ano_ref)
    longo["mes_ref"] = int(mes_ref) if mes_ref else pd.NA
    longo["id_fonte"] = "senatran_frota_tipo"
    longo["sha256_origem"] = sha256(caminho)

    cols = ["ano_ref", "mes_ref", "uf", "tipo_senatran", "frota_registrada",
            "id_fonte", "sha256_origem"]
    return longo[cols].sort_values(["uf", "tipo_senatran"], ignore_index=True)


def valida(df: pd.DataFrame, bruto_total=None) -> None:
    n_uf = df["uf"].nunique()
    if n_uf != 27:
        faltando = SIGLAS - set(df["uf"])
        raise AssertionError(
            f"esperava 27 UFs, vieram {n_uf}. Faltando: {sorted(faltando)}"
        )
    print(f"  27 UFs, {df['tipo_senatran'].nunique()} tipos de veiculo")
    assert (df["frota_registrada"] >= 0).all(), "frota negativa"

    total = int(df["frota_registrada"].sum())
    print(f"  frota total somada: {total:,}")
    if bruto_total:
        dif = abs(total - bruto_total) / bruto_total
        marca = "ok" if dif < 0.001 else "DIVERGE"
        print(f"  linha 'Brasil' do arquivo: {bruto_total:,}  [{marca}]")
        if dif >= 0.001:
            print("  >>> a soma das UFs deveria bater com a linha Brasil. "
                  "Alguma linha de agregado pode ter entrado, ou uma UF "
                  "ficou de fora.", file=sys.stderr)

    carga = df[df["tipo_senatran"].isin(TIPOS_CARGA)]
    print("\n  tipos ligados a carga:")
    print(carga.groupby("tipo_senatran")["frota_registrada"].sum()
          .sort_values(ascending=False).to_string())

    tratores = int(df.loc[df.tipo_senatran == "CAMINHAO TRATOR",
                          "frota_registrada"].sum())
    semis = int(df.loc[df.tipo_senatran == "SEMI REBOQUE",
                       "frota_registrada"].sum())
    if tratores and semis:
        razao = semis / tratores
        print(f"\n  razao semirreboques/cavalos = {razao:.2f}")
        if not 0.8 <= razao <= 3.0:
            print("  AVISO: razao fora da faixa plausivel — revisar antes de "
                  "acoplar.", file=sys.stderr)


def total_brasil(caminho: Path, aba) -> int | None:
    """Le a linha 'Brasil' do arquivo, para conferir a soma das UFs."""
    bruto = le_excel(caminho, aba, header=None, dtype=object)
    try:
        linha = acha_cabecalho(bruto)
    except ValueError:
        return None
    for i in range(linha + 1, min(linha + 5, len(bruto))):
        if normaliza(bruto.iloc[i, 0]) == "BRASIL":
            v = pd.to_numeric(bruto.iloc[i, 1], errors="coerce")
            return int(v) if pd.notna(v) else None
    return None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("arquivo", type=Path)
    p.add_argument("ano_ref", type=int, nargs="?", default=None)
    p.add_argument("--mes", type=int, default=None,
                   help="mes de referencia (o SENATRAN publica mensalmente)")
    p.add_argument("--aba", default=0)
    p.add_argument("--inspecionar", action="store_true",
                   help="imprime a estrutura do arquivo, sem extrair")
    a = p.parse_args()

    if not a.arquivo.exists():
        sys.exit(f"arquivo nao encontrado: {a.arquivo}")

    aba = int(a.aba) if str(a.aba).isdigit() else a.aba

    if a.inspecionar:
        inspeciona(a.arquivo, aba)
        return

    if a.ano_ref is None:
        sys.exit("informe o ano de referencia")

    df = extrai(a.arquivo, a.ano_ref, a.mes, aba)
    valida(df, total_brasil(a.arquivo, aba))

    SAIDA.mkdir(parents=True, exist_ok=True)
    sufixo = f"_{a.ano_ref}" + (f"_{a.mes:02d}" if a.mes else "")
    destino = SAIDA / f"senatran_frota{sufixo}.parquet"
    df.to_parquet(destino, index=False)
    print(f"\n  {len(df)} linhas -> {destino}")


if __name__ == "__main__":
    main()
