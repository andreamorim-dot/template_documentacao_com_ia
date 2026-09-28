# Estrutura gerada pela skill `pbi-doc-negocio`

Documento **único** em `docs/<projeto>/<TÍTULO> - Documentação de Negócio.docx`,
na mesma ordem de tópicos de `docs/templates/Modelo - Documentacao de Negocio.docx`.

## Fidelidade visual

O arquivo sai de `tools/pbidoc/assets/template-negocio.docx` — gerado localmente
(não versionado) por `make_template.py --modelo negocio` a partir de
`docs/templates/Modelo - Documentacao de Negocio.docx`, ou de um modelo da própria
equipe no mesmo formato. Estilos, fontes embutidas, tema, cabeçalho, logotipo da
capa e marcadores de lista são preservados byte a byte.

| Elemento | Formatação (padrão do modelo) |
| --- | --- |
| Título da capa | Lato bold 20 pt, `#76b900` |
| Sumário | campo TOC nativo, títulos de nível 1 e 2, com número de página (Arial 11 pt) |
| Título 1 | estilo Heading1 — Lato bold 15 pt, `#38761d` |
| Título 2 | estilo Heading2 — Lato bold, `#76b900` |
| Título 3 | estilo Heading3 — Lato bold |
| Corpo | Lato 11 pt, justificado |
| Listas | marcadores ●/○ do `numbering.xml` do modelo (Lato Light 12 pt nas medidas) |
| Marcador de preenchimento | `[PREENCHER: …]` em negrito, realce amarelo |

Fonte do corpo e cores de capa/subtítulos/cabeçalho de tabela vêm do padrão do
modelo, mas podem ser trocadas em `estilo_docx` do `.pbidoc.json` (`fonte_neg`,
`fonte_neg_leve`, `fonte_toc`, `cor_neg_titulo`, `cor_neg_destaque`; cores em hex sem
`#`). Os estilos de título (Heading1–3) são do `styles.xml` do modelo.

Cada seção de nível 1 começa em nova página. O sumário é um campo TOC nativo
(`TOC \o "1-2"`, com números de página): o Word o atualiza ao abrir o arquivo
(`updateFields`) e o Google Docs o converte no próprio sumário — se as páginas
parecerem desatualizadas, use "Atualizar sumário" (Google Docs) ou botão direito →
Atualizar campo (Word).

Regras de formatação que os renderizadores garantem (não reverter):

- **Nenhum indicador (bookmark) visível**: o Google Docs desenha uma fita azul antes de
  cada um. Só os títulos do sumário recebem indicador, sempre oculto (`_Toc…`).
- **Títulos únicos**: dois tópicos nunca têm o mesmo texto no sumário. Colunas com o
  mesmo rótulo ficam agrupadas numa tabela sob um único título; um rótulo que coincide
  com outro título do documento ganha o complemento `(campo)` ou `(medida)`.

## Seções e origem de cada informação

Legenda: **PBIP** = extraído dos arquivos; **prosa** = `_descriptions.json`;
**config** = bloco `negocio` do `.pbidoc.json` (vazio → `[PREENCHER: …]`).

1. **Capa** — logotipo, "Dicionário de Dados <TÍTULO>", sumário.
2. **Informações Gerais**
   - Nome do Dashboard/Relatório — título do projeto e arquivo `.Report` (PBIP)
   - Link do Dashboard/Relatório — `link_relatorio`, `link_dataset` (config)
   - Objetivo do Dashboard/Relatório — `objetivo` (config)
   - Owners — `owner_tecnico`, `owner_negocio` (config)
   - Público-Alvo — `publico_area`, `publico_clientes`, `publico_perfis` (config)
   - Propriedade do Dashboard — `propriedade` (config); Ferramenta de BI = Power BI
     (PBIP); Plataforma de origem — `plataforma_origem` (config) + fontes conectadas
     ao modelo (PBIP)
   - Datas — criação/atualização do dashboard (config); criação/atualização da
     documentação (`_meta.json`)
   - Frequência de Atualização — `frequencia_atualizacao` (config) + tabelas com
     atualização incremental (PBIP)
   - Status — `status` (config)
3. **Objetivo e Regras de Negócio** — objetivo (config); regras identificadas no
   projeto: filtros fixos de relatório/página, visuais com filtro próprio, perfis de
   RLS, atualização incremental, medidas marcadas para revisão (PBIP); outras regras
   (sempre `[PREENCHER]`). **Dúvidas frequentes** — `duvidas_frequentes` (config).
4. **Estrutura do Dashboard/Relatório** — uma seção por página, na ordem de
   navegação: Descrição (prosa `pagina::`), Principais visualizações (título, tipo e
   campos de cada visual de dados), Indicadores apresentados (medidas exibidas),
   Filtros disponíveis na página (segmentações) — PBIP.
5. **Dicionário de dados** — uma entrada por **rótulo** das colunas exibidas no
   relatório (visuais, segmentações e filtros). Rótulo de uma só coluna: descrição
   (prosa), campo `tabela[coluna]` e tipo. Rótulo usado por várias colunas (ex.:
   "Aluno"): um único título e uma tabela Campo | Descrição | Tipo.
6. **Medidas** — medidas exibidas no relatório (sem relatório: todas): Definição e
   Regra de Cálculo (prosa), Plataforma (só se o modelo tiver mais de uma fonte),
   Ponto de atenção (só se marcada para revisão).
7. **Filtros e Segurança** — Filtro Padrão (filtros com valor no relatório e nas
   páginas, campos livres do painel de filtros — PBIP; filtros na origem — config) e
   RLS (descrição de cada perfil — prosa; tabelas filtradas — PBIP; atribuição de
   usuários — sempre `[PREENCHER]`).

## Relatório conectado (sem modelo local)

Quando o projeto só tem o relatório (`tipo=relatorio_conectado`), o dataset não está no
repositório e o documento se adapta: **Informações gerais** trazem o dataset conectado e
a plataforma de origem vem da conexão (não fica `[PREENCHER]`); o **Dicionário de dados**
lista os campos usados sem tipo de dado ("definido no dataset"); **Medidas** traz as
medidas de relatório com o DAX e as do dataset só pelo nome/uso; **RLS** diz que é
definida no dataset (a atribuição de usuários continua `[PREENCHER]`).

## Preenchendo as informações que não estão no PBIP

```json
{
  "projetos": {
    "meu_projeto": {
      "negocio": {
        "owner_tecnico": "Nome Sobrenome (Time de dados) — nome@empresa.com",
        "status": "Ativo",
        "duvidas_frequentes": [
          {"pergunta": "Por que o valor difere do sistema de origem?",
           "resposta": "O relatório usa a data de fim da turma como referência."}
        ]
      }
    }
  }
}
```

`python3 tools/pbidoc/pbidoc.py --projeto <nome> status --escopo negocio` lista os
campos que ainda estão vazios.
