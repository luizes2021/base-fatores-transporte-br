"""
05_extrai_ineavar.py — camada 00_brutos -> 10_extraidos

Le os CSV do INEAVAR (Inventario Nacional de Emissoes Atmosfericas por
Veiculos Automotores Rodoviarios, MMA) e devolve, por categoria:

    ano_ref | categoria | motor | combustivel | fase | idade |
    frota | km_ano | litros_ano | l_por_km | ...

POR QUE ESTA FONTE MUDA O PROJETO
Ate aqui faltavam km/ano e L/km, e nao havia fonte publica facil. O INEAVAR
publica os dois, nacionais, em CSV, com a fracao fossil/biogenica ja separada:

    km_ajustado                     quilometragem anual, ajustada pelo consumo
    L_ajustado                      consumo anual de combustivel
    combustivel_fracao_fossil       litros fosseis
    combustivel_fracao_renovavel    litros biogenicos (o biodiesel)
    gCH4/km, gN2O/km                fatores de emissao
    gco2_fossil, gco2_renovavel     emissoes separadas por origem
    Frota                           frota CIRCULANTE, nao registrada

'Ajustado' quer dizer calibrado contra o consumo observado de combustivel —
a mesma reconciliacao top-down que esta base faria contra a ANP. Usar o valor
ajustado e herdar essa calibracao; o preliminar e o que vem antes dela.

O QUE O INEAVAR NAO RESOLVE
A categoria dele e de EMISSOES (leves, semipesados, pesados), nao de
LOGISTICA (toco, truck, bitruck, carreta, bitrem, rodotrem). E ele publica
g/km, nao g/tkm: fator de carga e percurso vazio continuam ausentes. Esses
dois pontos sao o que esta base acrescenta — ver crosswalk/ineavar_para_canonica.csv.

ATENCAO AO 'Idade'
O arquivo e desagregado por ano-modelo e idade. Somar sem agrupar mistura
coortes. O script agrega explicitamente e informa o que agregou.

Uso:
    python codigo/05_extrai_ineavar.py <arquivo.csv> --inspecionar
    python codigo/05_extrai_ineavar.py <arquivo.csv> --ano 2024
"""

import argparse
import hashlib
import sys
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "dados" / "10_extraidos"

# Nomes como o dicionario do INEAVAR os publica, ja normalizados.
PAPEIS = {
    "categoria": ("CATEGORIA",),
    "categoria_sucat": ("CATEGORIASUCAT", "CATEGORIA SUCAT"),
    "motor": ("MOTOR",),
    "combustivel": ("COMBUSTIVEL",),
    "fase": ("FASE",),
    "ano_modelo": ("ANOMODELO", "ANO MODELO"),
    "ano_ref": ("ANOCALENDARIO", "ANO CALENDARIO"),
    "idade": ("IDADE",),
    "frota": ("FROTA",),
    "km_ajustado": ("KM AJUSTADO", "KMAJUSTADO"),
    "km_preliminar": ("KM PRELIMINAR", "KMPRELIMINAR"),
    "litros_ajustado": ("L AJUSTADO", "LAJUSTADO"),
    "litros_preliminar": ("L PRELIMINAR", "LPRELIMINAR"),
    "litros_fossil": ("COMBUSTIVEL FRACAO FOSSIL",),
    "litros_renovavel": ("COMBUSTIVEL FRACAO RENOVAVEL",),
    "gco2_fossil": ("GCO2 FOSSIL",),
    "gco2_renovavel": ("GCO2 RENOVAVEL",),
    "gco2_total": ("GCO2 TOTAL",),
    "gco2e": ("GCO2 EQUIVALENTE",),
    "gch4_km": ("GCH4 KM",),
    "gn2o_km": ("GN2O KM",),
    "gch4": ("GCH4",),
    "gn2o": ("GN2O",),
}

# Sem estes dois nao da para calcular nada de intensidade.
MINIMO = {"categoria", "ano_ref"}

DIMENSOES = ["categoria", "categoria_sucat", "motor", "combustivel", "fase"]
SOMAVEIS = ["frota", "km_ajustado", "km_preliminar", "litros_ajustado",
            "litros_preliminar", "litros_fossil", "litros_renovavel",
            "gco2_fossil", "gco2_renovavel", "gco2_total", "gco2e",
            "gch4", "gn2o"]


def normaliza(texto) -> str:
    if pd.isna(texto):
        return ""
    s = unicodedata.normalize("NFKD", str(texto))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.upper().replace("-", " ").replace("/", " ").replace("_", " ")
    s = s.replace(".", " ")
    s = "".join(c if (c.isalnum() or c.isspace()) else " " for c in s)
    return " ".join(s.split())


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def detecta_encoding(caminho: Path) -> str:
    """UTF-8 antes de latin-1: latin-1 nunca falha e corrompe em silencio."""
    with open(caminho, "rb") as f:
        inicio = f.read(1 << 16)
    if inicio.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        inicio.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "latin-1"


