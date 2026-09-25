# Guia de estilo das descrições (`_descriptions.json`)

Este guia é **normativo**. Ele existe para que a documentação de qualquer projeto
Power BI saia com a mesma cara, independentemente de quem ou de qual modelo a gerou.
Siga-o literalmente.

## Regras gerais

1. **Idioma:** português do Brasil, registro técnico-formal, tratamento impessoal.
   Nunca use "eu", "nós", "você".
2. **Sem meta-comentário.** Não escreva "esta medida", "esta tabela", "este campo",
   "conforme o código acima", "aparentemente", "provavelmente".
3. **Descreva o que o código faz, não o que ele deveria fazer.** É proibido inventar
   regra de negócio que não seja dedutível do DAX/M/nome do objeto.
4. **Nunca repita o código em palavras.** "Soma a coluna X usando SUM" não é descrição.
   Diga o significado de negócio: "Total de horas registradas no período filtrado."
5. **Sem markdown** dentro dos valores: nada de `**`, `` ` ``, listas ou links. Texto
   corrido puro — os renderizadores cuidam da formatação.
6. **Sem quebras de linha**, exceto em `visao_geral.texto`, onde parágrafos são
   separados por uma linha em branco (`\n\n`).
7. **Sem ponto final em rótulos curtos** (grão, papel). Frases completas terminam com ponto.
8. **Não invente números.** Nunca cite volumes, percentuais ou datas que não estejam
   no código.

## Quando não dá para saber

Se o objeto for genuinamente ambíguo — nome opaco, DAX sem semântica clara, coluna
sem contexto — **não invente**. Preencha assim:

```json
"medida::Medidas::xpto": { "hash": "…", "descricao": "", "regra": "", "revisar": true }
```

`"revisar": true` marca o item para revisão humana: ele aparece com um aviso na
documentação e **não é reprocessado** nas execuções seguintes (economiza tokens).
Use com parcimônia — só quando realmente não houver base para descrever.

## Campos por tipo de objeto

### `visao_geral` → campo `texto`

2 a 4 parágrafos separados por linha em branco, cobrindo nesta ordem:

1. O que o modelo mede e a que domínio de negócio pertence (deduzir dos nomes de
   tabelas, medidas e páginas do relatório).
2. De onde vêm os dados e como estão organizados (fonte, tabelas fato x dimensão).
3. Os principais indicadores disponíveis.
4. Restrições relevantes: segurança em nível de linha, atualização incremental,
   tabelas de data automáticas — apenas se existirem.

Sem título, sem lista, sem saudação.

### `tabela::<nome>` → `descricao`, `grao`, `papel`

- **`descricao`** — 1 a 3 frases. O que a tabela representa e para que serve no modelo.
- **`grao`** — uma linha, sem ponto final, no formato *"Uma linha por &lt;entidade&gt;"*.
  Exemplos: `Uma linha por pedido`, `Uma linha por item de pedido`,
  `Uma linha por cliente`, `Uma linha por par vendedor × região`.
- **`papel`** — exatamente um destes valores, sem variação:
  `fato` · `dimensao` · `auxiliar` · `parametro` · `medidas`
  - `fato`: eventos/transações, tipicamente ligada por chaves a várias dimensões.
  - `dimensao`: entidades descritivas usadas para filtrar e agrupar.
  - `auxiliar`: apoio técnico (controle de carga, de-para, listas fixas).
  - `parametro`: tabela que só carrega parâmetros/configuração.
  - `medidas`: tabela sem colunas de dados que só hospeda medidas DAX.

### `coluna::<tabela>.<coluna>` → `descricao`

**Uma linha, no máximo 20 palavras, sem ponto final.**

- Coluna com nome autoexplicativo: escreva a expansão literal.
  `id_produto` → `Identificador do produto`
  `dt_faturamento` → `Data em que o pedido foi faturado`
- Coluna de chave estrangeira: diga para qual tabela aponta.
  `id_cliente` → `Chave para a tabela clientes`
- Coluna calculada: diga o resultado, não a fórmula.
  `faixa_valor` → `Classifica o pedido em Baixo, Médio ou Alto valor`
- Prefixos comuns: `id_` = identificador, `dt_` = data, `qtd_` = quantidade,
  `nm_`/`nome_` = nome, `fl_`/`is_` = indicador booleano.

### `medida::<tabela>::<nome>` → `descricao`, `regra`

- **`descricao`** — 1 a 3 frases começando com **verbo no presente da 3ª pessoa**:
  `Calcula…`, `Conta…`, `Soma…`, `Divide…`, `Classifica…`, `Retorna…`, `Mede…`.
  Diga o que o número significa para o negócio e em que unidade está.
- **`regra`** — uma frase explicando a lógica em linguagem de negócio: quais
  registros entram, quais filtros se aplicam e como o valor é obtido.
  **Sem nomes de função DAX.** Cite colunas pelo nome quando for essencial.
  - Certo: `Percentual de pedidos entregues no prazo sobre o total de pedidos concluídos.`
  - Errado: `Usa DIVIDE com CALCULATE e FILTER sobre pedidos.`
  - Se houver limites/exclusões explícitos no código (faixas de valor, status
    ignorados, valores inválidos), **mencione-os** — é o tipo de regra que a
    documentação precisa preservar.

### `m::<tabela>` → `resumo`, `passos`

- **`resumo`** — 1 a 2 frases: de onde os dados vêm e o que a consulta entrega.
  Mencione filtro por entidade, atualização incremental ou consulta nativa se houver.
- **`passos`** — objeto `{"<nome exato do passo>": "<explicação>"}`.
  Uma frase por passo, começando com verbo no presente, **sem ponto final**.
  Use exatamente os nomes de passo informados em `contexto.passos` — não renomeie,
  não traduza, não crie passos que não existem.
  - `Fonte` → `Conecta ao banco de dados e executa a consulta nativa`
  - `Tipo Alterado` → `Converte as colunas de data para o tipo datetime`
  - `Colunas Removidas` → `Descarta a coluna table_id, não usada no modelo`

### `parametro::<nome>` → `descricao`

Uma frase: o que o parâmetro controla e onde é usado. Se for `RangeStart`/`RangeEnd`,
explique o papel na atualização incremental.

### `rls::<nome>` → `descricao`

1 a 2 frases: quem o perfil representa e qual recorte de dados ele libera.
Descreva o critério de filtro em linguagem de negócio (por cliente, por região,
por unidade/UF), sem reproduzir o DAX.

### `pagina::<nome>` → `descricao` (escopo `negocio`, e sempre em `relatorio_conectado`)

1 a 3 frases, começando com **verbo no presente da 3ª pessoa** (`Apresenta…`,
`Mostra…`, `Detalha…`): o que a página do relatório exibe e que análise ela
permite, deduzido **apenas** dos visuais, títulos e campos listados em `contexto`.

- Cite os indicadores e os recortes principais pelo significado de negócio
  (ex.: "total vendido por mês, com filtros por região, produto e período").
- **Não invente objetivo, público ou decisão de negócio** que a página apoiaria —
  isso não está nos arquivos e é preenchido por pessoas (o documento de negócio já
  marca esses pontos com `[PREENCHER: …]`).
- Página de dica de ferramenta (`tipo_pagina` = `Tooltip`): diga que é exibida ao
  passar o mouse sobre outros visuais e o que ela mostra.
- Nunca cite valores de linhas de tabela (nomes de clientes, valores, datas
  reais): só estrutura.

### Relatório conectado: medidas e campos do dataset

Em projeto `relatorio_conectado` (veja `tipos-de-projeto.md`) o dataset não está no
repositório. As mesmas chaves (`medida::…`, `coluna::…`) valem, com estas regras:

- **Medida definida no relatório** (`contexto.origem` = "medida definida no relatório"):
  tem `dax`; siga a regra normal de `medida::` (`descricao` + `regra` em linguagem de
  negócio, sem nomes de função DAX).
- **Medida ou coluna do dataset** (`contexto.origem` = "dataset…", `dax` nulo, `tipo_dado`
  nulo): só há nome, tabela e `usado_em`. Descreva o significado pelo **nome, pelos
  rótulos e títulos dos visuais e pelas dicas escritas pelo autor** — uma linha, como uma
  coluna comum. Para uma medida do dataset, `regra` só se o nome/uso a deixar evidente;
  caso contrário omita `regra` (o documento indica que o cálculo está no dataset). Não
  afirme tipo de dado, fórmula, relacionamento ou regra que não esteja visível.
  Nome opaco e sem contexto: `"revisar": true`.
- Nunca cite valores de linhas (nomes de pessoas, e-mails, contagens reais).

## Exemplos completos

```json
"tabela::pedidos": {
  "hash": "a1b2c3d4e5f60718",
  "descricao": "Registra cada pedido realizado pelos clientes, com o valor total e as chaves de cliente, vendedor e produto.",
  "grao": "Uma linha por pedido",
  "papel": "fato"
},
"medida::Medidas::entregas_no_prazo%": {
  "hash": "0f1e2d3c4b5a6978",
  "descricao": "Calcula o percentual de pedidos entregues dentro do prazo combinado.",
  "regra": "Divide a quantidade de pedidos entregues no prazo pelo total de pedidos concluídos, desconsiderando pedidos cancelados."
},
"coluna::pedidos.dt_faturamento": {
  "hash": "9a8b7c6d5e4f3021",
  "descricao": "Data em que o pedido foi faturado"
},
"pagina::Visão Geral": {
  "hash": "5e6f7a8b9c0d1e2f",
  "descricao": "Apresenta o total vendido e a quantidade de pedidos, com a evolução mensal e filtros por região, produto e período."
}
```

Relatório conectado (campo do dataset e medida de relatório):

```json
"coluna::pedidos.status": {
  "hash": "3c4d5e6f7a8b9c0d",
  "descricao": "Situação atual do pedido"
},
"medida::Medidas::ticket_medio": {
  "hash": "7a8b9c0d1e2f3c4d",
  "descricao": "Calcula o valor médio por pedido.",
  "regra": "Divide o total vendido pela quantidade de pedidos distintos."
}
```
