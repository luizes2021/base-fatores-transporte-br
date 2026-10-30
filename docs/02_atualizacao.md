# Procedimento de atualização anual

Este documento existe para que a atualização seja uma tarefa de uma semana que
**outra pessoa** consegue executar lendo daqui — não conhecimento que só o
autor original tem. Se você está lendo isto e não construiu a base, é para
você mesmo.

---

## Política de versões

Dois DOIs vêm do Zenodo, e eles servem a propósitos diferentes:

| Onde usar | Qual DOI | Por quê |
|---|---|---|
| Artigo que usou os dados | o **da versão** (`v0.2`) | o revisor precisa dos números exatos |
| README, site, divulgação | o **de conceito** | quem chega novo deve achar o atual |

Numeração:

| Mudança | Versão |
|---|---|
| Ano de referência novo | `v0.2` → `v0.3` |
| Correção sem mudar metodologia | `v0.2` → `v0.2.1` |
| Priors de acoplamento substituídos por dado real | `v1.0` |
| Classe renomeada, coluna removida, unidade trocada | sobe o primeiro número |

**Qualquer mudança que quebre quem já usa a base é major.** Renomear
`CARRETA5` ou trocar `gCO2e/tkm` por `kgCO2e/tkm` quebra o código de terceiros
em silêncio. Isso é pior que um erro ruidoso.

---

## Política de revisão retroativa

**As fontes revisam o passado.** A ANP corrige meses anteriores; o SENATRAN
republica. Extrair "2024" em 2027 não dá o mesmo resultado que hoje.

A política desta base: **reextrair todos os anos a cada release** e publicar
junto um `revisoes.csv` com o que mudou em relação à versão anterior.

A alternativa — congelar cada ano na primeira publicação — deixa a base
internamente inconsistente, misturando dado revisado com não revisado. Quem
precisa do número antigo tem o DOI da versão anterior, que nunca muda.

O que torna isso auditável é o `sha256` no `MANIFESTO.csv`: ele distingue "o
arquivo da ANP como estava em 2026" de "como está em 2027". Sem o hash não há
como provar o que mudou.

---

## Checklist da atualização

### 1. Ambiente

```bash
cd base-fatores-br
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Mac/Linux
python codigo/_teste/testa_pipeline.py
```

Se o teste falhar **antes** de você tocar em qualquer dado, o problema é
mudança de API nas bibliotecas, não nos dados. Resolva isso primeiro — é mais
fácil depurar com arquivos sintéticos do que com os reais.

### 2. Baixar

Siga `docs/01_guia_download.md`. Registre **cada** arquivo no `MANIFESTO.csv`
no mesmo dia, com URL exata, data de acesso e hash.

Não apague os arquivos do ano anterior. `00_brutos/` é acumulativo — é o que
permite reconstruir qualquer versão passada.

### 3. Extrair e modelar

```bash
python codigo/01_extrai_senatran.py dados/00_brutos/<arquivo> <ANO>
python codigo/02_extrai_anp.py      dados/00_brutos/<arquivo> --ano <ANO>
python codigo/03_extrai_rntrc.py    dados/00_brutos/<arquivo> --inspecionar
python codigo/03_extrai_rntrc.py    dados/00_brutos/<arquivo> --ano <ANO>
python codigo/20_modelo_acoplamento.py --ano <ANO>
```

**Espere que algo quebre aqui.** Layout de planilha muda, coluna é renomeada,
produto novo aparece. Os extratores falham alto de propósito, em vez de
produzir número errado em silêncio. Cada correção vira uma linha de código ou
uma linha de crosswalk — **nunca** uma edição manual em `00_brutos/`.

### 4. Comparar com a versão anterior

Antes de publicar, gere o diff:

| Verificar | Sinal de alerta |
|---|---|
| Total de diesel vs. ano anterior | variação acima de 15% sem explicação |
| Frota por classe | salto que não corresponde a vendas de veículos novos |
| Taxa de aceitação do acoplamento | caiu muito: os priors não servem mais |
| Anos anteriores reextraídos | qualquer mudança vai para `revisoes.csv` |

Mudança grande não é necessariamente erro — mas precisa de uma frase de
explicação no `CHANGELOG.md`. Se você não consegue explicar, não publique.

### 5. Documentar

- `CHANGELOG.md`: o que mudou, por quê, e o que quebra para quem usa
- `revisoes.csv`: números de anos anteriores que mudaram, e a causa
- `README.md`: ano de referência mais recente, versão, DOI de conceito
- Se os priors mudaram, atualize a coluna `fonte_prior` no crosswalk

### 6. Congelar o ambiente

```bash
pip freeze > requirements.lock.txt
```

Esse arquivo é o que permite reproduzir **esta versão** daqui a cinco anos.
Vai no release.

### 7. Publicar

```bash
git add -A
git commit -m "v0.2: ano de referência 2025"
git tag v0.2.0
git push origin main --tags
```

Depois, no GitHub: Releases → Draft a new release → escolher a tag → publicar.
O Zenodo gera o DOI da versão automaticamente, desde que a integração esteja
ligada (uma vez só, em Settings → GitHub no Zenodo).

### 8. Avisar

Quem cita a base não descobre sozinho que há versão nova. Um aviso curto na
lista do grupo de pesquisa e nas redes basta. Se houver usuários
institucionais, um e-mail.

---

## Quando o pipeline quebrar e você tiver pouco tempo

Prioridade, em ordem:

1. **Publicar com um ano a menos é melhor que não publicar.** Marque o ano
   problemático como pendente no CHANGELOG e siga.
2. **Nunca publique número que você não consegue explicar.** Base errada com
   DOI é pior que base desatualizada.
3. **Se os priors não fecham, não force.** Alargue as faixas, documente que
   alargou, e registre a razão observada. A incerteza maior é informação
   honesta; o ponto falso não é.

---

## Horizonte de manutenção

Declare um, no README, e seja honesto. Algo como:

> Mantida com revisão anual até 2030. Depois disso, o repositório permanece
> arquivado e citável no Zenodo, mas sem garantia de atualização.

Isso é mais útil para quem depende da base do que manutenção presumida que
silenciosamente para. Se depois você quiser estender, basta mudar a frase.

**Sucessão:** se a atualização virar tarefa de um mestrando, ela precisa estar
no plano de trabalho dele com prazo — não como favor informal. Estudantes se
formam; o procedimento escrito é o que sobrevive à troca.
