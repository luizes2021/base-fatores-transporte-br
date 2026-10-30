# Base nacional de fatores operacionais e ambientais — transporte rodoviário de cargas (Brasil)

Fatores por **classe canônica de veículo de carga**: frota, quilometragem
anual, consumo específico e emissões. Construída por integração de fontes
públicas brasileiras, com o método de cada número declarado linha a linha.

**Versão 0.1.0** · dados CC-BY-4.0 · código MIT

> A v0.1 cobre frota, `km/ano`, `L/km` e emissões **por quilômetro**. Fator de
> carga e percurso vazio **não estão incluídos** — não há fonte pública
> brasileira para nenhum dos dois. As colunas por tonelada-quilômetro usam a
> capacidade máxima e são **piso teórico, não fator de emissão**. Ver
> `dados/30_publicados/DICIONARIO.md`.

## O dado

`dados/30_publicados/fatores_por_classe_2024.csv` — oito classes, âmbito
nacional. Ano-base 2024 para intensidades, Dez/2023 para a frota.

| Classe | Eixos | Frota | km/ano | L/km | Carga t | gCO₂e/tkm cap. |
|---|---|---|---|---|---|---|
| VUC / leve | 2 | 705.813 | 50.827 | 0,165 | 6 | 62,8 |
| Toco | 2 | 315.980 | 74.916 | 0,176 | 10 | 40,0 |
| Truck | 3 | 902.723 | 93.151 | 0,283 | 14 | 46,0 |
| Bitruck | 4 | 88.026 | 96.056 | 0,282 | 18 | 35,7 |
| Carreta 5 eixos | 5 | 160.966 | 98.465 | 0,281 | 27 | 23,7 |
| Carreta 6 eixos | 6 | 326.750 | 98.465 | 0,281 | 32 | 20,0 |
| Bitrem | 7 | 42.094 | 98.465 | 0,281 | 37 | 17,3 |
| Rodotrem | 9 | 84.314 | 98.465 | 0,281 | 50 | 12,8 |

O `L/km` é idêntico nas quatro articuladas porque o inventário nacional
publica um único valor para `CAMINHÕES PESADOS`. Elas se diferenciam pela
carga útil — e é por isso que o `gCO₂e/tkm` varia quase cinco vezes entre a
classe mais leve e a mais pesada.

## O que a base acrescenta às fontes de origem

O inventário do MMA já publica quilometragem, consumo e emissões — mas em
**categorias de emissão** (leve, médio, semipesado, pesado), e **por
quilômetro**. Esta base:

- **separa `CAMINHÕES PESADOS`** em bitruck, carreta de 5 e 6 eixos, bitrem e
  rodotrem, usando a contagem de eixos do SENATRAN e um modelo de acoplamento
  para os conjuntos articulados, que o registro veicular não contém;
- **publica a incerteza** das classes estimadas como p05/p50/p95, não como
  valor pontual;
- **declara o método de cada número** nas colunas `frota_metodo` e
  `intensidade_metodo`, para que medido e modelado não se confundam;
- **reconcilia as fontes entre si** e publica as verificações (abaixo).

## Verificações que a construção faz

| O quê | Resultado |
|---|---|
| Soma das 27 UFs × linha `Brasil` do SENATRAN | diferença **zero** (119.227.657) |
| Os dois arquivos do SENATRAN entre si | **3 veículos** de diferença em 119 milhões |
| ANP "por tipo" × ANP "por segmento" | mesmo total (67,4 bi L em 2024) |
| Consumo rodoviário do INEAVAR ÷ vendas ANP | **α = 0,795**; só caminhões, 0,616 |
| Canal "posto revendedor" da ANP, método independente | **0,583** — mesma ordem |
| Frota registrada (SENATRAN) ÷ circulante (INEAVAR) | **1,97×** |

A última linha quantifica a inflação do registro, antes apenas suposta.

## Fontes

| Fonte | O que fornece |
|---|---|
| [SENATRAN](https://www.gov.br/transportes/pt-br/assuntos/transito/conteudo-Senatran) | frota por tipo; contagem de eixos |
| [ANP](https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/vendas-de-derivados-de-petroleo-e-biocombustiveis) | vendas de diesel por tipo e canal |
| [MMA / INEAVAR](https://dados.mma.gov.br/dataset/emissoes-atmosfericas-veiculos-automotores) | km/ano, consumo, emissões, frota circulante |

`dados/00_brutos/MANIFESTO.csv` registra URL, data de acesso e hash SHA-256 de
cada arquivo usado — é o que permite reproduzir a extração a partir dos mesmos
insumos.

## Reproduzir

```bash
pip install -r requirements.txt     # ou: conda env create -f environment.yml

python codigo/01_extrai_senatran.py       dados/00_brutos/<frota>.xlsx 2023 --mes 12
python codigo/02_extrai_anp.py            dados/00_brutos/<diesel>.csv --ano 2024
python codigo/04_extrai_senatran_eixos.py dados/00_brutos/<eixos>.xlsx 2023 --mes 12
python codigo/05_extrai_ineavar.py        dados/00_brutos/consumo_emissoes.csv --ano 2024
python codigo/21_acoplamento_eixos.py     --ano 2023 --mes 12
python codigo/30_harmoniza_classes.py     --ano 2024 --ano-frota 2023 --mes-frota 12
```

Todo extrator tem `--inspecionar`, que mostra as colunas reais do arquivo antes
de confiar no mapeamento. Use-o sempre que uma fonte publicar uma edição nova.

Teste do pipeline, sem precisar de dado nenhum:

```bash
python codigo/_teste/testa_pipeline.py    # 37 verificações
```

As fixtures reproduzem as armadilhas dos arquivos reais — título que imita o
cabeçalho, UFs acentuadas, formato numérico americano, `eixos = 0` significando
"não informado". Uma GitHub Action roda isso no dia 1 de cada mês, para que
mudanças de API em pandas ou pyarrow apareçam cedo.

## Estrutura

```
dados/00_brutos/        originais + MANIFESTO.csv (imutável, fora do Git)
dados/10_extraidos/     um parquet por fonte
dados/20_harmonizados/  modelo de acoplamento
dados/30_publicados/    CSV + dicionário + datapackage.json   ← o produto
codigo/                 scripts numerados, sem orquestrador
crosswalk/              correspondências editadas à mão, versionadas
docs/                   guia de download, atualização, primeiro commit
```

O `crosswalk/` é dado, não código: cada alteração ali é uma decisão
metodológica, e o histórico do Git é o que a torna auditável.

## Limitações

Estão listadas por extenso no `CHANGELOG.md`. As quatro que mais afetam o uso:

1. **Fator de carga e percurso vazio ausentes** — as colunas `_tkm_capacidade`
   são piso teórico, não fator de emissão.
2. **Frota registrada, não circulante** — inflada em ~1,97× frente ao INEAVAR.
3. **Eixos não informados** em 31% dos caminhões; supor que seguem a
   distribuição dos informados é hipótese, não dado.
4. **`L/km` não diferencia as classes articuladas** — limite da fonte.

## Atualização e horizonte de manutenção

**Revisão anual**, ancorada em quando a ANP fecha o ano — na prática, no
primeiro semestre. O procedimento está em `docs/02_atualizacao.md`, escrito
para outra pessoa executar.

Cada versão recebe um DOI próprio no Zenodo e permanece arquivada e citável
mesmo que a manutenção seja descontinuada. Quem precisa de números estáveis
cita o DOI da versão; quem quer o mais recente cita o DOI de conceito.

## Citar

Ver `CITATION.cff`, ou o botão "Cite this repository" no GitHub.
