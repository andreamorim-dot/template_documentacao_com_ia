# AGENTS.md

Instruções para qualquer assistente de IA (Claude Code, OpenCode, Google Antigravity,
Cursor, Codex, ou outro) trabalhando neste repositório. `CLAUDE.md` só importa este
arquivo — não duplique instruções lá.

## O que é este repositório

Um template para documentar projetos Power BI (formato PBIP) com ajuda de um
assistente de IA. Cada projeto PBIP vive em `projetos/<nome>/` e ganha sua própria
documentação, isolada, em `docs/<nome>/`. Um repositório pode conter vários
projetos ao mesmo tempo.

A extração do modelo e do relatório (TMDL/PBIR → JSON) e a renderização da
documentação (Markdown/`.docx`) são **100% determinísticas**, feitas por scripts
Python em `tools/pbidoc/` — nunca pelo modelo de linguagem. O único trabalho do
assistente é escrever a prosa (descrições de tabelas, medidas, colunas, páginas do
relatório...) em `docs/<projeto>/_descriptions.json`, seguindo o guia normativo em
`.claude/skills/pbi-doc-md/reference/estilo.md`.

## Tipos de projeto (as skills identificam sozinhas)

O extrator classifica cada projeto pelos arquivos e informa `tipo=` em
`pbidoc.py projetos` (e em `diff`, `status` e `changes.json`). **Nunca deduza o tipo pelo
nome da pasta.** Regras completas de prosa por tipo:
`.claude/skills/pbi-doc-md/reference/tipos-de-projeto.md`.

| `tipo` | O que tem | Documentação |
| --- | --- | --- |
| `completo` | modelo semântico local + relatório | modelo (tabelas, medidas, M, relacionamentos, RLS) + relatório |
| `modelo` | só o modelo semântico | como `completo`, sem páginas |
| `relatorio_conectado` | só o relatório, ligado a um dataset **fora do repositório** (sem dados nem modelo) | conexão, páginas/visuais/filtros, medidas de relatório (com DAX), campos do dataset usados, bookmarks, navegação, alertas — **nunca inventar** tipos, DAX ou relacionamentos do dataset |

O `tipo` escolhe o renderizador: `md` e `docx` geram os arquivos de modelo (`completo`/
`modelo`) ou de relatório (`relatorio_conectado`); `negocio` se adapta ao tipo.

## Três formatos de documentação, três skills

| Formato | Skill | Saída em `docs/<projeto>/` | Escopo do catálogo |
| --- | --- | --- | --- |
| Markdown técnico | `pbi-doc-md` | `README.md`, `01-medidas.md`, … `04-modelo-relacional.md` (relatório conectado: `01-paginas.md` … `05-conexao-e-alertas.md`) | `tecnico` |
| Word técnico (glossário) | `pbi-doc-docx` | `<TÍTULO> - Glossário de Dados.docx` (relatório conectado: `<TÍTULO> - Documentação do Relatório.docx`) | `tecnico` |
| Word de **negócio** | `pbi-doc-negocio` | `<TÍTULO> - Documentação de Negócio.docx` | `negocio` |

- Quais formatos cada projeto gera é `formatos` (`md`, `docx`, `negocio`) no
  `.pbidoc.json`. O escopo `negocio` é um superconjunto do `tecnico`: acrescenta as
  **páginas do relatório** (`pagina::<nome>`) e exige a descrição de toda coluna
  exibida no relatório. A prosa é compartilhada entre os três formatos.
- O documento de negócio traz informações que **não existem nos arquivos do PBIP**
  (owners, objetivo, público, links, datas, status, FAQ...). Elas vêm do bloco
  `projetos.<nome>.negocio` do `.pbidoc.json`, preenchido por **pessoas**; enquanto
  vazias, saem como `[PREENCHER: …]` (realce amarelo). O assistente nunca as inventa
  nem escreve no `.pbidoc.json`.
