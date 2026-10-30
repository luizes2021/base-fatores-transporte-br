"""
30_harmoniza_classes.py — camadas 10/20 -> 30_publicados

Junta as tres fontes ja extraidas e publica a tabela por CLASSE CANONICA:

    id_classe | frota | km_ano_veic | l_por_km | gCO2e_por_km | ...
              | carga_util_t | l_por_tkm_capacidade | gCO2e_por_tkm_capacidade

Entradas:
    10_extraidos/ineavar_consumo_*.parquet      km/ano, L/km, fatores (por
                                                categoria de EMISSAO)
    10_extraidos/senatran_eixos_*.parquet       distribuicao de eixos
    20_harmonizados/conjuntos_por_eixos_*.parquet  conjuntos articulados
    crosswalk/ineavar_para_canonica.csv         mapa categoria -> classe
    crosswalk/classes_canonicas.csv             carga util de referencia

O QUE ESTA ETAPA PODE E NAO PODE FAZER

PODE: dar a FROTA por classe canonica, porque a contagem de eixos do SENATRAN
e o modelo de acoplamento separam o que o INEAVAR empilha.

NAO PODE: diferenciar L/km DENTRO de uma categoria do INEAVAR. Carreta de 5
eixos e rodotrem estao os dois em 'Caminhoes pesados', e o inventario publica
um unico valor para a categoria. Entao as duas herdam o MESMO L/km. Isso nao
e descuido: e o limite da fonte, e esta marcado na coluna `metodo` de cada
linha ('herdado' x 'medido').

POR QUE AINDA ASSIM VALE SEPARAR AS CLASSES
Porque o L/km e quase igual, mas o L/TKM nao e. A carga util vai de 6 t (VUC)
a 50 t (rodotrem). Dividir o mesmo consumo por capacidades tao diferentes muda
a intensidade por tonelada em quase uma ordem de grandeza. E exatamente o
numero que estudos de VRP verde e de descarbonizacao usam.

ATENCAO AO QUE A COLUNA DE TKM SIGNIFICA
`l_por_tkm_capacidade` usa a CARGA UTIL MAXIMA, nao a carga real. E um piso
teorico: o veiculo real roda com fator de carga abaixo de 1 e parte do
percurso vazio. O valor real e MAIOR — tipicamente bem maior. A coluna existe
para mostrar a ordem de grandeza e o efeito da classe, nao para ser usada como
fator de emissao. O fator de carga e o percurso vazio sao a lacuna que a v0.2
precisa preencher, e nao ha fonte publica brasileira para eles.

Uso:
    python codigo/30_harmoniza_classes.py --ano 2024
    python codigo/30_harmoniza_classes.py --ano 2024 --ano-frota 2023 --mes-frota 12
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
EXTRAIDOS = RAIZ / "dados" / "10_extraidos"
HARMONIZADOS = RAIZ / "dados" / "20_harmonizados"
PUBLICADOS = RAIZ / "dados" / "30_publicados"
CW = RAIZ / "crosswalk"

# Classes rigidas: a contagem de eixos do SENATRAN as separa diretamente.
EIXOS_RIGIDO = {2: ["VUC", "TOCO"], 3: ["TRUCK"], 4: ["BITRUCK"]}
ARTICULADAS = ["CARRETA5", "CARRETA6", "BITREM", "RODOTREM"]


def acha(pasta: Path, prefixo: str, ano: int, mes=None) -> Path:
    padrao = f"{prefixo}_{ano}" + (f"_{mes:02d}" if mes else "")
    achados = sorted(pasta.glob(f"{padrao}*.parquet"))
    if not achados:
        sys.exit(f"nao achei {padrao}*.parquet em {pasta}")
    return achados[-1]


def frota_rigidos(eixos: pd.DataFrame) -> dict:
    """Caminhoes rigidos de carga, por numero de eixos.

    VUC e TOCO sao ambos de 2 eixos e o registro nao os separa — a divisao
    depende do PBT, que o SENATRAN nao informa. Ficam agregados em VUC_TOCO
    e sao repartidos depois, pela frota do INEAVAR (que tem classe de peso).
    """
    c = eixos[(eixos["tipo"] == "CAMINHAO")
              & (eixos["especie"].isin(["CARGA", "TRACAO"]))
              & eixos["eixos"].notna()]
    por_eixo = c.groupby("eixos")["n_veiculos"].sum()
    conhecido = int(por_eixo.sum())
    total = int(eixos[(eixos["tipo"] == "CAMINHAO")
                      & (eixos["especie"].isin(["CARGA", "TRACAO"]))]
                ["n_veiculos"].sum())
    print(f"  rigidos de carga: {total:,} ({(total - conhecido) / total:.1%} "
          "sem eixo informado)")
    return {
        "VUC_TOCO": float(por_eixo.get(2, 0)),
        "TRUCK": float(por_eixo.get(3, 0)),
        "BITRUCK": float(por_eixo.get(4, 0)),
        "_conhecido": conhecido,
    }


def frota_articuladas(conj: pd.DataFrame, cenario_pref: str) -> dict:
    """Conjuntos articulados, do modelo de acoplamento (p50)."""
    c = conj[conj["variavel"] == "n_conjuntos"]
    cenarios = sorted(c["cenario"].unique())
    escolhido = next((x for x in cenarios if cenario_pref in x), cenarios[0])
    print(f"  cenario do acoplamento: '{escolhido}'")
    print(f"    (disponiveis: {cenarios})")
    sub = c[c["cenario"] == escolhido]
    return {r["id_classe"]: {"p05": r["p05"], "p50": r["p50"], "p95": r["p95"]}
            for _, r in sub.iterrows()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ano", type=int, required=True,
                    help="ano de referencia do INEAVAR")
    ap.add_argument("--ano-frota", type=int, default=None,
                    help="ano do SENATRAN, se diferente")
    ap.add_argument("--mes-frota", type=int, default=None)
    ap.add_argument("--cenario", default="so eixos informados | com priors")
    a = ap.parse_args()

    ano_frota = a.ano_frota or a.ano

    classes = pd.read_csv(CW / "classes_canonicas.csv").set_index("id_classe")
    mapa = pd.read_csv(CW / "ineavar_para_canonica.csv")
    mapa = mapa[mapa["tipo_mapeamento"] != "FORA_DO_ESCOPO"]

    inv = pd.read_parquet(acha(EXTRAIDOS, "ineavar_consumo", a.ano))
    inv = inv[inv["combustivel"].str.contains("DIESEL", na=False)]
    if inv.empty:
        sys.exit("nenhuma linha de diesel no parquet do INEAVAR")

    vistas = set(inv["categoria"])
    esperadas = set(mapa["categoria_ineavar"])
    if not (vistas & esperadas):
        sys.exit(
            "as categorias do parquet nao batem com o crosswalk.\n"
            f"  no parquet: {sorted(vistas)[:8]}\n"
            f"  no crosswalk: {sorted(esperadas)[:8]}\n"
            "Isso costuma significar que o parquet veio da fixture sintetica, "
            "e nao do arquivo real do MMA. Reextraia com:\n"
            "  python codigo/05_extrai_ineavar.py "
            "dados/00_brutos/consumo_emissoes.csv --ano <ANO>"
        )
    eixos = pd.read_parquet(acha(EXTRAIDOS, "senatran_eixos", ano_frota,
                                 a.mes_frota))
    conj = pd.read_parquet(acha(HARMONIZADOS, "conjuntos_por_eixos", ano_frota,
                                a.mes_frota))

    print(f"\nFROTA POR CLASSE ({ano_frota})")
    rig = frota_rigidos(eixos)
    art = frota_articuladas(conj, a.cenario)

    # --- intensidades por categoria do INEAVAR ---
    def agrega(cats):
        s = inv[inv["categoria"].isin(cats)]
        if s.empty or s["km_ajustado"].sum() == 0:
            return None
        km, lt = s["km_ajustado"].sum(), s["litros_ajustado"].sum()
        fr = s["frota"].sum()
        out = {"l_por_km": lt / km, "km_ano_veic": km / fr if fr else None,
               "frota_ineavar": fr}
        for col, nome in (("gco2e", "gCO2e"), ("gco2_fossil", "gCO2_fossil"),
                          ("gch4", "gCH4"), ("gn2o", "gN2O")):
            if col in s.columns and s[col].sum() > 0:
                out[f"{nome}_por_km"] = s[col].sum() / km
        if {"litros_fossil", "litros_renovavel"} <= set(s.columns):
            tot = s["litros_fossil"].sum() + s["litros_renovavel"].sum()
            out["fracao_biogenica"] = s["litros_renovavel"].sum() / tot
        return out

    CAT = {
        "VUC": ["CAMINHOES SEMILEVES", "CAMINHOES LEVES"],
        "TOCO": ["CAMINHOES MEDIOS"],
        "TRUCK": ["CAMINHOES SEMIPESADOS"],
        "BITRUCK": ["CAMINHOES SEMIPESADOS", "CAMINHOES PESADOS"],
        "CARRETA5": ["CAMINHOES PESADOS"], "CARRETA6": ["CAMINHOES PESADOS"],
        "BITREM": ["CAMINHOES PESADOS"], "RODOTREM": ["CAMINHOES PESADOS"],
    }

    # VUC e TOCO: repartir os 2 eixos na proporcao da frota do INEAVAR
    f_vuc = agrega(CAT["VUC"])["frota_ineavar"]
    f_toco = agrega(CAT["TOCO"])["frota_ineavar"]
    share_vuc = f_vuc / (f_vuc + f_toco)
    print(f"  VUC/TOCO: {rig['VUC_TOCO']:,.0f} de 2 eixos repartidos "
          f"{share_vuc:.1%} / {1 - share_vuc:.1%} pela frota do INEAVAR")

    frota = {
        "VUC": rig["VUC_TOCO"] * share_vuc,
        "TOCO": rig["VUC_TOCO"] * (1 - share_vuc),
        "TRUCK": rig["TRUCK"], "BITRUCK": rig["BITRUCK"],
    }
    for k in ARTICULADAS:
        frota[k] = art.get(k, {}).get("p50", float("nan"))

    linhas = []
    for id_classe, cl in classes.iterrows():
        ag = agrega(CAT[id_classe])
        if ag is None:
            continue
        cu = cl["carga_util_t"]
        r = {
            "ano_ref": a.ano, "ano_frota": ano_frota, "uf": "BR",
            "id_classe": id_classe, "classe_nome": cl["classe_nome"],
            "ordem": int(cl["ordem"]), "eixos": int(cl["eixos_total"]),
            "pbt_cmt_t": cl["pbt_cmt_t"], "carga_util_t": cu,
            "frota": frota[id_classe],
            "frota_metodo": "modelado" if id_classe in ARTICULADAS
                            else "eixos_senatran",
            "km_ano_veic": ag["km_ano_veic"],
            "l_por_km": ag["l_por_km"],
            "intensidade_metodo": "herdado_categoria_ineavar",
            "categoria_ineavar": " + ".join(CAT[id_classe]),
            "fracao_biogenica": ag.get("fracao_biogenica"),
        }
        for nome in ("gCO2e", "gCO2_fossil", "gCH4", "gN2O"):
            k = f"{nome}_por_km"
            if k in ag:
                r[k] = ag[k]
                r[f"{nome}_por_tkm_capacidade"] = ag[k] / cu
        r["l_por_tkm_capacidade"] = ag["l_por_km"] / cu
        if id_classe in art:
            r["frota_p05"] = art[id_classe]["p05"]
            r["frota_p95"] = art[id_classe]["p95"]
        linhas.append(r)

    out = pd.DataFrame(linhas).sort_values("ordem", ignore_index=True)

    print(f"\n{'classe':<24} {'frota':>10} {'km/ano':>9} {'L/km':>7} "
          f"{'carga t':>8} {'L/tkm cap':>10} {'gCO2e/tkm cap':>14}")
    for _, r in out.iterrows():
        g = r.get("gCO2e_por_tkm_capacidade", float("nan"))
        print(f"{r['classe_nome'][:23]:<24} {r['frota']:>10,.0f} "
              f"{r['km_ano_veic']:>9,.0f} {r['l_por_km']:>7.3f} "
              f"{r['carga_util_t']:>8.1f} {r['l_por_tkm_capacidade']:>10.4f} "
              f"{g:>14.1f}")

    print("\n  ATENCAO: as colunas '_capacidade' usam a CARGA UTIL MAXIMA.")
    print("  Sao piso teorico — o veiculo real roda abaixo da capacidade e")
    print("  parte do percurso vazio, entao o valor efetivo e MAIOR.")
    print("  Nao use como fator de emissao: falta o fator de carga (v0.2).")

    # Demonstracao do tamanho da lacuna. NAO vai para o arquivo publicado:
    # seriam numeros inventados com cara de fator de emissao.
    if "gCO2e_por_tkm_capacidade" in out.columns:
        print("\n  QUANTO O FATOR DE CARGA MUDA (ilustracao, nao publicada)")
        print("  gCO2e/tkm = valor de capacidade / fator_carga / (1 - vazio)")
        cen = [("capacidade plena", 1.00, 0.00),
               ("carga 0,75 | vazio 15%", 0.75, 0.15),
               ("carga 0,60 | vazio 25%", 0.60, 0.25),
               ("carga 0,45 | vazio 35%", 0.45, 0.35)]
        alvo = out[out["id_classe"].isin(["CARRETA5", "RODOTREM"])]
        print(f"  {'cenario':<26}" + "".join(
            f"{r['id_classe']:>14}" for _, r in alvo.iterrows()))
        for nome, fc, vz in cen:
            vals = "".join(
                f"{r['gCO2e_por_tkm_capacidade'] / fc / (1 - vz):>14.1f}"
                for _, r in alvo.iterrows())
            print(f"  {nome:<26}{vals}")
        print("  Para comparar: GLEC e DEFRA publicam ~50-80 gCO2e/tkm para")
        print("  conjuntos pesados — o que so e alcancado nos cenarios com")
        print("  fator de carga realista. E a prova de que a lacuna da v0.2")
        print("  nao e detalhe: e o que separa um piso teorico de um fator.")

    PUBLICADOS.mkdir(parents=True, exist_ok=True)
    destino = PUBLICADOS / f"fatores_por_classe_{a.ano}.csv"
    out.to_csv(destino, index=False)
    out.to_parquet(PUBLICADOS / f"fatores_por_classe_{a.ano}.parquet",
                   index=False)
    print(f"\n{len(out)} classes -> {destino}")


if __name__ == "__main__":
    main()
