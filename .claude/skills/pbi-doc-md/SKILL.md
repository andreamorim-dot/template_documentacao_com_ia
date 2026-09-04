---
name: pbi-doc-md
description: >-
  Gera ou atualiza a documentação em Markdown de um projeto Power BI (PBIP/TMDL) na
  pasta docs/<projeto>/: arquivo principal com overview e índice, mais medidas,
  tabelas, queries M e esquema relacional em Mermaid. Use ao pedir "documentar o
  projeto Power BI", "atualizar a documentação do PBI", "documentar as medidas/
  tabelas/queries M", ou quando um pre-commit disparar a atualização da documentação.
---

# pbi-doc-md — documentação Markdown de projeto Power BI

## O que esta skill faz (e o que ela NÃO faz)

Toda a extração e toda a formatação são feitas por scripts Python determinísticos em
`tools/pbidoc/`. **Seu único trabalho é escrever a prosa de negócio** em
`_descriptions.json`. Isso é o que garante que a documentação saia idêntica em
estrutura para qualquer projeto e que o custo em tokens seja mínimo.

**Você NUNCA:**

- edita, cria ou corrige qualquer arquivo `.md` dentro de `docs/`;
- altera qualquer arquivo do projeto Power BI (`*.tmdl`, `*.pbir`, `*.pbip`, `*.pbism`);
- altera `_model.json`, `_meta.json` ou os scripts em `tools/pbidoc/`;
- reescreve descrições cujo hash não mudou;
- lê arquivos TMDL diretamente — todo o contexto necessário vem de `changes.json`.

## Guardrails (obrigatório, não depende desta skill estar ativa)

Este repositório pode conter mais de um projeto PBIP e bloqueia, sempre — em
qualquer skill, ou sem nenhuma skill selecionada:

- leitura de segredos: `.env`/`.env.*` (exceto `.env.example`), dotfiles de shell,
  chaves privadas, dump de variáveis de ambiente;
- leitura de **dados reais** de qualquer projeto Power BI: `.pbix`, `.pbit`, `.abf`,
  a pasta `.pbi/` inteira, e planilhas/bancos tabulares (`.csv`, `.xlsx`, `.parquet`,
  `.sqlite`, ...).

Isso é reforçado por um hook que roda antes de toda tool call — não é algo que você
precisa lembrar de aplicar. Se uma leitura for negada por esse motivo, **isso é o
comportamento correto**: relate ao usuário e siga em frente. Nunca tente contornar
(por exemplo lendo o arquivo por outro caminho, ou pedindo ao usuário para colar o
conteúdo). Metadados — colunas, medidas, relacionamentos, RLS, queries M — **não**
são bloqueados; são o insumo desta skill e o pipeline os lê livremente.
Veja `.claude/skills/guardrails/SKILL.md` para a política completa.

**Você SEMPRE** executa os passos abaixo, na ordem, sem pular nenhum.

## Passo 0 — Escolher o projeto

Um repositório pode ter vários projetos PBIP, cada um numa subpasta de `projetos/`.
Descubra quais existem:

```bash
python3 tools/pbidoc/pbidoc.py projetos
```

- Se o usuário já disse qual projeto (nome, ou só há um), use-o.
- Se houver mais de um e o pedido for ambíguo ("documentar o projeto Power BI"),
  pergunte qual — **exceto em modo pre-commit** (veja abaixo), onde o projeto já vem
  determinado pelo prompt.
- Se `.pbidoc.json` não existir, crie-o (registra automaticamente todos os projetos
  encontrados):

```bash
python3 tools/pbidoc/pbidoc.py init
```

Em todos os comandos abaixo, `--projeto <nome>` vem **antes** do subcomando:
`python3 tools/pbidoc/pbidoc.py --projeto <nome> extract`.

## Passo 1 — Extrair o modelo (sem custo de tokens)

```bash
python3 tools/pbidoc/pbidoc.py --projeto <nome> extract
```

Grava `.pbidoc-cache/<nome>/model.json` com tabelas, colunas, medidas, DAX, código M,
relacionamentos, parâmetros, perfis de RLS e páginas do relatório.

## Passo 2 — Descobrir o que precisa de descrição

```bash
python3 tools/pbidoc/pbidoc.py --projeto <nome> diff
```

Em execução de pre-commit, limite o lote:

```bash
python3 tools/pbidoc/pbidoc.py --projeto <nome> diff --limite 120
```

