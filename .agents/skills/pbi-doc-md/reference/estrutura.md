# Estrutura gerada pela skill `pbi-doc-md`

Esta é a estrutura **fixa**. Nenhum arquivo, seção ou ordem pode ser alterado sem
alterar `tools/pbidoc/render_md.py` — o modelo de linguagem **nunca** edita estes
arquivos diretamente.

O repositório pode ter vários projetos PBIP (um por subpasta de `projetos/`); cada
um tem sua própria pasta de documentação, isolada das demais:

```
docs/
├── README.md                    índice de todos os projetos (gerado por `render`)
├── <projeto-a>/
│   ├── README.md                arquivo principal: overview + índice
│   ├── 01-medidas.md            todas as medidas DAX
│   ├── 02-tabelas.md            todas as tabelas, colunas e o RLS
│   ├── 03-queries-m.md          parâmetros, atualização incremental e código M
│   ├── 04-modelo-relacional.md  diagrama Mermaid + propriedades dos relacionamentos
│   ├── _descriptions.json       ÚNICO arquivo que a skill escreve
│   ├── _model.json              manifesto extraído do TMDL (gerado)
│   └── _meta.json               datas de criação/atualização (gerado)
└── <projeto-b>/
    └── ... (mesma estrutura, independente)
```

`docs/README.md` também é gerado — nunca editado à mão — e lista todos os projetos
com um link para o `README.md` de cada um.

## Relatório conectado (`tipo=relatorio_conectado`)

Sem modelo local, a estrutura é outra (gerada por `render_md_relatorio.py`, também fixa):

```
docs/<projeto>/
├── README.md                     visão geral, conexão, números, índice
├── 01-paginas.md                 uma seção por página: visuais, campos, filtros, navegação
├── 02-medidas.md                 medidas de relatório (com DAX) e medidas do dataset usadas
├── 03-campos-do-dataset.md       tabelas/campos usados, onde aparecem; tabelas sem uso
├── 04-filtros-e-navegacao.md     filtros, sincronização, bookmarks, drillthrough, tooltips
├── 05-conexao-e-alertas.md       dataset, tema, configurações, alertas de qualidade
├── _descriptions.json · _model.json · _meta.json
```

As regras invioláveis abaixo valem igualmente.

## README.md de cada projeto

| Seção | Origem |
| --- | --- |
| Cabeçalho com título e subtítulo | `.pbidoc.json` (globais ou `projetos.<nome>`) |
| Tabela de identificação do projeto | manifesto |
| `## Objetivo` (só se configurado) | `.pbidoc.json` |
| `## Visão geral` | `_descriptions.json` → `visao_geral.texto` |
| `## O modelo em números` | manifesto |
| `## Índice` — links para os 4 arquivos | fixo |
| `### Atalhos` — links diretos por tabela e por medida | manifesto |
| `## Páginas do relatório` | manifesto (PBIR) |
| `## Como esta documentação é mantida` | fixo |

## Arquivos auxiliares

Todos os quatro começam **e** terminam com o botão de retorno:

```markdown
[⬅ **Voltar para a documentação principal**](./README.md)
```

- **01-medidas.md** — índice de medidas agrupado por tabela; para cada medida:
  tabela de propriedades, `**Descrição:**`, `**Regra de cálculo:**`, bloco ```` ```dax ````
  e `**Depende de:**` (medidas e colunas detectadas no DAX).
- **02-tabelas.md** — índice com papel e descrição; por tabela: descrição, grão,
  tabela de propriedades, dicionário de colunas, colunas calculadas com DAX,
  hierarquias. Termina com `## Segurança em nível de linha (RLS)`.
- **03-queries-m.md** — `## Parâmetros`, `## Atualização incremental` e, por tabela,
  resumo, propriedades, `#### Tratamentos aplicados` (lista numerada dos passos do
  `let`), `#### Código M` e `#### Consulta SQL nativa` quando houver.
- **04-modelo-relacional.md** — `erDiagram` Mermaid apenas com os relacionamentos
  reais, tabela com filtro cruzado / filtro de segurança / estado, `### Pontos de
  atenção` e `## Tabelas por papel`.

## Regras invioláveis

1. Tabelas `LocalDateTable_*` e `DateTableTemplate_*` e seus relacionamentos **nunca**
   aparecem individualmente — só na nota agregada de "Pontos de atenção".
2. Nenhum arquivo `.md` é escrito por um modelo de linguagem. Todos saem de
   `render_md.py`.
3. Onde falta descrição, o renderizador imprime `_(descrição pendente)_`.
   Isso é esperado e não é erro.
4. Um projeto nunca lê nem referencia os arquivos de outro. `_descriptions.json`,
   `_model.json` e o cache de cada projeto ficam isolados em suas próprias pastas.
