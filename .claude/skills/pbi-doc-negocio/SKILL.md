---
name: pbi-doc-negocio
description: >-
  Gera ou atualiza a documentação de NEGÓCIO de um projeto Power BI (PBIP) num único
  .docx em docs/<projeto>/ ("<TÍTULO> - Documentação de Negócio.docx"), seguindo o
  "Modelo - Documentacao de Negocio": informações gerais, objetivo e regras,
  estrutura do dashboard por página, dicionário de dados, medidas, filtros e RLS.
  O que não pode ser extraído do PBIP sai com o marcador [PREENCHER: …]. Use ao
  pedir "documentação de negócio", "dicionário de dados do dashboard" ou
  "documentar o relatório para a área de negócio".
---

# pbi-doc-negocio — documentação de negócio em .docx

## O que esta skill faz (e o que ela NÃO faz)

Toda a extração e toda a formatação são feitas por scripts Python determinísticos em
`tools/pbidoc/`. **Seu único trabalho é escrever a prosa** em `_descriptions.json`
— o mesmo arquivo usado pelas skills `pbi-doc-md` e `pbi-doc-docx`. A prosa já
escrita por elas (colunas, medidas, RLS) é reaproveitada sem custo; aqui entram, a
mais, as descrições das **páginas do relatório**.

O `.docx` é produzido a partir de `tools/pbidoc/assets/template-negocio.docx`
(gerado localmente, não versionado), cópia de
`docs/templates/Modelo - Documentacao de Negocio.docx` com o corpo esvaziado
(estilos, logotipo, cabeçalho e marcadores de lista preservados).

### Regra obrigatória: o marcador `[PREENCHER: …]`

Tudo que **não existe nos arquivos do PBIP** — link, objetivo do dashboard, owners,
público-alvo, propriedade, sistema de origem, datas do dashboard, frequência de
atualização agendada, status, dúvidas frequentes, filtros feitos na origem e a
atribuição de usuários aos perfis de RLS — é escrito pelo renderizador com o
marcador `[PREENCHER: <o que informar>]`, em negrito e realçado em amarelo. Quem
revisar o documento encontra todos com Ctrl+F por **PREENCHER**.

Esses valores são informados por pessoas no bloco `negocio` do `.pbidoc.json`
(`projetos.<nome>.negocio`); quando preenchidos, o marcador some na próxima geração
e o valor sobrevive às regenerações. **Editar o .docx à mão não adianta**: ele é
regenerado a cada commit.

**Você NUNCA:**

- inventa ou deduz valores para o bloco `negocio` (owners, objetivo, público, links,
  datas, status, FAQ…) nem escreve no `.pbidoc.json` — só o usuário faz isso, e só se
  ele pedir explicitamente e informar o valor;
- escreve objetivo de negócio, público ou decisões dentro da descrição das páginas;
- tenta montar o `.docx` por conta própria ou instala bibliotecas;
- edita arquivos dentro de `docs/` além de `_descriptions.json`;
- altera arquivos do projeto Power BI (`*.tmdl`, `*.pbir`, `*.pbip`, `*.pbism`, `*.json`
  do relatório), os templates ou os scripts em `tools/pbidoc/`;
- reescreve descrições cujo hash não mudou;
- lê arquivos TMDL/PBIR diretamente — o contexto necessário vem de `changes.json`.

## Guardrails (obrigatório, não depende desta skill estar ativa)

Valem os mesmos bloqueios de `pbi-doc-md`: nunca ler segredos (`.env`, dotfiles de
shell, chaves) nem **dados reais** de qualquer projeto Power BI (`.pbix`, `.pbit`,
`.abf`, `.pbi/**`, planilhas e bancos tabulares). Metadados de estrutura — inclusive
páginas, visuais, campos e filtros do relatório — são o insumo desta skill e não são
bloqueados. Se uma leitura for negada, é o comportamento esperado: relate e siga,
nunca contorne. Nunca copie valores de linhas de tabela para as descrições — nem
como "exemplo" numa descrição de página ou de coluna. Política completa em
`.claude/skills/guardrails/SKILL.md`.

## Passo 0 — Escolher o projeto e conferir o template

Este repositório é um template e pode conter **vários** projetos PBIP. Liste-os:

```bash
python3 tools/pbidoc/pbidoc.py projetos
```

- Um único projeto: use-o.
- Mais de um: use o projeto que o usuário indicou; se ele não indicou, **pergunte
  qual** antes de continuar (exceto em modo pre-commit). Daqui em diante, **todo**
  comando leva `--projeto <nome>` (antes do subcomando) — nunca misture projetos.
- Projeto sem relatório (`relatorio=nao` na listagem): avise que as seções de
  estrutura, dicionário e filtros sairão reduzidas, e continue.

Se `.pbidoc.json` não tiver o projeto em `projetos`, registre-o (cria o bloco
`negocio` vazio que o usuário depois preenche):

```bash
python3 tools/pbidoc/pbidoc.py init
```

Confirme que `tools/pbidoc/assets/template-negocio.docx` existe. Se não existir:

```bash
python3 tools/pbidoc/make_template.py "docs/templates/Modelo - Documentacao de Negocio.docx" --modelo negocio
```

## Passo 0b — Identificar o tipo do projeto (obrigatório)

