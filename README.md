# Base nacional de fatores operacionais e ambientais — transporte rodoviário de cargas (Brasil)

Versão em construção — **v0.1.0-dev**. Ainda não citável.

## O que é

Fatores por categoria de veículo de carga: quilometragem anual, consumo específico,
fator de carga, percurso vazio e emissões por tonelada-quilômetro. Construída por
integração de fontes públicas brasileiras, com incerteza quantificada e calibração
contra o total de diesel vendido (ANP).

## Três regras invioláveis

1. **`dados/00_brutos/` é somente-leitura.** Nunca edite um arquivo baixado. Toda
   correção vira linha de código. É isso que garante que rodar o pipeline do zero
   reproduz exatamente o resultado publicado.
2. **Todo arquivo baixado entra no `MANIFESTO.csv`** com URL, data de acesso e hash
   SHA-256, no mesmo dia do download. Se não está no manifesto, não existe.
3. **O crosswalk é dado, não código.** Fica em `crosswalk/*.csv`, editado à mão e
   versionado. É a peça que os revisores vão auditar — precisa ser legível sem
   abrir Python.

## Fluxo

```
00_brutos  ->  10_extraidos  ->  20_harmonizados  ->  30_publicados
 (original)     (1 parquet        (formato longo,      (CSV + DOI)
                 por fonte)        classe canônica)
```

## Como rodar

```bash
pip install pandas openpyxl pyarrow duckdb pdfplumber

python codigo/01_extrai_senatran.py dados/00_brutos/<arquivo>.xlsx 2024
python codigo/02_extrai_anp.py      dados/00_brutos/<arquivo>.csv  --ano 2024
python codigo/03_extrai_rntrc.py    dados/00_brutos/<arquivo>.csv  --inspecionar
python codigo/03_extrai_rntrc.py    dados/00_brutos/<arquivo>.csv  --ano 2024
```

`pyarrow` não é opcional — é o que escreve os Parquet. Sem ele os scripts
falham só na última linha, depois de todo o processamento.

Para testar o pipeline sem ter baixado nada ainda, há geradores de arquivos
sintéticos em `codigo/_teste/` que reproduzem as armadilhas de cada fonte
(encoding latin-1, decimal com vírgula, linhas de título antes do cabeçalho):

```bash
python codigo/_teste/gera_senatran_sintetico.py
python codigo/01_extrai_senatran.py codigo/_teste/senatran_sintetico.xlsx 2024

python codigo/_teste/gera_anp_sintetico.py
python codigo/02_extrai_anp.py codigo/_teste/anp_vendas_sintetico.csv --ano 2024

python codigo/_teste/gera_rntrc_sintetico.py
python codigo/03_extrai_rntrc.py codigo/_teste/rntrc_veiculos_sintetico.csv --ano 2024
```

## ANP — o que a extração faz e o que ela deliberadamente não faz

Extrai vendas de diesel por UF, mês e produto. **Não aloca** ao transporte de
carga e **não separa** fração fóssil de biogênica: ambas são decisões de
modelagem e ficam na etapa 30 (calibração), documentadas com incerteza.

Dois pontos que mudam o resultado se passarem despercebidos:

- **O produto `ÓLEO DIESEL MARÍTIMO` vem junto** e não pode ser alocado ao
  rodoviário. A extração o mantém (ele existe no arquivo); a alocação precisa
  descartá-lo explicitamente, não por esquecimento.
- **S-10 e S-500 têm teores de biodiesel e perfis de uso diferentes.** Mantenha
  os dois separados até o fim; agregá-los cedo destrói informação.

## RNTRC — inspecione antes de extrair

O esquema da ANTT não é documentado de forma estável, então `03_extrai_rntrc.py`
**não adivinha nomes de coluna**. Rode `--inspecionar` primeiro: ele imprime as
colunas reais com valores de exemplo e sugere o mapa. Salve o resultado em
`crosswalk/rntrc_colunas.csv` e só então extraia. O arquivo é lido em blocos de
200 mil linhas, então o tamanho não é problema.

**Viés que precisa constar na documentação da base:** a RNTRC só inclui
transportadores com situação ATIVO, o que corrige a inflação do SENATRAN — mas
deixa de fora a frota própria (carga privada, não remunerada). Nenhuma das duas
fontes é a frota real. A combinação delas, com a diferença declarada, é o que
se pode defender.

## Limitação estrutural do SENATRAN — leia antes de confiar em qualquer número

O SENATRAN **não informa PBT nem número de eixos**, e registra cavalo mecânico e
semirreboque como veículos separados. Duas consequências que definem todo o resto
do projeto:

- **`CAMINHÃO` é um balde único.** VUC, toco, truck e bitruck estão todos dentro.
  Separá-los exige uma distribuição externa (Sindipeças, ANFAVEA ou microdados
  RENAVAM). No crosswalk isso aparece como `tipo_mapeamento = PARCELA`, com a
  parcela ainda `PENDENTE` — ou seja, é **parâmetro estimado, não fato observado**.
- **Carreta, bitrem e rodotrem não existem no registro.** Só existem tratores e
  unidades rebocadas. Os conjuntos precisam ser inferidos por um modelo de
  acoplamento (razão semirreboques/cavalos por faixa, calibrada com o RNTRC).
  No crosswalk: `tipo_mapeamento = ACOPLAMENTO`.

Qualquer tabela publicada precisa carregar essa distinção na coluna `metodo`
(`medido` / `declarado` / `estimado` / `modelado`). Apagar essa diferença é o erro
mais comum na literatura brasileira do tema.

## Estrutura

```
dados/00_brutos/       original + MANIFESTO.csv (imutável)
dados/10_extraidos/    um parquet por fonte, ainda na taxonomia da fonte
dados/20_harmonizados/ formato longo na classe canônica
dados/30_publicados/   CSV final + datapackage.json
codigo/                scripts numerados, sem orquestrador
crosswalk/             tabelas de correspondência editadas à mão
docs/                  Quarto -> site estático
```

## Licenças previstas

Dados CC-BY-4.0 · código MIT.
