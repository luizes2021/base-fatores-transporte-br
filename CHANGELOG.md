# Changelog

Versionamento semântico, com a convenção de `docs/02_atualizacao.md`:
ano de referência novo sobe a versão menor; correção sem mudar metodologia sobe
a de correção; mudança que quebra quem já usa sobe a maior.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

---

## [0.1.0] — 2026-10-30

Primeira versão publicável. O DOI é gerado pelo Zenodo no release do GitHub;
preencha-o aqui e em `CITATION.cff` depois.

**Produto:** `dados/30_publicados/fatores_por_classe_2024.csv` — oito classes
canônicas, âmbito nacional, com dicionário de dados e `datapackage.json`.

### Escopo da v0.1

Publica, por classe canônica de veículo de carga: **frota, km/ano, L/km,
gCO₂e/km, gCH₄/km, gN₂O/km e fração biogênica**, mais os mesmos fatores
divididos pela **carga útil de capacidade**.

Fator de carga e percurso vazio ficam para a v0.2 — não há fonte pública
brasileira para nenhum dos dois. Por isso as colunas `_capacidade` são piso
teórico, não fator de emissão, e estão marcadas como tal.

### Conteúdo publicado

Por classe canônica: frota, km/ano por veículo, L/km, fração biogênica,
gCO₂e/km, gCO₂ fóssil/km, gCH₄/km, gN₂O/km, e os mesmos fatores divididos pela
carga útil de capacidade. Oito classes: VUC, toco, truck, bitruck, carreta de
5 e de 6 eixos, bitrem e rodotrem.

### Adicionado

- Pipeline de quatro camadas (bruto → extraído → harmonizado → publicado), com
  scripts numerados e sem orquestrador.
- Extratores: SENATRAN frota por UF e tipo (01), ANP vendas de derivados (02),
  ANTT RNTRC (03), SENATRAN tipo/espécie/eixos (04), MMA/INEAVAR (05).
- Modelo de acoplamento por amostragem de rejeição (20), que publica
  distribuições p05/p50/p95 em vez de valores pontuais.
- Modelo de acoplamento v2 por restrições de eixo (21), com solução fechada:
  fixado o excedente de semirreboques, o total de conjuntos pesados fica
  determinado. O teto desse excedente passa a sair do dado (s ≤ 0,645 em
  Dez/2023), não de faixa arbitrada. O v1 fica no repositório como comparação
  metodológica — a diferença entre os dois mostra o quanto a escolha de
  restrição altera o resultado.
- Harmonização por classe canônica (30), que junta as três fontes e publica
  `dados/30_publicados/fatores_por_classe_<ano>.csv`. Cada linha declara o
  método de cada número: `frota_metodo` (medido por eixos ou modelado) e
  `intensidade_metodo` (herdado da categoria do INEAVAR).
- Manifesto das fontes com URL, data de acesso e hash SHA-256 por arquivo.
- Tabelas de correspondência como CSV versionado, não lógica embutida no
  código.
- Suíte de 36 verificações sobre arquivos sintéticos que reproduzem as
  armadilhas dos arquivos reais, e GitHub Action mensal.

### Validações que o pipeline faz

- A soma das 27 UFs bate com a linha `Brasil` do próprio arquivo do SENATRAN
  (diferença zero em Dez/2023).
- Os dois arquivos do SENATRAN reconciliam entre si: 119.227.654 contra
  119.227.657, 3 veículos de diferença em 119 milhões.
- Os arquivos da ANP "por tipo" e "por segmento" dão o mesmo total nacional
  de diesel (67,4 bilhões de litros em 2024).
- O consumo rodoviário do INEAVAR fecha contra as vendas da ANP: 53,6 contra
  67,4 bilhões de litros em 2024, ou seja α = 0,795 para todo o rodoviário e
  0,616 só para caminhões. O canal "posto revendedor" da ANP, estimado por
  método independente, dá 0,583 — mesma ordem, duas rotas diferentes.
- A frota registrada do SENATRAN tem **1,97×** os caminhões que o INEAVAR
  considera circulantes (3.980.714 contra 2.025.606). A inflação do registro,
  antes suposta, está medida.

### Fontes que mudaram o plano durante a construção

- **SENATRAN "Tipo, espécie e eixos"** traz contagem de eixos, o que resolve a
  separação dos caminhões rígidos (2, 3 e 4 eixos) sem recorrer ao Sindipeças
  em PDF, e dá ao acoplamento uma restrição por tamanho de semirreboque.
- **MMA/INEAVAR** (inventário nacional, ano-base 2024, em CSV) publica
  `km_ajustado`, `L_ajustado`, fração fóssil/biogênica já separada, fatores de
  CH₄ e N₂O, e frota **circulante**. Preenche a lacuna de intensidade que não
  tinha fonte pública fácil, e torna a extração de PDF verificação em vez de
  construção.

