"""
Roda o pipeline inteiro sobre os arquivos sinteticos e confere os resultados.

NAO testa os dados reais — testa se o CODIGO ainda roda. E o que pega quando
pandas, pyarrow ou openpyxl mudam de API entre versoes: voce descobre num
e-mail automatico do CI, nao em abril quando for publicar a versao do ano.

    python codigo/_teste/testa_pipeline.py

Sai com codigo 0 se tudo passou, 1 se algo quebrou.
"""

import subprocess
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent.parent
TESTE = RAIZ / "codigo" / "_teste"
EXTRAIDOS = RAIZ / "dados" / "10_extraidos"
HARMONIZADOS = RAIZ / "dados" / "20_harmonizados"

ANO = 2024
falhas = []


def roda(descricao, *args):
    print(f"\n>>> {descricao}")
    r = subprocess.run([sys.executable, *map(str, args)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        falhas.append(f"{descricao}: saiu com codigo {r.returncode}")
        print(r.stdout[-1500:])
        print(r.stderr[-1500:], file=sys.stderr)
        return False
    print(r.stdout.strip()[-600:] or "(sem saida)")
    return True


def confere(condicao, mensagem):
    if condicao:
        print(f"    ok  {mensagem}")
    else:
        falhas.append(mensagem)
        print(f"  FALHA {mensagem}", file=sys.stderr)


def limpa_saidas():
    """Apaga os parquet antes de rodar.

    Sem isto, um arquivo de uma execucao anterior — ou de dados REAIS — pode
    ser lido no lugar do que o teste acabou de gerar, e o teste passa sem ter
    testado nada. Ja aconteceu: um parquet real com 972 linhas satisfez a
    verificacao destinada ao sintetico, que tambem tem 972.
    """
    n = 0
    for pasta in (EXTRAIDOS, HARMONIZADOS):
        for p in pasta.glob("*.parquet"):
            p.unlink()
            n += 1
        for p in pasta.glob("*.csv"):
            p.unlink()
            n += 1
    print(f"  {n} arquivo(s) de saida anteriores removidos")


def main() -> int:
    print("=" * 70)
    print("TESTE DO PIPELINE SOBRE ARQUIVOS SINTETICOS")
    print(f"python {sys.version.split()[0]} | pandas {pd.__version__}")
    print("=" * 70)
    limpa_saidas()

    # --- geradores ---
    for nome in ("gera_senatran_sintetico.py", "gera_anp_sintetico.py",
                 "gera_rntrc_sintetico.py", "gera_senatran_eixos_sintetico.py",
                 "gera_ineavar_sintetico.py"):
        roda(f"gerando fixture: {nome}", TESTE / nome)

    # --- SENATRAN ---
    roda("extraindo SENATRAN",
         RAIZ / "codigo" / "01_extrai_senatran.py",
         TESTE / "senatran_sintetico.xlsx", ANO)
    p = EXTRAIDOS / f"senatran_frota_{ANO}.parquet"
    confere(p.exists(), "parquet do SENATRAN existe")
    if p.exists():
        d = pd.read_parquet(p)
        tipos = set(d["tipo_senatran"])
        confere(d["uf"].nunique() == 27, f"27 UFs (veio {d['uf'].nunique()})")
        confere("TOTAL" not in tipos, "coluna TOTAL nao virou tipo de veiculo")
        confere("BRASIL" not in set(d["uf"]), "linha Brasil nao virou UF")
        confere({"CAMINHAO", "CAMINHAO TRATOR", "SEMI REBOQUE"} <= tipos,
                "tipos de carga presentes")
        confere({"TRATOR ESTEIRA", "TRATOR RODAS"} <= tipos,
                "tratores agricolas preservados na extracao")

    # --- ANP: os dois layouts devem convergir ---
    totais = {}
    for rotulo, arquivo in (("longo", "anp_vendas_sintetico.csv"),
                            ("largo", "anp_vendas_largo_sintetico.csv")):
        if roda(f"extraindo ANP ({rotulo})",
                RAIZ / "codigo" / "02_extrai_anp.py",
                TESTE / arquivo, "--ano", ANO):
            # as fixtures nao tem 'tipo'/'segmento'/'municipio' no nome,
            # entao o extrator as classifica como visao 'geral'
            p = EXTRAIDOS / f"anp_vendas_diesel_geral_{ANO}.parquet"
            confere(p.exists(), f"ANP {rotulo}: parquet gerado em {p.name}")
            if not p.exists():
                continue
            d = pd.read_parquet(p)
            totais[rotulo] = float(d["vendas_litros"].sum())
            confere(len(d) == 972, f"ANP {rotulo}: 972 linhas (veio {len(d)})")
            confere("segmento" in d.columns, f"ANP {rotulo}: coluna segmento")

    if len(totais) == 2:
        dif = abs(totais["longo"] - totais["largo"]) / totais["longo"]
        confere(dif < 1e-9,
                f"os dois layouts da ANP convergem (diferenca {dif:.2e})")
        bi = totais["largo"] / 1e9
        confere(50 <= bi <= 70, f"total do diesel plausivel ({bi:.1f} bi L)")

    # --- RNTRC ---
    roda("extraindo RNTRC",
         RAIZ / "codigo" / "03_extrai_rntrc.py",
         TESTE / "rntrc_veiculos_sintetico.csv", "--ano", ANO)
    p = EXTRAIDOS / f"rntrc_veiculos_{ANO}.parquet"
    confere(p.exists(), "parquet da RNTRC existe")
    if p.exists():
        d = pd.read_parquet(p)
        confere(int(d["n_veiculos"].sum()) == 120_000,
                f"RNTRC: 120.000 veiculos (veio {int(d['n_veiculos'].sum()):,})")

    # --- modelo de acoplamento ---
    roda("rodando o modelo de acoplamento",
         RAIZ / "codigo" / "20_modelo_acoplamento.py", "--ano", ANO)
    p = HARMONIZADOS / f"frota_conjuntos_{ANO}.parquet"
    confere(p.exists(), "parquet dos conjuntos existe")
    if p.exists():
        d = pd.read_parquet(p)
        classes = set(d["id_classe"])
        confere({"CARRETA5", "CARRETA6", "BITREM", "RODOTREM"} <= classes,
                "as quatro classes articuladas foram estimadas")
        conj = d[d["variavel"] == "n_conjuntos"]
        confere((conj["p05"] <= conj["p50"]).all()
                and (conj["p50"] <= conj["p95"]).all(),
                "percentis ordenados (p05 <= p50 <= p95)")
        confere((conj["p05"] > 0).all(), "nenhuma classe com estimativa zero")

        # os cavalos usados no modelo devem ser SO 'CAMINHAO TRATOR' —
        # 'TRATOR ESTEIRA' e 'TRATOR RODAS' sao agricolas e nao puxam carreta
        sen = pd.read_parquet(EXTRAIDOS / f"senatran_frota_{ANO}.parquet")
        por_tipo = sen.groupby("tipo_senatran")["frota_registrada"].sum()
        esperado = por_tipo["SEMI REBOQUE"] / por_tipo["CAMINHAO TRATOR"]
        obs = d[d["fonte"] == "senatran_registrada"]["observacao"].iloc[0]
        r_usado = float(obs.split("R=")[1].split(",")[0])
        confere(abs(r_usado - esperado) < 0.01,
                f"R do modelo = semi/caminhao-trator ({r_usado:.3f} vs "
                f"{esperado:.3f}) — tratores agricolas fora")

    # --- SENATRAN eixos (04) ---
    roda("extraindo SENATRAN tipo/especie/eixos",
         RAIZ / "codigo" / "04_extrai_senatran_eixos.py",
         TESTE / "senatran_eixos_sintetico.xlsx", ANO)
    p = EXTRAIDOS / f"senatran_eixos_{ANO}.parquet"
    confere(p.exists(), "parquet de eixos existe")
    if p.exists():
        d = pd.read_parquet(p)
        confere(d["uf"].nunique() == 27, f"eixos: 27 UFs ({d['uf'].nunique()})")
        confere("NAO IDENTIFICADO" not in set(d["uf"]),
                "UFs nao identificadas descartadas")
        eixos = d["eixos"].dropna()
        confere(eixos.between(1, 9).all(),
                "eixos implausiveis viraram nao informado")
        confere(d["eixos"].isna().any(),
                "eixos=0 preservado como nao informado, nao como zero")

    # --- acoplamento por eixos (21) ---
    roda("rodando o acoplamento por eixos",
         RAIZ / "codigo" / "21_acoplamento_eixos.py", "--ano", ANO)
    p = HARMONIZADOS / f"conjuntos_por_eixos_{ANO}.parquet"
    confere(p.exists(), "parquet do acoplamento por eixos existe")
    if p.exists():
        d = pd.read_parquet(p)
        conj = d[d["variavel"] == "n_conjuntos"]
        confere((conj["p05"] <= conj["p50"]).all()
                and (conj["p50"] <= conj["p95"]).all(),
                "eixos: percentis ordenados")
        confere(conj["cenario"].nunique() >= 2,
                "publica cenarios com e sem imputacao")
        confere((conj["p05"] >= 0).all(), "nenhum conjunto negativo")

        # o teto do excedente tem de vir do dado, nao de um chute
        exc = d[d["variavel"] == "excedente_semirreboques"]
        confere(len(exc) > 0 and (exc["p95"] <= 1.0).all(),
                "excedente dentro do teto imposto pelo dado")

    # --- INEAVAR (05) ---
    roda("extraindo INEAVAR", RAIZ / "codigo" / "05_extrai_ineavar.py",
         TESTE / "ineavar_sintetico.csv", "--ano", ANO)
    p = EXTRAIDOS / f"ineavar_consumo_{ANO}.parquet"
    confere(p.exists(), "parquet do INEAVAR existe")
    if p.exists():
        d = pd.read_parquet(p)
        confere("l_por_km" in d.columns, "L/km calculado")
        confere("fracao_biogenica" in d.columns, "fracao biogenica calculada")
        lk = d["l_por_km"].dropna()
        confere(lk.between(0.1, 0.8).all(),
                f"L/km plausivel para diesel ({lk.min():.2f}-{lk.max():.2f})")
        confere(not d.duplicated(
            subset=[c for c in ["ano_ref", "categoria", "motor", "combustivel",
                                "fase"] if c in d.columns]).any(),
            "coortes de ano-modelo agregadas sem duplicar")

    # --- harmonizacao por classe canonica (30) ---
    # a fixture do INEAVAR usa categorias no singular; o crosswalk espera as
    # reais, no plural. Entao o 30 deve FALHAR aqui, com mensagem util.
    print("\n>>> harmonizacao com fixture (deve recusar categorias sinteticas)")
    import subprocess as sp
    r = sp.run([sys.executable, str(RAIZ / "codigo" / "30_harmoniza_classes.py"),
                "--ano", str(ANO)], capture_output=True, text=True)
    saida = (r.stdout + r.stderr)
    confere(r.returncode != 0 and "crosswalk" in saida,
            "30 recusa parquet sintetico com mensagem explicativa")

    print("\n" + "=" * 70)
    if falhas:
        print(f"{len(falhas)} FALHA(S):")
        for f in falhas:
            print(f"  - {f}")
        return 1
    print("TUDO PASSOU")
    return 0


if __name__ == "__main__":
    sys.exit(main())
