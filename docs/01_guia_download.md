# Guia de download das fontes — v0.1

Ordem deliberada: do mais fácil ao mais penoso, e da âncora para as dependentes.
Não pule para o PDF antes de fechar as três primeiras.

**Regra única:** todo arquivo baixado entra no `MANIFESTO.csv` **no mesmo dia**,
com URL exata, data de acesso e hash. Daqui a seis meses ninguém lembra de onde
veio o arquivo. Sem isso a base não é reprodutível — é um CSV com um DOI em cima.

---

## Links

Confirmados em outubro de 2026. Portais do governo reorganizam URLs com alguma
frequência — se um link quebrar, o caminho de navegação ao lado sobrevive.

| Fonte | Onde |
|---|---|
| **ANP** | [vendas-de-derivados-de-petroleo-e-biocombustiveis](https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/vendas-de-derivados-de-petroleo-e-biocombustiveis) |
| **ANTT / RNTRC** | [dados.antt.gov.br](https://dados.antt.gov.br/pl/tag/cargas) → dataset *RNTRC - Dados de Veículos* |
| **SENATRAN** | [frota-de-veiculos-2023](https://www.gov.br/transportes/pt-br/assuntos/transito/conteudo-Senatran/frota-de-veiculos-2023) — troque o ano no fim da URL |

---

## 1. ANP — vendas de diesel (a âncora)

**Onde:** gov.br/anp → Centrais de Conteúdo → Dados Abertos → *Vendas de
derivados de petróleo e biocombustíveis*.

**Baixe três arquivos.** A página tem vários conjuntos e eles servem a
propósitos diferentes:

| Arquivo | Para quê | Prioridade |
|---|---|---|
| `vendas-oleo-diesel-tipo-m3-2013-20XX.csv` | diesel **separado por tipo** (S-10 / S-500) | **principal** |
| `vendas-combustiveis-segmento-m3-2012-20XX.csv` | canal de venda — limita a alocação (ver abaixo) | alta |
| `vendas-combustiveis-m3-1990-20XX.csv` | série longa, todos os combustíveis | contexto |

Ignore os arquivos "por município" (são anuais e em litros) e o "por produtor".

**Dois layouts.** A ANP mistura os dois na mesma página, e o extrator detecta
qual é. Rode a inspeção antes de confiar no mapeamento automático:

```bash
python codigo/02_extrai_anp.py dados/00_brutos/<arquivo>.csv --inspecionar
python codigo/02_extrai_anp.py dados/00_brutos/<arquivo>.csv --ano 2024
```

A inspeção mostra as colunas reais, o layout detectado, e a lista de produtos
e segmentos encontrados.

### O que os arquivos reais têm (verificado out/2026)

Três armadilhas que quebrariam a extração e já estão tratadas:

- **Encoding é UTF-8 com BOM**, não latin-1. Isso importa porque latin-1
  *nunca falha* — ele decodifica qualquer byte. Lido como latin-1, o BOM vira
  `ï»¿ANO` e a coluna do ano deixa de ser reconhecida, sem erro nenhum. O
  extrator agora detecta o BOM e só cai para latin-1 em último caso.
- **O mês vem abreviado**: `JAN`, `FEV`, `MAR`. Nomes por extenso aparecem só
  como colunas nos arquivos de série histórica.
- **Os arquivos por município vêm em LITROS**, não m³ (asfalto, GLP e óleo
  combustível vêm em kg). Tratar litro como m³ multiplica o volume por mil — e
  mil vezes ainda *parece* um número, então o erro passa. Use
  `--unidade litros` nesses arquivos; se esquecer, a validação acusa.

Mais duas coisas para saber:

- Há **cinco tipos de diesel**, não dois: `S-10`, `S-500`, `S-1800`,
  `MARÍTIMO` e `(OUTROS )`. Marítimo e S-1800 **não são rodoviários** e
  precisam sair na alocação — explicitamente, não por esquecimento.
- Nos arquivos de layout largo há uma coluna `TOTAL`, que é a soma do ano, e
  `UNIDADE` ali é a unidade de medida, **não** unidade da federação.

Mantenha S-10 e S-500 separados até o fim. Teor de biodiesel e perfil de uso
diferem, e agregar cedo destrói informação que a série temporal vai precisar.

### Validação cruzada que vale fazer

Os arquivos "por tipo" e "por segmento" são visões independentes do mesmo
volume. Em 2024 os dois deram **67,4 bilhões de litros** — se divergirem em
algum ano, há problema em um deles.

O extrator grava cada visão num Parquet próprio
(`anp_vendas_diesel_tipo_2024.parquet`, `..._segmento_2024.parquet`),
justamente para que uma não sobrescreva a outra.

### O que `SEGMENTO` resolve — e o que não resolve

O arquivo "por segmento" tem uma coluna `SEGMENTO` com três valores: **posto
revendedor**, **TRR** (transportador-revendedor-retalhista) e **consumidor
final**.

Isso é **canal de venda, não setor de consumo**. Não existe uma linha
"transporte rodoviário de cargas" — seria bom demais.

Mas ainda assim aperta o parâmetro mais frágil da base. A alocação do diesel ao
rodoviário de carga (o `α` da calibração) era palpite puro. Com o segmento ela
vira palpite com limites:

- **posto revendedor** — venda no varejo, majoritariamente rodoviário
- **consumidor final** — venda direta a grandes consumidores: mineração,
  geração, agropecuária, e também grandes frotas de carga
- **TRR** — entrega a consumidores, mistura de agropecuária, construção e
  indústria

A fronteira não é limpa: transportadora grande compra como consumidor final.
Então o segmento **não identifica** `α`, mas define faixas defensáveis em vez
de um número do nada. O extrator preserva a dimensão para a etapa 30.

**Resultado real para o diesel em 2024:**

| Canal | Volume | Participação |
|---|---|---|
| Posto revendedor | 39,3 mi m³ | 58,3% |
| Consumidor final | 17,2 mi m³ | 25,4% |
| TRR | 11,0 mi m³ | 16,3% |

E a série é notavelmente estável: posto revendedor fica entre 56,7% e 59,7%
em todos os anos de 2012 a 2026. Consumidor final cai de 30,7% para 25,4% no
período, com TRR subindo de 12,6% para 16,3% — provável migração de canal, não
de uso.

Essa estabilidade é informação: um `α` que oscilasse muito ano a ano seria
suspeito. O limite inferior defensável para o rodoviário é o posto revendedor
sozinho (~58%), lembrando que mesmo ele inclui ônibus, utilitários leves e
veículos agrícolas que abastecem em posto.

**Validação:** o total nacional deve cair entre 50 e 70 bilhões de litros/ano.
Fora disso, o script avisa. Costuma significar arquivo de uma UF só, ano
incompleto, ou a coluna `TOTAL` entrando na soma.

---

## 2. ANTT — RNTRC (frota ativa) — **opcional na v0.1**

> **Se o portal estiver fora do ar, siga sem ele.** O pipeline roda só com o
> SENATRAN: o modelo de acoplamento usa as fontes que encontrar e informa
> quais usou. O que se perde está descrito ao fim desta seção — e precisa
> constar na documentação da versão publicada.

**Onde:** dados.antt.gov.br → dataset **RNTRC - Dados de Veículos**. Há também
um *RNTRC Histórico*, útil depois para a série temporal.

**Se a página não abrir**, tente nesta ordem:

1. A API do portal, direto no navegador:
   `dados.antt.gov.br/api/3/action/package_show?id=rntrc-veiculos`
   Devolve JSON com a lista de recursos e as URLs de download.
2. Os prefixos de idioma do portal — `dados.antt.gov.br/en/dataset/rntrc-veiculos`
   ou `/pl/dataset/rntrc-veiculos`. O portal é multilíngue e às vezes uma
   variante responde quando a padrão não responde.
3. A página de tags: `dados.antt.gov.br/pl/tag/cargas`, que lista os datasets
   de carga e leva aos recursos.
4. Os *Painéis de Dados Abertos do Transporte Rodoviário de Cargas*, na mesma
   página de tags — dão agregados mesmo quando o download do CSV falha.

**O que se perde sem a RNTRC:** a correção de frota ativa. O SENATRAN não tem
baixa obrigatória efetiva, então a frota registrada está inflada nas faixas
antigas. Sem a RNTRC, a contagem de veículos entra alta — e, como a calibração
fecha contra o total de diesel da ANP, uma frota inflada puxa o `L/km` médio
para baixo. O erro é invisível no agregado.

Isso **aumenta a importância do Sindipeças** (frota circulante e curvas de
sobrevivência), que passa a ser a única fonte de correção. Registre a ausência
no `CHANGELOG.md` da versão, não só aqui.

**Atenção:** o esquema de colunas não é documentado de forma estável, e não
consegui confirmá-lo. Por isso **inspecione antes de extrair**:

```bash
python codigo/03_extrai_rntrc.py dados/00_brutos/<arquivo>.csv --inspecionar
```

Isso imprime as colunas reais com valores de exemplo e sugere o mapa. Salve a
sugestão em `crosswalk/rntrc_colunas.csv`, confira à mão, e só então:

```bash
python codigo/03_extrai_rntrc.py dados/00_brutos/<arquivo>.csv --ano 2024
```

**O que olhar na saída:** o vocabulário de `tipo_rntrc`. Se as unidades
tratoras não aparecerem com "TRATOR" ou "CAVALO" no nome, e as rebocadas sem
"SEMI", ajuste `MARCA_TRATORA` / `MARCA_REBOCADA` no topo do script. O
diagnóstico avisa quando não reconhece.

**Viés a documentar:** a RNTRC inclui apenas transportadores ATIVOS, o que
corrige a inflação do SENATRAN — mas exclui frota própria (carga privada, não
remunerada). Nenhuma das duas fontes é a frota real.

---

## 3. SENATRAN — frota registrada

**Onde:** a página é anual, no padrão
`gov.br/transportes/pt-br/assuntos/transito/conteudo-Senatran/frota-de-veiculos-AAAA`.
Troque o ano no fim da URL. Publicação mensal dentro de cada página.

A página tem dois blocos. No primeiro, *Frota Nacional*, cada mês traz:

- **01 — Frota por UF e Tipo de Veículo** ← é este que você quer
- 02 — Frota por Município e Tipo

**Baixe o mês de dezembro** do ano de referência.

**Atenção ao formato:** a maioria dos meses vem em **`.xls`** (formato antigo
do Excel), não `.xlsx`. Isso exige a biblioteca `xlrd` — o `openpyxl` não lê
esse formato. Já está no `requirements.txt`; se faltar, o extrator diz o que
instalar.

```bash
python codigo/01_extrai_senatran.py dados/00_brutos/<arquivo>.xls 2024
```

Rode a inspeção primeiro, como nas outras fontes:

```bash
python codigo/01_extrai_senatran.py dados/00_brutos/<arquivo> --inspecionar
```

Se houver mais de uma aba, passe `--aba "Nome da aba"`; a mensagem de erro
lista as abas disponíveis.

### O que o arquivo real tem (verificado em Dez/2023)

Seis armadilhas, todas com o mesmo efeito se ignoradas — número errado **sem
mensagem de erro**:

- **O título da planilha contém "Unidades da Federação"**, igual ao rótulo da
  coluna. Quem procura o cabeçalho por texto cai no título. O extrator exige
  também que a linha tenha várias células preenchidas.
- **O rótulo da coluna tem quebra de linha dentro da célula.**
- **As UFs vêm por extenso, acentuadas e com espaços sobrando** — `"Pará "`,
  `"São Paulo "`. Nunca por sigla.
- **Linhas de agregado** (`Brasil`, `Norte`, `Nordeste`…) se misturam às de
  UF. Somá-las duplicaria a frota inteira.
- **Coluna `TOTAL`**, que é a soma da linha.
- **Uma segunda tabela abaixo**, com percentuais em vez de contagens.

**A verificação que fecha tudo:** o extrator soma as 27 UFs e compara com a
linha `Brasil` do próprio arquivo. Em Dez/2023 bateu exatamente —
119.227.657. Se divergir, algum agregado entrou ou alguma UF ficou de fora.

### Números reais de Dez/2023

| Tipo | Frota |
|---|---|
| Caminhão | 3.088.034 |
| Reboque | 2.258.798 |
| Utilitário | 1.580.714 |
| Semirreboque | 1.306.369 |
| Caminhão trator | 892.680 |

**Razão semirreboques/cavalos = 1,46.**

Note que `REBOQUE` (2,26 mi) é *maior* que `SEMI-REBOQUE` (1,31 mi). A
limitação declarada da v0.1 — deixar reboques e dollies fora do modelo de
acoplamento — pesa mais do que parecia. Muitos são agrícolas e leves, mas o
romeu-e-julieta usa reboque, e ele não está sendo contado.

### Baixe também: "08 — Tipo, espécie e eixos"

No segundo bloco da página, *Quantidade de Veículos por Município*, há um
arquivo chamado **08 - Tipo, espécie e eixos**.

Se ele trouxer contagem de eixos por tipo de veículo, resolve — total ou
parcialmente — o problema que hoje depende do Sindipeças em PDF: separar
`CAMINHÃO` em VUC, toco (2 eixos), truck (3) e bitruck (4). Também ajuda a
restringir os priors do acoplamento.

Vale baixar e inspecionar **antes** de encarar a extração de PDF. É o atalho
mais promissor do projeto inteiro, e é barato verificar.

O arquivo **01 — Ano de fabricação e modelo**, do mesmo bloco, é o insumo da
fase PROCONVE mais adiante. Baixe junto.

---

## 4. Fechar a etapa 20

Com SENATRAN e RNTRC extraídos:

```bash
python codigo/20_modelo_acoplamento.py --ano 2024
```

**O momento da verdade:** se a taxa de aceitação vier perto de zero, as faixas
em `crosswalk/acoplamento_priors.csv` não reproduzem a razão rebocadas/cavalo
real. Isso é achado, não bug — o script informa qual intervalo de razão as
faixas produzem. Ajuste os priors e **documente a mudança no commit**.

---

## 5. MMA / INEAVAR — km/ano, L/km e fatores de emissão

**Esta fonte substitui a maior parte do que iria para a extração de PDF.**

**Onde:** [Portal de Dados Abertos do MMA](https://dados.mma.gov.br/dataset/emissoes-atmosfericas-veiculos-automotores)
— *Inventário Nacional de Emissões Atmosféricas por Veículos Automotores
Rodoviários 2025 (ano-base 2024)*.

**O que baixar**, em CSV:

| Arquivo | Para quê |
|---|---|
| `frota_e_quilometragem.csv` | frota **circulante**, `km_ajustado`, `L_ajustado`, por categoria, fase PROCONVE, ano-modelo e idade |
| `consumo_emissoes.csv` | consumo por combustível, fração fóssil e renovável, `gCH4/km`, `gN2O/km`, CO₂ por origem |
| `dicionario-de-dados-ineavar.csv` | dicionário das colunas |

```bash
python codigo/05_extrai_ineavar.py dados/00_brutos/<arquivo>.csv --inspecionar
python codigo/05_extrai_ineavar.py dados/00_brutos/<arquivo>.csv --ano 2024
```

### O que isso resolve

- **km/ano por categoria** — não havia fonte pública fácil
- **L/km** — sai de `L_ajustado ÷ km_ajustado`
- **Fração biogênica** — o biodiesel já vem separado em
  `combustivel_fracao_fossil` e `combustivel_fracao_renovavel`, o que dispensa
  reconstruir o mandato ano a ano
- **CH₄ e N₂O** — fatores por km, por categoria e fase PROCONVE
- **Frota circulante**, não registrada — ataca o problema que a RNTRC resolveria

O sufixo `ajustado` significa calibrado contra o consumo observado de
combustível: é a mesma reconciliação top-down que esta base faria contra a ANP.
Usar o valor ajustado é herdar essa calibração; `preliminar` é o que vem antes
dela. O extrator prefere o ajustado e registra qual usou.

### O que isso NÃO resolve — e é onde a base contribui

- **A categoria do INEAVAR é de emissões** (leve, médio, semipesado, pesado),
  não de logística. `CAMINHÃO PESADO` empilha bitruck, carreta, bitrem e
  rodotrem num balde só. A desagregação por eixos que construímos é o que
  separa isso — ver `crosswalk/ineavar_para_canonica.csv`.
- **Publica g/km, não g/tkm.** Fator de carga e percurso vazio continuam
  ausentes, e não há fonte pública para eles no Brasil.

Essas duas lacunas são, agora, a contribuição da base: o INEAVAR dá o
numerador; o que falta é o denominador em toneladas-quilômetro e o mapeamento
para classes que fazem sentido em logística.

## Depois: as fontes em PDF — agora opcionais

Sindipeças (curvas de sobrevivência) e CNT (quilometragem) continuam úteis para
validação cruzada, mas deixaram de ser caminho crítico. A CETESB publica só o
estado de São Paulo e, desde 2022, retirou as tabelas dos apêndices do
relatório. Com o INEAVAR disponível, em âmbito nacional e em CSV, a extração de
PDF virou verificação, não construção.

---

## Registrar no manifesto

Para cada arquivo, uma linha em `dados/00_brutos/MANIFESTO.csv`:

| campo | o que preencher |
|---|---|
| `id_fonte` | o identificador já previsto na linha-modelo |
| `arquivo` | nome exato do arquivo baixado |
| `url_origem` | **a URL de onde você clicou**, não a página inicial do órgão |
| `data_acesso` | hoje, em AAAA-MM-DD |
| `sha256` | o hash (comando abaixo) |
| `tipo_url` | `arquivo` se a URL baixa o arquivo direto; `pagina` se é a página de onde você clicou |
| `observacao` | qualquer coisa que o você-do-futuro vai esquecer |

**Sobre `tipo_url`:** o ideal é a URL que baixa o arquivo direto — é ela que
permite a outra pessoa repetir o download sem navegar. Quando só se tem a
página (ANP e SENATRAN entregam o arquivo por JavaScript ou por caminho que
muda), registre a página e marque `pagina`. O hash continua garantindo que o
arquivo é o mesmo; o que se perde é poder baixá-lo por script.

Hash no Windows:

```
certutil -hashfile dados\00_brutos\<arquivo> SHA256
```

No Mac ou Linux: `shasum -a 256 dados/00_brutos/<arquivo>`

A função `registra()` do notebook faz tudo isso de uma vez, se preferir.
