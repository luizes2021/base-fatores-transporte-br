"""
21_acoplamento_eixos.py — camada 10_extraidos -> 20_harmonizados

Modelo de acoplamento v2: usa a CONTAGEM DE EIXOS para estimar quantos
conjuntos articulados existem por configuracao.

POR QUE SUBSTITUI O v1 (20_modelo_acoplamento.py)
O v1 tinha uma unica restricao — a razao semirreboques/cavalos — e cinco
incognitas. Era pouco: qualquer composicao plausivel passava.

O arquivo de eixos do SENATRAN separa os semirreboques por numero de eixos, e
isso vira uma restricao por tamanho de semi, nao uma so no agregado:

    semis de 2 eixos = (carreta5 + 2 x bitrem)   x (1 + s)
    semis de 3 eixos = (carreta6 + 2 x rodotrem) x (1 + s)
    cavalos de 3 eixos = carreta5 + carreta6 + bitrem + rodotrem

Tres equacoes, cinco incognitas (as quatro classes mais o excedente s). Ainda
indeterminado, mas o espaco viavel encolhe muito — e, melhor, o proprio dado
IMPOE UM TETO ao excedente de semirreboques:

    s <= (semis totais / cavalos de 3 eixos) - 1

Acima disso o numero de conjuntos ficaria negativo. No v1 essa faixa era
chutada (0,05 a 1,30); aqui ela sai do dado.

O QUE CONTINUA SENDO HIPOTESE
  - a contabilidade de eixos de cada configuracao (crosswalk/configuracoes_cvc.csv)
  - que os veiculos com eixos NAO INFORMADOS seguem a distribuicao dos
    informados — ~18% dos semirreboques e ~20% dos cavalos em Dez/2023.
    O script mostra o resultado COM e SEM essa imputacao.
  - que so cavalos de 3 eixos puxam CVC pesada. Os de 2 eixos (16% da frota)
    puxam semirreboques leves, fora das quatro classes modeladas.

Uso:
    python codigo/21_acoplamento_eixos.py --ano 2023
    python codigo/21_acoplamento_eixos.py --ano 2023 --mes 12 --n 500000
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "dados" / "10_extraidos"
SAIDA = RAIZ / "dados" / "20_harmonizados"
CONFIG = RAIZ / "crosswalk" / "configuracoes_cvc.csv"

ESPECIES_CARGA = ["CARGA", "TRACAO"]
EIXOS_CAVALO_CVC = 3   # so cavalos 6x2/6x4 puxam as CVC modeladas


def le_eixos(ano: int, mes=None) -> pd.DataFrame:
    padrao = f"senatran_eixos_{ano}" + (f"_{mes:02d}" if mes else "")
    achados = sorted(ENTRADA.glob(f"{padrao}*.parquet"))
    if not achados:
        sys.exit(
            f"nao achei {padrao}*.parquet em {ENTRADA}.\n"
            "Rode antes:  python codigo/04_extrai_senatran_eixos.py <arquivo> "
            f"{ano}"
        )
    print(f"  fonte: {achados[-1].name}")
    return pd.read_parquet(achados[-1])


def contagens(df: pd.DataFrame) -> dict:
    """Totais por tipo e eixo, com e sem imputacao dos nao informados."""
    c = df[df["especie"].isin(ESPECIES_CARGA)]
    out = {}

    for chave, tipo in (("cavalo", "CAMINHAO TRATOR"), ("semi", "SEMI REBOQUE")):
        sub = c[c["tipo"] == tipo]
        total = int(sub["n_veiculos"].sum())
        conhecido = sub[sub["eixos"].notna()]
        n_conh = int(conhecido["n_veiculos"].sum())
        por_eixo = (conhecido.groupby("eixos")["n_veiculos"].sum()
                    .astype(int).to_dict())
        out[chave] = {
            "total": total,
            "conhecido": n_conh,
            "frac_sem_info": (total - n_conh) / total if total else 0.0,
            "por_eixo": {int(k): v for k, v in por_eixo.items()},
        }
    return out


def entradas(cont: dict, imputar: bool):
    """Devolve (cavalos de 3 eixos, semis de 2, semis de 3).

    Com imputar=True, os nao informados sao redistribuidos na proporcao dos
    informados — hipotese explicita, nao dado.
    """
    def pega(bloco, eixos):
        v = bloco["por_eixo"].get(eixos, 0)
        if not imputar or bloco["conhecido"] == 0:
            return float(v)
        return float(v) * bloco["total"] / bloco["conhecido"]

    cav3 = pega(cont["cavalo"], EIXOS_CAVALO_CVC)
    s2 = pega(cont["semi"], 2)
    s3 = pega(cont["semi"], 3)
    return cav3, s2, s3


def amostra(cfg: pd.DataFrame, cav3, s2, s3, n, semente):
    """Resolve as restricoes em vez de sortear e torcer.

    Rejeicao pura aqui e quase inutil: duas igualdades simultaneas num espaco
    de cinco dimensoes sao acertadas por acaso em ~0,03% dos sorteios. Mas o
    sistema tem solucao fechada dado s.

    Com A = semis2/(1+s), B = semis3/(1+s) e T = cavalos de 3 eixos:

        C5 = A - 2.BT          (semis de 2 eixos: carreta5 leva 1, bitrem 2)
        C6 = B - 2.RT          (semis de 3 eixos: carreta6 leva 1, rodotrem 2)
        C5 + C6 + BT + RT = T

    Somando, BT + RT = A + B - T. Ou seja: FIXADO s, o total de conjuntos
    pesados (bitrem + rodotrem) fica DETERMINADO — so a divisao entre os dois
    permanece livre. Sao dois graus de liberdade no fim: s e essa divisao.

    Entao sorteamos s e a divisao, e resolvemos o resto. Toda amostra e viavel
    por construcao, e o conjunto viavel fica exatamente caracterizado em vez
    de aproximado.
    """
    rng = np.random.default_rng(semente)
    ordem = list(cfg["id_classe"])
    iC5, iC6 = ordem.index("CARRETA5"), ordem.index("CARRETA6")
    iBT, iRT = ordem.index("BITREM"), ordem.index("RODOTREM")

    s_max = (s2 + s3) / cav3 - 1.0
    if s_max <= 0:
        return np.empty((0, 4)), np.empty(0), s_max, {"viavel": 0}

    s = rng.uniform(0.0, s_max, size=n)
    A = s2 / (1.0 + s)
    B = s3 / (1.0 + s)
    Y = A + B - cav3                      # bitrem + rodotrem, determinado

    # BT limitado por: nao usar mais semis de 2 eixos do que existem (BT<=A/2)
    # e deixar RT=Y-BT dentro do que os semis de 3 eixos permitem (RT<=B/2)
    bt_lo = np.maximum(0.0, Y - B / 2.0)
    bt_hi = np.minimum(Y, A / 2.0)
    viavel = (Y >= 0) & (bt_hi >= bt_lo)

    bt = bt_lo + rng.uniform(size=n) * np.maximum(bt_hi - bt_lo, 0.0)
    rt = Y - bt
    c5 = A - 2.0 * bt
    c6 = B - 2.0 * rt

    conj = np.empty((n, 4))
    conj[:, iC5], conj[:, iC6] = c5, c6
    conj[:, iBT], conj[:, iRT] = bt, rt

    ok = viavel & (conj >= 0).all(axis=1)
    conj, s = conj[ok], s[ok]
    if not len(conj):
        return conj, s, s_max, {"viavel": 0}

    p = conj / conj.sum(axis=1, keepdims=True)
    return p, s, s_max, {"viavel": int(ok.sum())}


def filtra_priors(p, s, cfg):
    """Aplica as faixas de participacao ao conjunto viavel."""
    lo = cfg["share_min"].to_numpy()
    hi = cfg["share_max"].to_numpy()
    dentro = ((p >= lo) & (p <= hi)).all(axis=1)
    return p[dentro], s[dentro]


def resumo(v: np.ndarray) -> dict:
    return {"p05": float(np.percentile(v, 5)),
            "p50": float(np.percentile(v, 50)),
            "p95": float(np.percentile(v, 95))}


def publica(p, s, cav3, cfg, ano, mes, fonte, cenario, s_max):
    linhas = []
    print(f"\n  {'classe':<30} {'p05':>11} {'p50':>11} {'p95':>11}")
    for i, cl in cfg.reset_index(drop=True).iterrows():
        q = resumo(p[:, i] * cav3)
        print(f"  {cl['classe_nome']:<30} {q['p05']:>11,.0f} "
              f"{q['p50']:>11,.0f} {q['p95']:>11,.0f}")
        linhas.append({
            "ano_ref": ano, "mes_ref": mes, "uf": "BR",
            "id_classe": cl["id_classe"], "variavel": "n_conjuntos",
            "unidade": "conjuntos", "fonte": fonte, "cenario": cenario,
            "metodo": "modelado", "dist": "empirica", **q,
            "n_amostras": len(p),
            "observacao": f"restricoes de eixos; s<={s_max:.3f}",
        })

    qs = resumo(s)
    print(f"  {'excedente de semirreboques (s)':<30} {qs['p05']:>11.3f} "
          f"{qs['p50']:>11.3f} {qs['p95']:>11.3f}")
    linhas.append({
        "ano_ref": ano, "mes_ref": mes, "uf": "BR",
        "id_classe": "__EXCEDENTE_SEMIS", "variavel": "excedente_semirreboques",
        "unidade": "fracao", "fonte": fonte, "cenario": cenario,
        "metodo": "modelado", "dist": "empirica", **qs,
        "n_amostras": len(p),
        "observacao": f"teto imposto pelo dado: {s_max:.3f}",
    })
    return linhas


def roda(cont, cfg, imputar, ano, mes, n, semente):
    base = "com imputacao" if imputar else "so eixos informados"
    cav3, s2, s3 = entradas(cont, imputar)
    print(f"\n{'=' * 64}\n{base.upper()}")
    print(f"  cavalos de 3 eixos : {cav3:>12,.0f}")
    print(f"  semis de 2 eixos   : {s2:>12,.0f}")
    print(f"  semis de 3 eixos   : {s3:>12,.0f}")

    p, s, s_max, diag = amostra(cfg, cav3, s2, s3, n, semente)
    print(f"  teto do excedente s, imposto pelo dado: {s_max:.3f}")
    print(f"  amostras viaveis: {len(p):,} de {n:,} ({len(p)/n:.1%})")

    if len(p) < 300:
        print("  FALHA: a contabilidade de eixos em "
              "crosswalk/configuracoes_cvc.csv nao admite solucao com estes "
              "totais.", file=sys.stderr)
        return []

    linhas = []

    # 1) conjunto viavel puro — so o que os eixos permitem, sem opiniao
    print(f"\n  [A] CONJUNTO VIAVEL — so as restricoes de eixos")
    linhas += publica(p, s, cav3, cfg, ano, mes, "senatran_eixos",
                      f"{base} | sem priors", s_max)

    # 2) com as faixas de participacao aplicadas por cima
    pf, sf = filtra_priors(p, s, cfg)
    frac = len(pf) / len(p)
    print(f"\n  [B] COM AS FAIXAS DE PARTICIPACAO "
          f"({len(pf):,} das viaveis, {frac:.1%})")
    if len(pf) < 300:
        print("  as faixas excluem quase todo o conjunto viavel — provavel "
              "conflito entre o prior e o dado. Publicando so [A].",
              file=sys.stderr)
    else:
        linhas += publica(pf, sf, cav3, cfg, ano, mes, "senatran_eixos",
                          f"{base} | com priors", s_max)
    return linhas


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ano", type=int, required=True)
    ap.add_argument("--mes", type=int, default=None)
    ap.add_argument("--n", type=int, default=300_000)
    ap.add_argument("--semente", type=int, default=42)
    a = ap.parse_args()

    if not CONFIG.exists():
        sys.exit(f"faltam as configuracoes: {CONFIG}")
    cfg = pd.read_csv(CONFIG)

    if not (cfg["share_min"].sum() <= 1.0 <= cfg["share_max"].sum()):
        sys.exit(f"faixas impossiveis: soma dos minimos "
                 f"{cfg['share_min'].sum():.2f}, dos maximos "
                 f"{cfg['share_max'].sum():.2f}. O intervalo precisa conter 1.")

    df = le_eixos(a.ano, a.mes)
    cont = contagens(df)
    for chave, rot in (("cavalo", "cavalos"), ("semi", "semirreboques")):
        b = cont[chave]
        print(f"  {rot}: {b['total']:,} | sem eixo informado "
              f"{b['frac_sem_info']:.1%}")

    linhas = []
    for imputar in (False, True):
        linhas += roda(cont, cfg, imputar, a.ano, a.mes, a.n, a.semente)

    if not linhas:
        sys.exit("\nnenhum cenario produziu resultado — ajuste as faixas.")

    SAIDA.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(linhas)
    sufixo = f"_{a.ano}" + (f"_{a.mes:02d}" if a.mes else "")
    destino = SAIDA / f"conjuntos_por_eixos{sufixo}.parquet"
    out.to_parquet(destino, index=False)
    out.to_csv(SAIDA / f"conjuntos_por_eixos{sufixo}.csv", index=False)
    print(f"\n{len(out)} linhas -> {destino}")
    print("            e o .csv ao lado, para inspecao rapida")


if __name__ == "__main__":
    main()