Isso grava `.pbidoc-cache/<nome>/changes.json`. **Leia esse arquivo.** Ele traz, para
cada objeto que precisa de prosa: `chave`, `tipo`, `estado` (`novo` / `alterado` /
`pendente`) e o `contexto` mínimo (DAX, código M, tipos de coluna, etc.).

**Decida pelo campo `resumo`:**

| Situação | Ação |
| --- | --- |
| `total_a_escrever` é `0` | pule direto para o Passo 5 |
| `modo` é `completo` | descreva todos os itens da lista |
| `modo` é `incremental` | descreva **apenas** os itens listados em `itens` |

Nunca abra `_descriptions.json` para ler: tudo que você precisa está em `changes.json`.

## Passo 3 — Escrever as descrições em lotes

Leia **`reference/estilo.md`** (nesta mesma skill) antes de escrever a primeira
palavra. Ele é normativo: define campo por campo o formato, o tempo verbal, o
tamanho e os valores permitidos.

Escreva arquivos de lote em `.pbidoc-cache/<nome>/patch-NN.json`, com **no máximo 60
objetos por arquivo**:

```json
{
  "objetos": {
    "tabela::pedidos": {
      "descricao": "…",
      "grao": "Uma linha por pedido",
      "papel": "fato"
    },
    "medida::Medidas::qtd_pedidos": {
      "descricao": "…",
      "regra": "…"
    },
    "coluna::pedidos.dt_faturamento": {
      "descricao": "Data em que o pedido foi faturado"
    }
  }
}
```

Regras do lote:

- Use a `chave` **exatamente** como aparece em `changes.json`.
- Preencha exatamente os campos listados em `campos` para aquele item — nada além.
- **Não inclua o campo `hash`**: ele é carimbado automaticamente na mesclagem.
- Se não houver base para descrever, use `"revisar": true` com os campos vazios
  (ver `reference/estilo.md`).
- Cubra **todos** os itens de `changes.json`. Se forem muitos, escreva vários lotes
  — não pare no meio nem resuma.

## Passo 4 — Mesclar

```bash
python3 tools/pbidoc/pbidoc.py merge .pbidoc-cache/<nome>/patch-*.json --limpar
```

O comando valida as chaves, carimba os hashes, descarta campos inválidos e remove
descrições de objetos que não existem mais. **Leia os avisos** e corrija o que ele
apontar (chave inexistente, papel inválido) reescrevendo apenas os itens com erro.
Ao final ele informa quantas descrições ainda faltam — se for maior que zero e você
não estiver em modo pre-commit, volte ao Passo 3 para o restante.

## Passo 5 — Renderizar

```bash
python3 tools/pbidoc/pbidoc.py --projeto <nome> render --md
```

Gera em `docs/<nome>/`: `README.md`, `01-medidas.md`, `02-tabelas.md`,
`03-queries-m.md` e `04-modelo-relacional.md`, além de atualizar o índice
`docs/README.md`. A estrutura exata está descrita em `reference/estrutura.md` — não
a altere.

## Passo 6 — Relatar

Informe em no máximo 5 linhas: qual projeto, quantos objetos foram descritos, quais
arquivos mudaram e quantos itens ficaram marcados com `"revisar": true` (use
`python3 tools/pbidoc/pbidoc.py --projeto <nome> status`). Não cole trechos da
documentação gerada.

## Modo pre-commit

Quando acionada automaticamente pelo hook `hooks/pre-commit` (prompt contendo
`--precommit`):

- o projeto já vem indicado no prompt — não pergunte, não descubra sozinho;
- não faça exploração do repositório, não leia arquivos além de `changes.json`;
- respeite `limite_itens_precommit` do `.pbidoc.json` (passe `--limite`);
- não peça confirmação e não faça perguntas;
- saída final em **uma linha**: `pbidoc: N descrições atualizadas`.

## Se algo falhar

- `Nenhum projeto encontrado` → confira se o PBIP está em `projetos/<nome>/` (ou na
  raiz, no modo de projeto único) e se há uma pasta `*.SemanticModel`.
- `Manifesto ausente` → rode o Passo 1.
- Avisos de `chave inexistente` → você inventou uma chave; use as de `changes.json`.
- Uma leitura foi negada por segredo/dado real → correto, veja a seção Guardrails.
- Qualquer outro erro nos scripts: **relate e pare**. Não contorne escrevendo `.md`
  na mão.
