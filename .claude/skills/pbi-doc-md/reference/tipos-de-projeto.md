# Tipos de projeto Power BI e como documentar cada um

Este guia é **normativo** e compartilhado pelas skills `pbi-doc-md`, `pbi-doc-docx` e
`pbi-doc-negocio`. Antes de escrever qualquer descrição, descubra o **tipo** do projeto.

## Como descobrir o tipo (nunca adivinhe)

```bash
python3 tools/pbidoc/pbidoc.py projetos
```

A listagem traz `tipo=` para cada projeto; `diff` e `status` repetem o tipo
(`tipo: …`), e `changes.json` traz `tipo_projeto`. Esse valor vem do extrator, que decide
pelos arquivos do projeto — não pelo nome da pasta nem por suposição.

| `tipo` | O que o projeto tem | Como o extrator reconhece |
| --- | --- | --- |
| `completo` | modelo semântico local (`*.SemanticModel`, TMDL) **e** relatório (`*.Report`) | as duas pastas |
| `modelo` | só o modelo semântico, sem relatório | `*.SemanticModel` sem `*.Report` |
| `relatorio_conectado` | só o relatório, ligado a um dataset **que não está no repositório** (sem dados nem modelo) | `*.Report` sem `*.SemanticModel`; `definition.pbir` com `datasetReference` `byConnection` (ou `byPath` para modelo fora da pasta) |

Um projeto `relatorio_conectado` é o "thin report": os visuais consultam um dataset
publicado no serviço do Power BI. Por isso o repositório **não** contém tabelas, colunas
com tipos, relacionamentos, RLS, Power Query nem o DAX das medidas do dataset.

## O que cada formato entrega, por tipo

| Formato (skill) | `completo` / `modelo` | `relatorio_conectado` |
| --- | --- | --- |
| Markdown (`pbi-doc-md`) | `README`, `01-medidas`, `02-tabelas`, `03-queries-m`, `04-modelo-relacional` | `README`, `01-paginas`, `02-medidas`, `03-campos-do-dataset`, `04-filtros-e-navegacao`, `05-conexao-e-alertas` |
| Word técnico (`pbi-doc-docx`) | `<TÍTULO> - Glossário de Dados.docx` | `<TÍTULO> - Documentação do Relatório.docx` (mesmo conteúdo do Markdown) |
| Word de negócio (`pbi-doc-negocio`) | `<TÍTULO> - Documentação de Negócio.docx` | o mesmo arquivo, adaptado (dicionário sem tipos, medidas de relatório com DAX, RLS "definido no dataset", dataset nas informações gerais) |

Quais formatos cada projeto gera continua sendo `formatos` (`md`, `docx`, `negocio`) no
`.pbidoc.json` (ou em `projetos/<nome>/.pbidoc.json`): o **tipo** escolhe o renderizador.

## O que o extrator já resolve para um relatório conectado

Você não precisa (nem pode) ler os arquivos do relatório: `changes.json` traz o
contexto. Do relatório, o pipeline extrai — e o documento traz — conexão com o dataset,
páginas (tipo, visibilidade, tamanho, drillthrough), visuais (campos com rótulo e
agregação, ordenação, filtros, segmentações e sincronização), medidas definidas no
relatório (`reportExtensions.json`, com DAX), campos do dataset usados e em quais
páginas, filtros de relatório/página, bookmarks, navegação, tooltips, tema,
configurações e **alertas** (tooltip inexistente, medida de relatório sem uso, bookmark
sem botão, coluna de dado pessoal exibida, filtro divergente entre páginas...).

## Regras de prosa por tipo

### `completo` / `modelo`
Como sempre: descreva tabelas, colunas, medidas, M e RLS conforme `estilo.md`.

### `relatorio_conectado`
1. **Nunca invente o que o dataset não mostra.** Para campos e medidas **do dataset**
   (`origem` "dataset" em `contexto`) só existem nome, tabela e onde são usados. Descreva
   o significado pelo nome e pelo uso (títulos de visual, rótulos, textos do autor); não
   afirme tipo de dado, cálculo, relacionamento ou regra que não esteja visível. Sem base
   suficiente: `"revisar": true` com os campos vazios.
2. **Medidas de relatório** (`origem` "medida definida no relatório") **têm DAX**: descreva
   e explique a regra de cálculo a partir dele, como em `estilo.md` (`medida::…`).
3. **Páginas** (`pagina::<nome>`): use `contexto.visuais`, `textos_do_autor` (cabeçalhos e
   **dicas de KPI escritas pelo autor** — são a melhor fonte do significado dos
   indicadores) e `filtros_da_pagina`. Cite os filtros que definem o recorte quando forem
   relevantes ("exceto 2 trilhas", "apenas ordem de rematrícula maior que 1"), sem
   inventar objetivo, público ou decisão de negócio.
4. **Filtros trazem valores** (são regras do relatório) e podem ser citados; **nunca cite
   valores de linhas de tabela** (nomes de pessoas, e-mails, quantidades reais, datas de
   registros). O extrator já descarta o estado salvo de tabelas/matrizes e de bookmarks.
5. **Dado pessoal**: colunas como e-mail ou usuário exibidas no relatório aparecem como
   alerta; descreva-as pelo nome ("E-mail do usuário") sem repetir nenhum valor.
6. **Não há** `tabela::`, `m::`, `parametro::` nem `rls::` neste tipo — não crie essas
   chaves; use só as de `changes.json`.
7. No Word de negócio, o que o PBIP não traz continua sendo `[PREENCHER: …]`
   (bloco `negocio` do `.pbidoc.json`); o dataset e a plataforma de origem saem da
   conexão do relatório e não precisam de preenchimento.

## Limites a comunicar ao usuário (no relato final)

Para `relatorio_conectado`, diga em uma frase o que **não** pôde ser documentado por
estar no dataset (tabelas e tipos, DAX das medidas do dataset, relacionamentos, RLS,
Power Query, fontes originais) e sugira, se fizer sentido, documentar também o projeto do
dataset (um projeto `completo`/`modelo` do mesmo dataset). Liste os alertas de qualidade
mais relevantes que o extrator encontrou (`status` ou `_model.json`).
