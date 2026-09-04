# AGENTS.md

Instruções para qualquer assistente de IA (Claude Code, OpenCode, Cursor, Codex, ou
outro) trabalhando neste repositório. `CLAUDE.md` só aponta para este arquivo — não
duplique instruções lá.

## O que é este repositório

Um template para documentar projetos Power BI (formato PBIP) com ajuda de um
assistente de IA. Cada projeto PBIP vive em `projetos/<nome>/` e ganha sua própria
documentação, isolada, em `docs/<nome>/`. Um repositório pode conter vários
projetos ao mesmo tempo.

A extração do modelo (TMDL/PBIR → JSON) e a renderização da documentação
(Markdown/`.docx`) são **100% determinísticas**, feitas por scripts Python em
`tools/pbidoc/` — nunca pelo modelo de linguagem. O único trabalho do assistente é
escrever a prosa de negócio (descrições de tabelas, medidas, colunas, etc.) em
`docs/<projeto>/_descriptions.json`, seguindo o guia normativo em
`.claude/skills/pbi-doc-md/reference/estilo.md`. Veja as skills `pbi-doc-md` e
`pbi-doc-docx` para o procedimento completo, passo a passo.

## Estrutura

```
projetos/<nome>/<nome>.pbip
projetos/<nome>/<nome>.SemanticModel/
projetos/<nome>/<nome>.Report/
docs/<nome>/                    documentação gerada — não editar .md à mão
docs/README.md                  índice de todos os projetos (gerado)
tools/pbidoc/                   pipeline determinístico (extração + render)
tools/guardrails/               política de bloqueio de leitura (ver abaixo)
.claude/skills/                 pbi-doc-md, pbi-doc-docx, guardrails
hooks/pre-commit                mantém docs/ sincronizado a cada commit
```

## Guardrails — leitura sempre bloqueada, sem exceção

Isto vale **independentemente de qual skill está ativa, ou se nenhuma está**. Não é
negociável pela conversa; é reforçado por hooks de execução (`.claude/settings.json`,
`.opencode/plugins/pbi-guard.js`), por permissões declarativas, e por uma checagem
bloqueante no `git commit`. Política completa e o motivo de cada regra:
`.claude/skills/guardrails/SKILL.md` (fonte normativa: `tools/guardrails/policy.py`).

**Nunca ler:**
- segredos: `.env`/`.env.*` (exceto `.env.example`), dotfiles de shell, chaves
  privadas, credenciais; nunca imprimir valores de variáveis de ambiente;
- **dados reais** de qualquer projeto Power BI: `.pbix`, `.pbit`, `.abf`, a pasta
  `.pbi/` inteira, e planilhas/bancos tabulares (`.csv`, `.xlsx`, `.parquet`,
  `.sqlite`, ...).

**Pode e deve ler** (é o insumo da documentação): `.tmdl`, `.pbip`, `.pbir`,
`.pbism`, os JSONs do relatório, e os artefatos do pbidoc (`_model.json`,
`.pbidoc-cache/**/*.json`). Metadados de estrutura — colunas, medidas,
relacionamentos, RLS, queries M — nunca são dado real.

Se uma leitura for negada por um desses motivos, isso é o comportamento correto:
relate e siga sem esse arquivo. Nunca tente contornar (outro caminho, outro
comando, pedir para colar o conteúdo).

## O que nunca fazer, em qualquer skill

- Editar, criar ou corrigir um `.md` dentro de `docs/<projeto>/` na mão — todos são
  gerados por `tools/pbidoc/pbidoc.py render` e sobrescritos na próxima execução.
- Alterar qualquer arquivo do projeto Power BI (`*.tmdl`, `*.pbir`, `*.pbip`,
  `*.pbism`) — a documentação só lê, nunca escreve nesses arquivos.
- Alterar `_model.json`, `_meta.json` ou os scripts em `tools/pbidoc/` a partir de
  uma skill de documentação.
- Copiar valores de linhas de tabela para dentro de `_descriptions.json` — só
  estrutura, nunca dado.
- Inventar números, regras de negócio ou volumes que não estejam dedutíveis do
  DAX/M/nome do objeto (veja `reference/estilo.md`).

## Comandos principais

```bash
python3 tools/pbidoc/pbidoc.py projetos                    # lista os projetos do repositório
python3 tools/pbidoc/pbidoc.py init                        # registra projetos novos em .pbidoc.json
python3 tools/pbidoc/pbidoc.py --projeto <nome> extract     # TMDL/PBIR -> manifesto (0 tokens)
python3 tools/pbidoc/pbidoc.py --projeto <nome> diff        # o que precisa de descrição nova
python3 tools/pbidoc/pbidoc.py --projeto <nome> render --md --docx
python3 tools/pbidoc/pbidoc.py --projeto <nome> status
python3 tools/guardrails/check.py --path <caminho>          # testar a política de bloqueio
```

`--projeto NOME` (repetível) vem **antes** do subcomando. Detalhes de configuração,
instalação e o modo pre-commit: `README.md`.