def le_csv(caminho: Path, **kw) -> pd.DataFrame:
    enc = detecta_encoding(caminho)
    ultimo = None
    for sep in (";", ",", "\t"):
        try:
            df = pd.read_csv(caminho, sep=sep, encoding=enc, dtype=str, **kw)
            if df.shape[1] >= 3:
                if "nrows" not in kw:
                    print(f"  encoding={enc} sep='{sep}'")
                return df
        except Exception as e:  # noqa: BLE001
            ultimo = e
    raise ValueError(f"nao consegui ler o CSV: {ultimo}")


def para_numero(serie: pd.Series) -> pd.Series:
    """Aceita o formato BRASILEIRO e o AMERICANO.

    O INEAVAR usa o americano, com aspas e espacos: ' 94,553,724.47 ' — virgula
    de milhar, ponto decimal. Tratar isso como formato brasileiro (remover os
    pontos, virgula vira decimal) daria 94553724,47 -> 9455372447, ou seja
    cem vezes o valor. E um numero plausivel, entao o erro passaria.

    O formato e decidido para a COLUNA inteira, nao valor a valor. Decidir
    valor a valor erra em numeros sem parte decimal: em '26,714,473' o
    separador mais a direita e uma virgula, o que o faria parecer brasileiro.
    Um arquivo nao mistura os dois formatos, entao a coluna basta.
    """
    s = serie.astype(str).str.strip().str.replace(r"[^\d,.\-eE]", "",
                                                  regex=True)
    com_sep = s[s.str.contains(r"[.,]", na=False)]
    if com_sep.empty:
        return pd.to_numeric(s, errors="coerce")

    # Milhar americano: grupo de 3 digitos apos virgula, nao iniciado por zero
    # ('94,553' sim; '0,006' nao, que e decimal brasileiro).
    sinal_us = com_sep.str.contains(r"[1-9]\d{0,2},\d{3}(?:[.,]|$)",
                                    na=False).sum()
    # Decimal brasileiro: virgula seguida de 1-2 ou 4+ digitos no fim, ou
    # numero que comeca com '0,'.
    sinal_br = com_sep.str.contains(r",\d{1,2}$|,\d{4,}$|^-?0,\d+",
                                    na=False).sum()

    if sinal_us >= sinal_br:
        limpo = s.str.replace(",", "", regex=False)
    else:
        limpo = (s.str.replace(".", "", regex=False)
                 .str.replace(",", ".", regex=False))
    return pd.to_numeric(limpo, errors="coerce")


def mapeia(cols) -> dict:
    norm = {normaliza(c): c for c in cols}
    mapa = {p: norm[n] for p, nomes in PAPEIS.items()
            for n in nomes if n in norm}
    faltando = MINIMO - set(mapa)
    if faltando:
        raise ValueError(
            f"colunas essenciais ausentes: {sorted(faltando)}.\n"
            f"Vistas: {sorted(norm)[:30]}\n"
            "Este script espera um CSV do INEAVAR (frota_e_quilometragem.csv "
            "ou consumo_emissoes.csv)."
        )
    return mapa


def inspeciona(caminho: Path) -> None:
    d = le_csv(caminho, nrows=5000)
    print(f"  amostra: {len(d):,} linhas x {len(d.columns)} colunas\n")
    print(f"{'COLUNA NO ARQUIVO':<34} {'PAPEL':<20} EXEMPLOS")
    print("-" * 100)
    norm = {c: normaliza(c) for c in d.columns}
    inverso = {n: p for p, nomes in PAPEIS.items() for n in nomes}
    for col, n in norm.items():
        papel = inverso.get(n, "")
        ex = " | ".join(str(v)[:14] for v in d[col].dropna().unique()[:3])
        print(f"{str(col)[:33]:<34} {papel:<20} {ex[:44]}")

    mapa = mapeia(d.columns)
    print(f"\n  papeis reconhecidos: {sorted(mapa)}")
    if "categoria" in mapa:
        cats = sorted({normaliza(v) for v in d[mapa["categoria"]].dropna().unique()})
        print(f"\n  categorias na amostra ({len(cats)}):")
        for c in cats[:30]:
            print(f"    {c}")