A listagem do Passo 0 traz `tipo=` para cada projeto (o mesmo valor aparece em `diff`,
`status` e em `changes.json` → `tipo_projeto`). **Leia `../pbi-doc-md/reference/tipos-de-projeto.md`**: ele define os tipos
e as regras de prosa de cada um. Nunca deduza o tipo pelo nome da pasta — use o `tipo=`.

- `completo` / `modelo` (modelo semântico local): siga os passos normalmente.
- `relatorio_conectado` (só o relatório, ligado a um dataset que **não** está no
  repositório): o `.docx` de negócio sai adaptado — dicionário sem tipos de dado, medidas de relatório com o DAX, medidas do dataset só pelo nome, RLS "definido no dataset", e dataset/plataforma de origem preenchidos pela conexão do relatório (só o que o PBIP não traz fica `[PREENCHER]`). O catálogo é o mesmo do escopo `negocio` (`visao_geral`, `pagina::`, `medida::`, `coluna::`); não invente `tabela::`, `m::`, `parametro::` ou `rls::`.

## Passo 1 — Extrair o modelo e o relatório (sem custo de tokens)

```bash
python3 tools/pbidoc/pbidoc.py --projeto <nome> extract
```

## Passo 2 — Descobrir o que precisa de descrição

```bash
python3 tools/pbidoc/pbidoc.py --projeto <nome> diff --escopo negocio
```

O escopo `negocio` acrescenta ao catálogo os itens `pagina::<nome>` e exige a
descrição de toda coluna exibida no relatório. **Leia
`.pbidoc-cache/<nome>/changes.json`** e decida pelo campo `resumo`:

| Situação | Ação |
| --- | --- |
| `total_a_escrever` é `0` | pule direto para o Passo 5 |
| `modo` é `completo` | descreva todos os itens da lista |
| `modo` é `incremental` | descreva **apenas** os itens listados em `itens` |

## Passo 3 — Escrever as descrições em lotes

Leia **`../pbi-doc-md/reference/estilo.md`** antes de escrever a primeira palavra —
em especial a seção `pagina::<nome>`. É o guia normativo único dos três formatos.

Escreva arquivos de lote em `.pbidoc-cache/<nome>/patch-NN.json`, com no máximo 60
objetos por arquivo:

```json
{
  "objetos": {
    "pagina::Visão Geral": {
      "descricao": "Apresenta o total vendido e a quantidade de pedidos, com a evolução mensal e filtros por região, produto e período."
    },
    "coluna::produtos.nome": { "descricao": "Nome do produto" },
    "medida::Medidas::qtd_pedidos": { "descricao": "…", "regra": "…" }
  }
}
```

Regras do lote:

- Use a `chave` **exatamente** como aparece em `changes.json`.
- Preencha exatamente os campos listados em `campos` — nada além.
- **Não inclua o campo `hash`**: ele é carimbado na mesclagem.
- A descrição de página usa só o que está em `contexto.visuais` (tipos, títulos e
  campos). Sem base para descrever? Use `"revisar": true` com os campos vazios.
- Cubra **todos** os itens de `changes.json`, em quantos lotes forem necessários.

## Passo 4 — Mesclar

```bash
python3 tools/pbidoc/pbidoc.py merge .pbidoc-cache/<nome>/patch-*.json --limpar --escopo negocio
```

Leia os avisos e corrija apenas os itens apontados. (O projeto é inferido do
caminho dos lotes.)

## Passo 5 — Renderizar o .docx de negócio

```bash
python3 tools/pbidoc/pbidoc.py --projeto <nome> render --negocio
```

Gera `docs/<projeto>/<TÍTULO> - Documentação de Negócio.docx`. A ordem das seções
e a origem de cada informação estão em `reference/estrutura.md` — não as altere.

## Passo 6 — Relatar

```bash
python3 tools/pbidoc/pbidoc.py --projeto <nome> status --escopo negocio
```

Informe em no máximo 6 linhas: qual projeto, quantos objetos foram descritos, o
caminho do `.docx`, quantos itens ficaram com `"revisar": true` e **quantas
informações ainda estão com `[PREENCHER]`**, lembrando que elas são preenchidas no
bloco `projetos.<nome>.negocio` do `.pbidoc.json` (liste os nomes dos campos que o
`status` mostrou). Não cole trechos do documento.

Se o projeto for `relatorio_conectado`, diga em uma frase o que **não** pôde ser documentado por estar no dataset (tabelas e tipos, DAX das medidas do dataset, relacionamentos, RLS, Power Query) e cite os alertas de qualidade mais relevantes que `status` mostrou.

## Modo pre-commit

Quando acionada automaticamente pelo hook (prompt contendo `--precommit`): o
projeto vem no prompt e o hook já rodou `extract` e `diff` — **não** os rode de
novo, comece no Passo 3 lendo `.pbidoc-cache/<nome>/changes.json`. Sem exploração do
repositório, sem perguntas, e saída final em uma linha:
`pbidoc: N descrições atualizadas`.

## Se algo falhar

- `Template ausente` → gere-o com `make_template.py` (Passo 0).
- `Projeto não encontrado` / `Nenhum projeto encontrado` → confira `--projeto` e se
  o PBIP está em `projetos/<nome>/` com uma pasta `*.SemanticModel` e/ou `*.Report`.
- Avisos de `chave inexistente` → você inventou uma chave; use as de `changes.json`.
- Uma leitura foi negada por segredo/dado real → correto, veja a seção Guardrails.
- Qualquer outro erro nos scripts: **relate e pare**. Não tente produzir o `.docx`
  de outro jeito.