- Os `.docx` saem de templates gerados localmente e **não versionados**
  (`tools/pbidoc/assets/template-tecnico.docx`, `template-negocio.docx` e
  `template-relatorio.docx`), feitos a partir dos documentos-modelo versionados em
  `docs/templates/`
  (`python3 tools/pbidoc/make_template.py "<modelo.docx>" --modelo tecnico|negocio|relatorio`).
  Os modelos de `docs/templates/` trazem `[PREENCHER: …]` no lugar de nomes, e-mails,
  clientes e sistemas — a equipe pode trocá-los pelos seus próprios modelos.
- Regras de formatação dos `.docx` (garantidas por `tools/pbidoc/docx_writer.py`; ao
  alterar renderizadores ou modelos, preserve-as): sumário/índice é um campo TOC nativo
  com números de página (níveis 1–2); **nenhum indicador (bookmark) visível** — o Google
  Docs desenha uma fita azul em cada um, então só existem os `_Toc…` ocultos do sumário;
  **nenhum título repetido** — itens com o mesmo rótulo são agrupados (tabela) sob um
  único título.

## Estrutura

```
projetos/<nome>/<nome>.pbip
projetos/<nome>/<nome>.SemanticModel/
projetos/<nome>/<nome>.Report/            (relatório conectado: só isto + o .pbip)
projetos/<nome>/.pbidoc.json              config local do projeto (opcional)
docs/<nome>/                    documentação gerada — não editar .md à mão
docs/README.md                  índice de todos os projetos (gerado)
docs/templates/                 documentos-modelo Word (técnico, negócio e relatório)
tools/pbidoc/                   pipeline determinístico (extração + render)
tools/guardrails/               política de bloqueio de leitura (ver abaixo)
tools/sync_skills.py            espelha .claude/skills em .agents/skills
.claude/skills/                 FONTE das skills: pbi-doc-md, pbi-doc-docx,
                                pbi-doc-negocio, guardrails
.agents/skills/                 CÓPIA gerada das skills (Antigravity) — não editar
.agents/hooks.json              hook de guardrails do Antigravity
hooks/pre-commit                mantém docs/ sincronizado a cada commit
.gitattributes                  fim de linha LF em qualquer SO; .docx como binário
```

## Harnesses suportados

| Harness | Instruções | Skills | Guardrails em tempo de execução |
| --- | --- | --- | --- |
| Claude Code | `CLAUDE.md` → este arquivo | `.claude/skills/` | `.claude/settings.json` (hook `PreToolUse` + `deny`) |
| OpenCode | este arquivo (`opencode.json`) | via `opencode.json` | `.opencode/plugins/pbi-guard.js` + `permission` |
| Google Antigravity | este arquivo (lido nativamente) | `.agents/skills/` | `.agents/hooks.json` (hook `PreToolUse`) |
| Outros que leem `AGENTS.md` | este arquivo | — | só as camadas de commit e política |

**Skills têm uma única fonte: `.claude/skills/`.** `.agents/skills/` é gerado por
`python3 tools/sync_skills.py` (o `hooks/pre-commit` roda isso a cada commit;
`--check` serve para CI) — **nunca edite `.agents/skills/` à mão**, a alteração é
sobrescrita. Ao criar ou alterar uma skill, edite só `.claude/skills/` e rode o sync.

## Guardrails — leitura sempre bloqueada, sem exceção

Isto vale **independentemente de qual skill está ativa, ou se nenhuma está**. Não é
negociável pela conversa; é reforçado por hooks de execução (`.claude/settings.json`,
`.opencode/plugins/pbi-guard.js`, `.agents/hooks.json`), por permissões declarativas,
e por uma checagem bloqueante no `git commit`. Política completa e o motivo de cada
regra: `.claude/skills/guardrails/SKILL.md` (fonte normativa dos padrões:
`tools/guardrails/policy.py`).

**Nunca ler:**
- segredos: `.env`/`.env.*` (exceto `.env.example`), dotfiles de shell, chaves
  privadas, credenciais; nunca imprimir valores de variáveis de ambiente;