def extrai(caminho: Path, ano_filtro=None) -> pd.DataFrame:
    d = le_csv(caminho)
    print(f"  {len(d):,} linhas lidas")
    mapa = mapeia(d.columns)
    d = d.rename(columns={v: k for k, v in mapa.items()})
    presentes = [p for p in mapa if p in d.columns]
    print(f"  papeis: {sorted(presentes)}")

    for c in SOMAVEIS:
        if c in d.columns:
            d[c] = para_numero(d[c])
    for c in ("ano_ref", "ano_modelo", "idade"):
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce").astype("Int64")
    for c in DIMENSOES:
        if c in d.columns:
            d[c] = d[c].map(normaliza)

    if ano_filtro:
        antes = len(d)
        d = d[d["ano_ref"] == int(ano_filtro)]
        print(f"  ano {ano_filtro}: {len(d):,} de {antes:,} linhas")
        if d.empty:
            anos = sorted(pd.read_csv.__self__ if False else
                          [int(a) for a in d["ano_ref"].dropna().unique()])
            raise ValueError(f"nenhuma linha para {ano_filtro}")

    # Agregar as coortes de ano-modelo/idade: somar sem agrupar as mistura.
    chaves = [c for c in ["ano_ref"] + DIMENSOES if c in d.columns]
    somaveis = [c for c in SOMAVEIS if c in d.columns]
    if "idade" in d.columns or "ano_modelo" in d.columns:
        print(f"  agregando coortes de ano-modelo/idade em: {chaves}")
    g = d.groupby(chaves, dropna=False)[somaveis].sum().reset_index()

    # Intensidades: so onde o denominador existe.
    km = g["km_ajustado"] if "km_ajustado" in g else g.get("km_preliminar")
    lt = g["litros_ajustado"] if "litros_ajustado" in g else g.get("litros_preliminar")
    if km is not None:
        g["km_ano"] = km
        if "frota" in g:
            g["km_por_veiculo_ano"] = (km / g["frota"].replace(0, pd.NA))
    if lt is not None:
        g["litros_ano"] = lt
        if km is not None:
            g["l_por_km"] = lt / km.replace(0, pd.NA)
    if {"litros_fossil", "litros_renovavel"} <= set(g.columns):
        tot = g["litros_fossil"] + g["litros_renovavel"]
        g["fracao_biogenica"] = g["litros_renovavel"] / tot.replace(0, pd.NA)

    g["id_fonte"] = "mma_ineavar"
    g["sha256_origem"] = sha256(caminho)
    return g


def relata(g: pd.DataFrame) -> None:
    if "l_por_km" in g.columns:
        print("\n  CONSUMO ESPECIFICO por categoria (L/km)")
        sub = g[g["l_por_km"].notna()].copy()
        if "combustivel" in sub.columns:
            sub = sub[sub["combustivel"].str.contains("DIESEL", na=False)]
        if not sub.empty:
            t = (sub.groupby("categoria")
                 .apply(lambda x: pd.Series({
                     "l_por_km": x["litros_ano"].sum() / x["km_ano"].sum(),
                     "km_ano_total": x["km_ano"].sum(),
                     "frota": x["frota"].sum() if "frota" in x else float("nan"),
                 }), include_groups=False)
                 .sort_values("km_ano_total", ascending=False))
            for cat, r in t.head(14).iterrows():
                kmv = (r["km_ano_total"] / r["frota"]) if r["frota"] else float("nan")
                print(f"    {cat[:34]:<36} {r['l_por_km']:.3f} L/km   "
                      f"{kmv:>9,.0f} km/ano/veic")
        else:
            print("    (nenhuma linha de diesel com km e litros)")

    if "fracao_biogenica" in g.columns:
        sub = g[g["fracao_biogenica"].notna()]
        # so o diesel: os outros combustiveis dao 0 ou 1 e poluem a faixa
        if "combustivel" in sub.columns:
            sub = sub[sub["combustivel"].str.contains("DIESEL", na=False)]
        if len(sub):
            print(f"\n  fracao biogenica do combustivel: "
                  f"{sub['fracao_biogenica'].min():.3f} a "
                  f"{sub['fracao_biogenica'].max():.3f}")
            print("    (e o biodiesel misturado; muda ano a ano com o mandato)")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("arquivo", type=Path)
    p.add_argument("--ano", type=int, default=None)
    p.add_argument("--inspecionar", action="store_true")
    a = p.parse_args()

    if not a.arquivo.exists():
        sys.exit(f"arquivo nao encontrado: {a.arquivo}")
    if a.inspecionar:
        inspeciona(a.arquivo)
        return

    g = extrai(a.arquivo, a.ano)
    relata(g)

    SAIDA.mkdir(parents=True, exist_ok=True)
    nome = "ineavar_" + ("consumo" if "gco2_total" in g.columns
                         or "litros_fossil" in g.columns else "frota_km")
    sufixo = f"_{a.ano}" if a.ano else ""
    destino = SAIDA / f"{nome}{sufixo}.parquet"
    g.to_parquet(destino, index=False)
    print(f"\n  {len(g)} linhas -> {destino}")


if __name__ == "__main__":
    main()
