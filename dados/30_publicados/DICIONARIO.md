# Dicionário de dados — `fatores_por_classe_<ano>.csv`

Uma linha por classe canônica de veículo de carga. Âmbito nacional (`uf = BR`).

## Como ler esta tabela antes de usá-la

Três colunas dizem de onde cada número vem, e são a primeira coisa a olhar:

| Coluna | Valores | O que significa |
|---|---|---|
| `frota_metodo` | `eixos_senatran` | contado na distribuição de eixos do registro |
| | `modelado` | estimado pelo modelo de acoplamento; veja `frota_p05`/`frota_p95` |
| `intensidade_metodo` | `herdado_categoria_ineavar` | o `L/km` vem da categoria de emissão do INEAVAR, **não** da classe |
| `categoria_ineavar` | texto | qual categoria do inventário originou a intensidade |

**Consequência prática:** as quatro classes articuladas compartilham o mesmo
`l_por_km`, porque o INEAVAR publica um único valor para `CAMINHÕES PESADOS`.
Elas se diferenciam pela carga útil, não pelo consumo por quilômetro.

## Identificação

| Coluna | Tipo | Descrição |
|---|---|---|
| `ano_ref` | inteiro | ano de referência das intensidades (INEAVAR) |
| `ano_frota` | inteiro | ano de referência da frota (SENATRAN), pode diferir |
| `uf` | texto | `BR` — a v0.1 é só nacional |
| `id_classe` | texto | chave da classe canônica |
| `classe_nome` | texto | nome por extenso |
| `ordem` | inteiro | ordem de apresentação, do mais leve ao mais pesado |

## Características do veículo

| Coluna | Unidade | Descrição |
|---|---|---|
| `eixos` | contagem | eixos do conjunto completo |
| `pbt_cmt_t` | tonelada | PBT (rígidos) ou CMT (articulados), de referência |
| `carga_util_t` | tonelada | capacidade de carga de referência. **Ainda é valor de especialista** — veja `crosswalk/classes_canonicas.csv`, marcado `PENDENTE`. Divide todas as colunas `_tkm_capacidade` |

## Frota

| Coluna | Unidade | Descrição |
|---|---|---|
| `frota` | veículos | frota da classe. Para rígidos, contagem por eixos; para articulados, mediana do modelo de acoplamento |
| `frota_p05`, `frota_p95` | veículos | percentis, só para as classes modeladas |

**A frota é REGISTRADA, não circulante.** O SENATRAN não tem baixa obrigatória
efetiva. Comparando com o INEAVAR, o registro tem **1,97×** os caminhões que o
inventário considera em circulação. Para contagem de veículos em uso, prefira a
frota do INEAVAR.

## Intensidade de uso e consumo

| Coluna | Unidade | Descrição |
|---|---|---|
| `km_ano_veic` | km/ano | quilometragem anual por veículo, do INEAVAR (`km_ajustado ÷ Frota`) |
| `l_por_km` | L/km | consumo específico (`L_ajustado ÷ km_ajustado`) |
| `fracao_biogenica` | fração 0–1 | parcela renovável do combustível, isto é, o biodiesel misturado. Muda ano a ano com o mandato |

`ajustado` significa calibrado pelo INEAVAR contra o consumo observado de
combustível — a mesma reconciliação top-down que se faria contra a ANP.

## Emissões por quilômetro

| Coluna | Unidade |
|---|---|
| `gCO2e_por_km` | g CO₂-equivalente por km |
| `gCO2_fossil_por_km` | g CO₂ de origem fóssil por km |
| `gCH4_por_km` | g CH₄ por km |
| `gN2O_por_km` | g N₂O por km |

## Emissões por tonelada-quilômetro — leia antes de usar

| Coluna | Unidade |
|---|---|
| `l_por_tkm_capacidade` | L por tonelada-km, **na capacidade máxima** |
| `gCO2e_por_tkm_capacidade` | g CO₂e por tonelada-km, **na capacidade máxima** |
| `gCO2_fossil_por_tkm_capacidade` | idem, só fóssil |
| `gCH4_por_tkm_capacidade`, `gN2O_por_tkm_capacidade` | idem |

> **Estas colunas NÃO são fatores de emissão.**
>
> Elas dividem o consumo pela carga útil **máxima**. Um veículo real roda com
> fator de carga abaixo de 1 e parte do percurso vazio, então o valor efetivo é
> **maior** — tipicamente duas a três vezes.
>
> ```
> gCO2e/tkm efetivo ≈ valor_capacidade ÷ fator_carga ÷ (1 − percurso_vazio)
> ```
>
> Com fator de carga 0,60 e 25% de percurso vazio, a carreta de 5 eixos sai de
> 23,7 para 52,7 gCO₂e/tkm — faixa compatível com o que GLEC e DEFRA publicam
> para conjuntos pesados.
>
> **Fator de carga e percurso vazio não estão nesta base.** Não há fonte
> pública brasileira para nenhum dos dois; são o objeto da v0.2. Até lá, estas
> colunas servem para comparar classes entre si e ver a ordem de grandeza — não
> para calcular a pegada de uma operação.

## Classes canônicas

| `id_classe` | Eixos | PBT/CMT (t) | Carga útil (t) |
|---|---|---|---|
| `VUC` | 2 | 10,0 | 6,0 |
| `TOCO` | 2 | 16,0 | 10,0 |
| `TRUCK` | 3 | 23,0 | 14,0 |
| `BITRUCK` | 4 | 29,0 | 18,0 |
| `CARRETA5` | 5 | 41,5 | 27,0 |
| `CARRETA6` | 6 | 48,5 | 32,0 |
| `BITREM` | 7 | 57,0 | 37,0 |
| `RODOTREM` | 9 | 74,0 | 50,0 |

VUC e toco têm ambos 2 eixos, e o registro não informa PBT. A separação entre
os dois é feita pela proporção da frota do INEAVAR, que tem classe de peso.

## O que não está na v0.1

- fator de carga e percurso vazio
- desagregação por UF
- `L/km` diferenciado dentro de `CAMINHÕES PESADOS`
- combustíveis que não o diesel
- reboques e dollies (romeu-e-julieta) no modelo de acoplamento
