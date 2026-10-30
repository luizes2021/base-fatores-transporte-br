"""
20_modelo_acoplamento.py — camada 10_extraidos -> 20_harmonizados

O PROBLEMA
Nem o SENATRAN nem a RNTRC contam conjuntos articulados. Ambos contam pecas:
cavalos mecanicos de um lado, semirreboques do outro. Carreta, bitrem e
rodotrem precisam ser INFERIDOS.

O MODELO
Cada cavalo em operacao puxa exatamente uma configuracao. Entao, chamando de
p_c a participacao da configuracao c entre os cavalos (as p somam 1) e de
reb_c o numero de unidades rebocadas que cada conjunto consome:

    rebocadas_por_cavalo = SOMA_c (p_c * reb_c)

Mas a frota tem MAIS rebocadas do que as em uso: no engate-e-desengate, o
semirreboque fica no cliente carregando ou descarregando enquanto o cavalo
roda com outro. Chamando esse excedente de s:

    R = SOMA_c (p_c * reb_c) * (1 + s)

Como reb = 1 para carreta e 2 para bitrem/rodotrem, isso simplifica para:

    R = (1 + p_bitrem + p_rodotrem) * (1 + s)

Uma equacao, cinco incognitas. A razao observada NAO identifica a composicao
sozinha — quem publica um numero unico aqui esta escondendo uma escolha.

A SOLUCAO
Amostragem por rejeicao. Sorteia-se p e s dentro das faixas declaradas em
crosswalk/acoplamento_priors.csv, calcula-se o R implicado e guarda-se apenas
o que reproduz o R observado dentro da tolerancia. O resultado e uma
DISTRIBUICAO por classe, nao um ponto.

Se a taxa de aceitacao for ~0, as faixas sao incompativeis com o dado — e isso
e um achado, nao um bug. O script avisa e mostra o R que as faixas produzem.

DUAS FONTES, DE PROPOSITO
SENATRAN = frota registrada (inflada, sem baixa efetiva).
RNTRC    = frota ativa de carga remunerada (exclui frota propria).
A verdade esta entre as duas. O script roda nas duas e publica ambas.

LIMITE DECLARADO DA v0.1
Dollies e reboques (romeu-e-julieta) nao entram no modelo: o tipo REBOQUE
tambem e puxado por caminhao rigido, e separar isso exige dado que nao temos.
Soma-se a isso que o SENATRAN nao informa eixos nem PBT.

Uso:
    python codigo/20_modelo_acoplamento.py --ano 2024
    python codigo/20_modelo_acoplamento.py --ano 2024 --n 400000 --tol 0.015
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "dados" / "10_extraidos"
SAIDA = RAIZ / "dados" / "20_harmonizados"
PRIORS = RAIZ / "crosswalk" / "acoplamento_priors.csv"

# Excedente de rebocadas sobre as em uso (engate-e-desengate, sazonalidade,
# unidades paradas). Faixa larga de proposito: nao ha medicao publica no Brasil.
EXCEDENTE_MIN, EXCEDENTE_MAX = 0.05, 1.30

MARCA_TRATORA = ("TRATOR", "CAVALO")
MARCA_REBOCADA = ("SEMI",)  # REBOQUE fica de fora — ver limite declarado acima

# ARMADILHA: o SENATRAN publica 'TRATOR ESTEIRA' e 'TRATOR RODAS' — tratores
# AGRICOLAS e de construcao, que nunca puxam semirreboque. Procurar so por
# 'TRATOR' os inclui e infla a contagem de cavalos mecanicos em ~4%, baixando
# a razao R e, por consequencia, a estimativa de bitrens e rodotrens.
# Nenhuma mensagem de erro apareceria.
EXCLUI_TRATORA = ("ESTEIRA", "RODAS", "AGRICOLA")


def soma_por_marca(df, col_tipo, col_valor, marcas, exclui=()):
    alvo = df[col_tipo].astype(str)
    sel = np.zeros(len(df), dtype=bool)
    for m in marcas:
        sel |= alvo.str.contains(m, na=False).to_numpy()
    for e in exclui:
        sel &= ~alvo.str.contains(e, na=False).to_numpy()
    return float(df.loc[sel, col_valor].sum())


def le_fonte(ano: int):
    """Devolve [(rotulo, n_tratores, n_rebocadas), ...] para as fontes presentes."""
    achados = []

    p_sen = ENTRADA / f"senatran_frota_{ano}.parquet"
    if p_sen.exists():
        d = pd.read_parquet(p_sen)
        achados.append((
            "senatran_registrada",
            soma_por_marca(d, "tipo_senatran", "frota_registrada", MARCA_TRATORA,
                           EXCLUI_TRATORA),
            soma_por_marca(d, "tipo_senatran", "frota_registrada", MARCA_REBOCADA),
        ))

    p_rn = ENTRADA / f"rntrc_veiculos_{ano}.parquet"
    if p_rn.exists():
        d = pd.read_parquet(p_rn)
        achados.append((
            "rntrc_ativa",
            soma_por_marca(d, "tipo_rntrc", "n_veiculos", MARCA_TRATORA,
                           EXCLUI_TRATORA),
            soma_por_marca(d, "tipo_rntrc", "n_veiculos", MARCA_REBOCADA),
        ))

    if not achados:
        sys.exit(f"nenhum parquet de frota para {ano} em {ENTRADA}. Rode as "
                 "etapas 01 e 03 primeiro.")
    return achados


def amostra(priors: pd.DataFrame, r_obs: float, n: int, tol: float, semente: int):
    """Rejeicao: devolve (shares aceitos, excedentes aceitos, r implicado de todos)."""
    rng = np.random.default_rng(semente)
    lo = priors["share_min"].to_numpy()
    hi = priors["share_max"].to_numpy()
    reb = priors["rebocadas_por_conjunto"].to_numpy(dtype=float)

    p = rng.uniform(lo, hi, size=(n, len(priors)))
    p /= p.sum(axis=1, keepdims=True)
    # normalizar pode jogar para fora das faixas declaradas: descarta esses
    dentro = ((p >= lo) & (p <= hi)).all(axis=1)

    s = rng.uniform(EXCEDENTE_MIN, EXCEDENTE_MAX, size=n)
    r_impl = (p * reb).sum(axis=1) * (1.0 + s)

    aceito = dentro & (np.abs(r_impl - r_obs) <= tol * r_obs)
    return p[aceito], s[aceito], r_impl[dentro]


def resumo(valores: np.ndarray) -> dict:
    return {
        "p05": float(np.percentile(valores, 5)),
        "p50": float(np.percentile(valores, 50)),
        "p95": float(np.percentile(valores, 95)),
    }


def roda_fonte(rotulo, n_trat, n_reb, priors, ano, n, tol, semente):
    print(f"\n--- {rotulo} ---")
    if n_trat <= 0 or n_reb <= 0:
        print("  tratoras ou rebocadas ausentes — fonte ignorada", file=sys.stderr)
        return []

    r_obs = n_reb / n_trat
    print(f"  tratoras: {n_trat:,.0f}   rebocadas: {n_reb:,.0f}   R = {r_obs:.3f}")

    p, s, r_todos = amostra(priors, r_obs, n, tol, semente)
    taxa = len(p) / n
    print(f"  aceitos: {len(p):,} de {n:,} ({taxa:.1%})")

    if len(p) < 500:
        faixa = (float(np.percentile(r_todos, 1)), float(np.percentile(r_todos, 99)))
        print(f"  FALHA: as faixas do prior produzem R entre {faixa[0]:.2f} e "
              f"{faixa[1]:.2f}, incompativel com o R observado de {r_obs:.2f}.",
              file=sys.stderr)
        print("  Isso e um achado, nao um bug: ou as participacoes assumidas "
              "estao erradas, ou o excedente de rebocadas no Brasil e maior do "
              "que a faixa declarada. Ajuste crosswalk/acoplamento_priors.csv "
              "ou EXCEDENTE_MAX e documente a mudanca.", file=sys.stderr)
        return []

    linhas = []
    print(f"\n  {'classe':<30} {'p05':>12} {'p50':>12} {'p95':>12}")
    for i, cl in priors.reset_index(drop=True).iterrows():
        n_conj = p[:, i] * n_trat
        q = resumo(n_conj)
        print(f"  {cl['classe_nome']:<30} {q['p05']:>12,.0f} {q['p50']:>12,.0f} "
              f"{q['p95']:>12,.0f}")
        linhas.append({
            "ano_ref": ano, "uf": "BR", "id_classe": cl["id_classe"],
            "variavel": "n_conjuntos", "unidade": "veiculos",
            "fonte": rotulo, "metodo": "modelado", "dist": "empirica",
            **q,
            "n_amostras": len(p),
            "observacao": f"rejeicao sobre R={r_obs:.3f}, tol={tol}",
        })

    qs = resumo(s)
    print(f"\n  excedente de rebocadas (s): p05={qs['p05']:.2f}  "
          f"p50={qs['p50']:.2f}  p95={qs['p95']:.2f}")
    linhas.append({
        "ano_ref": ano, "uf": "BR", "id_classe": "__EXCEDENTE_REBOCADAS",
        "variavel": "excedente_rebocadas", "unidade": "fracao",
        "fonte": rotulo, "metodo": "modelado", "dist": "empirica", **qs,
        "n_amostras": len(p),
        "observacao": "posterior do excedente, dado o R observado",
    })
    return linhas


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ano", type=int, required=True)
    ap.add_argument("--n", type=int, default=200_000, help="amostras sorteadas")
    ap.add_argument("--tol", type=float, default=0.02, help="tolerancia relativa em R")
    ap.add_argument("--semente", type=int, default=42)
    a = ap.parse_args()

    if not PRIORS.exists():
        sys.exit(f"priors ausentes: {PRIORS}")
    priors = pd.read_csv(PRIORS)

    soma_min = priors["share_min"].sum()
    soma_max = priors["share_max"].sum()
    if not (soma_min <= 1.0 <= soma_max):
        sys.exit(f"faixas impossiveis: soma dos minimos={soma_min:.2f}, dos "
                 f"maximos={soma_max:.2f}. O intervalo precisa conter 1.")

    print(f"priors: {len(priors)} classes | excedente de rebocadas entre "
          f"{EXCEDENTE_MIN} e {EXCEDENTE_MAX}")

    linhas = []
    for rotulo, n_trat, n_reb in le_fonte(a.ano):
        linhas += roda_fonte(rotulo, n_trat, n_reb, priors, a.ano,
                             a.n, a.tol, a.semente)

    if not linhas:
        sys.exit("\nnenhuma fonte produziu resultado — ajuste os priors e repita.")

    SAIDA.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(linhas)
    destino = SAIDA / f"frota_conjuntos_{a.ano}.parquet"
    df.to_parquet(destino, index=False)
    df.to_csv(SAIDA / f"frota_conjuntos_{a.ano}.csv", index=False)
    print(f"\n{len(df)} linhas -> {destino}")
    print("            e o .csv ao lado, para inspecao rapida")


if __name__ == "__main__":
    main()
