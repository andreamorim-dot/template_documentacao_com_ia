# Estrutura gerada pela skill `pbi-doc-docx`

Documento **único** em `docs/<projeto>/<TÍTULO> - Glossário de Dados.docx`, um por
projeto do repositório.

## Fidelidade visual

O arquivo é produzido a partir de `tools/pbidoc/assets/template.docx` — gerado
localmente por `make_template.py` a partir do documento de referência de cada
equipe, e **nunca versionado** (fica fora do git, veja `.gitignore`). Tema,
cabeçalho com logotipo, rodapé e configuração de página são preservados byte a byte
a partir dessa referência.

Fontes e cores do corpo do texto (títulos, rótulos, código, tabelas) vêm de
`tools/pbidoc/docx_writer.py` e usam, por padrão, uma paleta neutra sem marca de
nenhum cliente:

| Elemento | Padrão de fábrica |
| --- | --- |
| Título da capa | Calibri bold 20 pt, `#1f2937` |
| Subtítulo da capa | Calibri itálico 16 pt, `#1f2937` |
| Metadados da capa | Calibri 10 pt, `#6b7280` |
| Título 1 | Calibri bold 20 pt, `#1f2937` |
| Título 2 | Calibri bold 16 pt, `#2563eb` |
| Título 3 | Calibri 14 pt, `#374151` |
| Corpo | Calibri Light 12 pt, justificado |
| Rótulo (`Descrição:`) | Calibri bold 12 pt + texto em Calibri Light |
| Código (DAX/M/SQL) | Consolas 9 pt sobre `#f3f4f6`, com borda |
| Tabelas | cabeçalho branco sobre `#1f2937`, linhas alternadas `#fafafa` |

**Para usar a identidade visual da sua equipe**, defina `estilo_docx` em
`.pbidoc.json` (globalmente, ou por projeto em `projetos.<nome>.estilo_docx` — é um
override do objeto inteiro, não campo a campo):

```json
{
  "estilo_docx": {
    "fonte": "Lato",
    "fonte_leve": "Lato Light",
    "cor_titulo": "1d4c4f",
    "cor_subtitulo": "1aa6b7"
  }
}
```

Chaves aceitas: `fonte`, `fonte_leve`, `fonte_mono`, `cor_titulo`, `cor_subtitulo`,
`cor_texto`, `cor_suave`, `cor_h3`, `cor_codigo_fundo`, `cor_borda`, `cor_branco`
(cores em hex, sem `#`). Campos omitidos mantêm o padrão neutro. Isso é
configuração — a skill nunca precisa tocar em `docx_writer.py`.

Tabelas são a única adição ao repertório do template original (que só tem
parágrafos): sem elas, um dicionário com centenas de colunas ficaria ilegível.

## Ordem das seções (fixa)

1. **Capa** — título, subtítulo, `Criado em … | Atualizado em: …`, elaborado/revisado por
2. **Objetivo**
3. **Informações gerais** — identificação, o modelo em números, páginas do relatório
4. **Índice** — links internos para seções, tabelas e medidas
5. **Visão geral do modelo**
6. **Modelo relacional** — tabela de relacionamentos e pontos de atenção
7. **Tabelas** — por tabela: descrição, grão, papel, origem, colunas, colunas calculadas
8. **Medidas** — por medida: descrição, regra de cálculo, formato, dependências, DAX
9. **Queries M** — parâmetros, atualização incremental, código e tratamentos por tabela
10. **Segurança em nível de linha (RLS)**

Cada seção de nível 1 começa em nova página.

## Diferenças em relação ao Markdown

- O Word não renderiza Mermaid: o diagrama vira a **tabela de relacionamentos**,
  com a mesma informação e mais colunas (filtro cruzado, estado).
- Não há "botão de voltar": a navegação é feita pelo **Índice** com links internos
  (indicadores/bookmarks do Word).
- O conteúdo textual é o mesmo — os dois formatos leem o **mesmo** `_descriptions.json`.

## Regenerar o template

Necessário na primeira vez que a equipe usa este template, e sempre que o documento
de referência mudar:

```bash
python3 tools/pbidoc/make_template.py "<caminho/para/referencia.docx>"
```
