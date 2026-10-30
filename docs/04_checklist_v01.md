# Checklist de publicação da v0.1

Tudo que segue já está no repositório, exceto onde diz **você**.

## 1. Preencher — o que só você tem

| Arquivo | Campo | Onde achar |
|---|---|---|
| — | — | **tudo preenchido**: ORCID, URL do repositório, data do release e horizonte de manutenção |

O manifesto já está completo para os oito arquivos usados: hash SHA-256, URL e
data de acesso (30/10/2026). Duas observações:

- Para a ANP e o SENATRAN, a URL registrada é a **página** de onde o arquivo
  foi baixado, não o link direto — os dois portais entregam o arquivo por
  caminho que muda. A coluna `tipo_url` marca isso. O hash continua garantindo
  que é o mesmo arquivo; o que se perde é poder baixar por script.
- O `dicionario-de-dados-ineavar.csv` está no manifesto **sem hash e é
  opcional**. Ele é só documentação das colunas do INEAVAR; o mapeamento do
  extrator 05 já foi validado contra os arquivos reais, então a base não
  depende dele. Se quiser registrá-lo, o link direto está na coluna
  `url_origem` da linha `mma_ineavar_dicionario`.
- Todos os nove arquivos baixados têm **URL direta** (`tipo_url = arquivo`),
  hash SHA-256 e data de acesso. A proveniência está completa: outra pessoa
  consegue repetir o download por script e conferir que pegou o mesmo arquivo.

## 2. Conferir

```bash
python codigo/_teste/testa_pipeline.py        # 37 verificações
head -3 dados/30_publicados/fatores_por_classe_2024.csv
```

E abra o `dados/30_publicados/DICIONARIO.md`: ele é o que um usuário lê antes
de usar os números, e é onde os avisos sobre `_tkm_capacidade` vivem.

## 3. Congelar o ambiente

```bash
pip freeze > requirements.lock.txt
```

É o que permite reproduzir **esta versão** daqui a cinco anos.

## 4. Commit e release

Passo a passo em `docs/03_primeiro_commit.md`. Resumo:

```bash
git init && git add -A
git status                # PARE e leia: nenhum dado bruto, nenhum .venv
git commit -m "v0.1.0: fatores por classe canônica, ano-base 2024"
git tag v0.1.0
git push origin main --tags
```

Depois, no GitHub: Releases → Draft a new release → tag `v0.1.0` → o
`CHANGELOG.md` como descrição → publicar.

O repositório precisa estar **público** e o Zenodo ligado **antes** do release:
ele não captura releases anteriores à ativação.

## 5. Depois do DOI

- preencher o DOI de conceito em `CITATION.cff`, e commitar
- registrar a base no **re3data** e no **FAIRsharing** — é assim que ela
  aparece para quem procura dataset de frete brasileiro sem conhecer você
- considerar um *data paper* em *Data in Brief* ou *Scientific Data*: não
  republica os dados, só descreve a base e aponta para o DOI. Dá um registro
  indexado em Scopus/WoS, o que ajuda na hora de negociar microdados com CNT
  ou CETESB

## O que dizer sobre a v0.1 quando apresentá-la

A alegação defensável, nesta ordem:

1. O inventário nacional publica quilometragem, consumo e emissões em
   **categorias de emissão** e **por quilômetro**.
2. Estudos de logística precisam de **classes de veículo** e de **tonelada-
   quilômetro**.
3. Esta base faz a ponte: desagrega `CAMINHÕES PESADOS` em carreta, bitrem e
   rodotrem usando a contagem de eixos e um modelo de acoplamento, publica a
   incerteza disso, e declara o método de cada número.
4. O que ainda falta — fator de carga e percurso vazio — está medido em
   tamanho, não apenas mencionado: é a diferença entre 23,7 e ~52,7 gCO₂e/tkm
   numa carreta de 5 eixos.

O item 4 é o que transforma uma limitação em agenda de pesquisa.