- **dados reais** de qualquer projeto Power BI: `.pbix`, `.pbit`, `.abf`, a pasta
  `.pbi/` inteira, e planilhas/bancos tabulares (`.csv`, `.xlsx`, `.parquet`,
  `.sqlite`, ...).

**Pode e deve ler** (é o insumo da documentação): `.tmdl`, `.pbip`, `.pbir`,
`.pbism`, os JSONs do relatório (páginas, visuais, campos, filtros), e os artefatos do
pbidoc (`_model.json`, `.pbidoc-cache/**/*.json`). Metadados de estrutura — colunas,
medidas, relacionamentos, RLS, queries M, páginas — nunca são dado real.

**Estado salvo de relatórios:** arquivos de relatório (`visual.json`, `bookmark.json`) podem
guardar valores reais de linhas (`expansionStates` de matrizes, estado de filtros em
bookmarks). O extrator descarta esse estado; nenhuma skill deve lê-lo ou citá-lo. As
**condições dos filtros** (regras do relatório) podem ser documentadas.

Se uma leitura for negada por um desses motivos, isso é o comportamento correto:
relate e siga sem esse arquivo. Nunca tente contornar (outro caminho, outro
comando, pedir para colar o conteúdo).

## O que nunca fazer, em qualquer skill

- Editar, criar ou corrigir um `.md` ou `.docx` dentro de `docs/<projeto>/` na mão —
  todos são gerados por `tools/pbidoc/pbidoc.py render` e sobrescritos na próxima
  execução.
- Alterar qualquer arquivo do projeto Power BI (`*.tmdl`, `*.pbir`, `*.pbip`,
  `*.pbism`, JSONs do relatório) — a documentação só lê, nunca escreve neles.
- Alterar `_model.json`, `_meta.json`, os templates ou os scripts em `tools/pbidoc/`
  a partir de uma skill de documentação.
- Preencher o bloco `negocio` do `.pbidoc.json` ou escrever objetivo, público ou
  decisões de negócio dentro das descrições de páginas — isso é informação humana,
  marcada com `[PREENCHER: …]`.
- Copiar valores de linhas de tabela para dentro de `_descriptions.json` — só
  estrutura, nunca dado.
- Em relatório conectado: inventar tipos de dado, DAX, relacionamentos ou RLS do dataset,
  que não estão no repositório — descreva só o que o relatório revela.
- Inventar números, regras de negócio ou volumes que não estejam dedutíveis do
  DAX/M/nome do objeto (veja `reference/estilo.md`).
- Editar `.agents/skills/` (é cópia gerada — veja acima).

## Comandos principais

```bash
python3 tools/pbidoc/pbidoc.py projetos                    # lista os projetos do repositório
python3 tools/pbidoc/pbidoc.py init                        # registra projetos novos em .pbidoc.json
python3 tools/pbidoc/pbidoc.py --projeto <nome> extract     # TMDL/PBIR -> manifesto (0 tokens)
python3 tools/pbidoc/pbidoc.py --projeto <nome> diff --escopo tecnico|negocio
python3 tools/pbidoc/pbidoc.py merge .pbidoc-cache/<nome>/patch-*.json --limpar --escopo negocio
python3 tools/pbidoc/pbidoc.py --projeto <nome> render --md --docx --negocio
python3 tools/pbidoc/pbidoc.py --projeto <nome> status --escopo negocio
python3 tools/sync_skills.py [--check]                      # espelha as skills para o Antigravity
python3 tools/guardrails/check.py --path <caminho>          # testar a política de bloqueio
```

`--projeto NOME` (repetível) vem **antes** do subcomando. `--escopo` só se aplica a
`diff`, `merge` e `status`; sem ele vale `negocio` se o projeto tem `negocio` em
`formatos`, senão `tecnico`. Detalhes de configuração, instalação e o modo
pre-commit: `README.md`.