Com isso, a contribuição da base fica mais nítida: o INEAVAR dá o numerador
(emissões por km, em categorias de emissão); o que falta — e o que esta base
acrescenta — é o denominador em toneladas-quilômetro e o mapeamento para
classes que fazem sentido em logística.

### O que a tabela mostra

A intensidade por km quase não varia entre as classes pesadas — todas herdam
o valor de `CAMINHÕES PESADOS` do INEAVAR, porque a fonte não as distingue.
Mas a intensidade **por tonelada-quilômetro** varia quase 5×, de 62,8
gCO₂e/tkm no VUC a 12,8 no rodotrem, porque a carga útil vai de 6 t a 50 t.

É isso que justifica separar as classes: o `L/km` não as distingue, o `L/tkm`
sim — e é o `tkm` que estudos de roteirização verde e de descarbonização usam.

Aplicando fator de carga e percurso vazio plausíveis ao valor de capacidade,
uma carreta de 5 eixos sai de 23,7 para 52,7 gCO₂e/tkm (carga 0,60, vazio
25%), que é a faixa que GLEC e DEFRA publicam para conjuntos pesados. A
consistência é um bom sinal para a cadeia toda — e mostra que a lacuna da
v0.2 é o que separa um piso teórico de um fator utilizável.

### Limitações declaradas

- **Eixos não informados.** `EIXOS = 0` significa "não informado", não "zero
  eixos": 30,9% dos caminhões, 19,9% dos cavalos e 17,7% dos semirreboques em
  Dez/2023. Supor que os não informados seguem a distribuição dos informados é
  hipótese, não dado — e provavelmente falsa, já que registros antigos devem
  concentrar a omissão.
- **Frota registrada, não circulante.** O SENATRAN não tem baixa obrigatória
  efetiva, então a frota está inflada nas faixas antigas. A correção dependeria
  da RNTRC (frota ativa) ou do Sindipeças (curvas de sobrevivência), nenhuma
  das duas incorporada ainda.
- **Reboques e dollies fora do acoplamento.** O tipo `REBOQUE` (2,26 milhões,
  mais que os semirreboques) também é puxado por caminhão rígido, e separar
  isso exige dado que não temos. O romeu-e-julieta não está sendo contado.
- **Priors de acoplamento ainda são faixas de especialista.** Marcados como
  `SUBSTITUIR` em `crosswalk/acoplamento_priors.csv`. É o elo mais frágil.
- **Alocação do diesel ao rodoviário.** O `SEGMENTO` da ANP é canal de venda
  (posto, TRR, consumidor final), não setor de consumo. Limita a faixa, não
  identifica o parâmetro.
- **Fator de carga e percurso vazio ausentes.** Não há fonte pública brasileira
  para nenhum dos dois, e são justamente as variáveis que dominam a dispersão
  do denominador em tkm. É a lacuna que dados primários de telemetria
  preencheriam.
- **A desagregação de `CAMINHÕES PESADOS` do INEAVAR ainda é parcela
  estimada.** Essa categoria empilha bitruck, carreta, bitrem e rodotrem num
  balde só, e separá-la depende da distribuição de eixos do SENATRAN. Marcado
  `PENDENTE` em `crosswalk/ineavar_para_canonica.csv`.

### Bugs corrigidos durante a construção

Registrados porque os três produziriam número errado **sem mensagem de erro**:

- Formato numérico: o INEAVAR usa o padrão **americano** (`" 94,553,724.47 "`),
  com vírgula de milhar e ponto decimal. Tratá-lo como brasileiro daria cem
  vezes o valor — um número ainda plausível, que passaria despercebido. O
  parser decide o formato pela coluna inteira, porque decidir valor a valor
  erra em números sem parte decimal como `26,714,473`.
- Encoding: os arquivos da ANP são UTF-8 com BOM. Tentar latin-1 primeiro não
  falha — latin-1 decodifica qualquer byte — e o BOM vira `ï»¿ANO`, quebrando
  o reconhecimento da coluna do ano em silêncio.
- Tratores agrícolas: `TRATOR ESTEIRA` e `TRATOR RODAS` entravam na contagem
  de cavalos mecânicos, inflando-a em 4% e reduzindo a estimativa de bitrens e
  rodotrens.
- Unidade: os arquivos anuais por município da ANP vêm em litros, não m³.

---

## Modelo para as próximas entradas

```
## [0.2.0] — AAAA-MM-DD

DOI: 10.5281/zenodo.XXXXXXX

### Conteúdo publicado

Por classe canônica: frota, km/ano por veículo, L/km, fração biogênica,
gCO₂e/km, gCO₂ fóssil/km, gCH₄/km, gN₂O/km, e os mesmos fatores divididos pela
carga útil de capacidade. Oito classes: VUC, toco, truck, bitruck, carreta de
5 e de 6 eixos, bitrem e rodotrem.

### Adicionado
### Alterado
### Corrigido
### Revisões retroativas
Números de anos anteriores que mudaram e por quê. Detalhe em `revisoes.csv`.
### Quebra de compatibilidade
O que muda para quem já usa a versão anterior.
```
