# Primeiro commit e ligação com o Zenodo

Meia hora, uma vez só. Depois disso a base passa a existir fora da sua
máquina e cada versão ganha um DOI sozinha.

---

## 1. Antes de começar: três campos a preencher

| Arquivo | O que falta |
|---|---|
| `CITATION.cff` | seu ORCID, a URL do repositório, co-autores se houver |
| `.zenodo.json` | nada obrigatório agora; confira a afiliação |
| `README.md` | o horizonte de manutenção (ver `docs/02_atualizacao.md`) |

Sobre e-mail: `CITATION.cff` aceita um, mas é opcional. Um e-mail pessoal num
repositório público é escolha sua, não requisito — o ORCID já identifica você
de forma estável.

---

## 2. Git na sua máquina

Confira se já está instalado:

```
git --version
```

Se não estiver, instale o Git para Windows (git-scm.com) com as opções padrão.

Identifique-se uma vez só, na máquina toda:

```
git config --global user.name "Luiz Eduardo Simão"
git config --global user.email "seu-email@exemplo.br"
git config --global init.defaultBranch main
```

O e-mail aqui aparece em cada commit. Se preferir não expor o pessoal, o
GitHub oferece um e-mail de encaminhamento em Settings → Emails → "Keep my
email addresses private" — use esse.

---

## 3. Primeiro commit

```
cd C:\Users\luize\Documents\base-fatores-br
git init
git add -A
git status
```

**Pare no `git status` e leia.** Deve listar código, crosswalk, docs,
`MANIFESTO.csv`, `.github/`, as licenças e os `.gitkeep`. **Não** deve listar
arquivos de dados brutos, `.parquet`, `.venv/` nem as fixtures sintéticas. Se
listar, o `.gitignore` não pegou — conserte antes de commitar, porque arquivo
grande commitado por engano é trabalhoso de remover do histórico depois.

```
git commit -m "Pipeline de extração e modelo de acoplamento (v0.1-dev)"
```

---

## 4. Repositório no GitHub

Crie em github.com/new:

- **Nome:** `base-fatores-transporte-br`
- **Visibilidade:** pode começar privado. Torne público antes do release — o
  Zenodo só arquiva repositório público.
- **Não** marque "Add a README", "Add .gitignore" nem "Choose a license": já
  temos os três, e marcar cria conflito no primeiro push.

Depois:

```
git remote add origin https://github.com/SEU-USUARIO/base-fatores-transporte-br.git
git push -u origin main
```

O GitHub pede autenticação. Use o Git Credential Manager (vem com o Git para
Windows) e autorize pelo navegador — senha de conta não funciona mais para
push.

Confirme que a GitHub Action rodou: aba **Actions** no repositório. Ela deve
executar as 21 verificações em dois Pythons.

---

## 5. Ligar o Zenodo

1. Entre em zenodo.org com a conta do GitHub.
2. Vá em **Settings → GitHub**.
3. Encontre `base-fatores-transporte-br` e ligue a chave para **ON**.

A partir daí, todo *release* publicado no GitHub é arquivado e recebe DOI
automaticamente. Isso só funciona com o repositório público.

**Importante:** o Zenodo arquiva apenas releases criados **depois** de ligar a
chave. Releases anteriores não são capturados retroativamente.

---

## 6. Quando a v0.1 estiver pronta

Antes de marcar a versão:

```
pip freeze > requirements.lock.txt
python codigo/_teste/testa_pipeline.py
git add -A
git commit -m "v0.1.0: módulo de frota"
git tag v0.1.0
git push origin main --tags
```

Depois, no GitHub: **Releases → Draft a new release**, escolher a tag `v0.1.0`,
escrever a descrição (o `CHANGELOG.md` já tem o conteúdo) e publicar.

O Zenodo gera dois DOIs. Use cada um no seu lugar:

| Onde | Qual DOI |
|---|---|
| Artigo que usou os dados | o **da versão** — números exatos, congelados |
| README, site, divulgação | o **de conceito** — sempre o mais recente |

Volte ao `CITATION.cff` e preencha o DOI de conceito em `identifiers`, depois
commite. A partir daí o botão "Cite this repository" do GitHub devolve a
citação completa.

---

## Rotina diária, depois disso

```
git add -A
git commit -m "o que mudou e por quê"
git push
```

Commits pequenos e frequentes, com mensagem que explique a **razão**, não a
mecânica. `"corrige tratores agrícolas entrando na contagem de cavalos"` serve;
`"atualiza script"` não serve.

Isso vale especialmente para o `crosswalk/`: cada alteração ali é uma decisão
metodológica, e o histórico do Git é o que permite a um revisor — ou a você
daqui a dois anos — entender por que um número mudou.
