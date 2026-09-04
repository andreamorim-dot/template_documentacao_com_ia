---
name: guardrails
description: >-
  Política obrigatória de bloqueio de leitura deste repositório: segredos (.env,
  chaves, dumps de variáveis de ambiente) e dados reais de projetos Power BI
  (.pbix, .pbi/**, planilhas e bancos tabulares). Use para explicar por que uma
  leitura foi negada, para verificar se um caminho está bloqueado antes de tentar
  acessá-lo, ou quando o usuário perguntar sobre a política de segurança do
  repositório.
---

# guardrails — o que este repositório nunca lê

Este repositório documenta projetos Power BI com a ajuda de um assistente de IA.
Duas categorias de arquivo são **sempre** bloqueadas — em qualquer skill, com
qualquer skill ativa ou nenhuma, em qualquer harness (Claude Code, OpenCode, ou
outro que leia `AGENTS.md`). Isto não é uma preferência configurável pela conversa;
é reforçado por um hook que roda antes de toda tool call, por permissões
declarativas, e por uma verificação bloqueante no `git commit`.

## O que é bloqueado

**Segredos:**
- `.env` e `.env.*` (exceto `.env.example`/`.sample`/`.template`/`.dist`/`.tmpl`);
- dotfiles de shell: `.bashrc`, `.zshrc`, `.profile`, `.envrc`, ...;
- `.netrc`, `.pgpass`, `.npmrc`, `.git-credentials`;
- chaves privadas: `id_rsa*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`;
- comandos que despejam variáveis de ambiente: `env`, `printenv`, `export -p`,
  `declare -p`, `/proc/*/environ`, `source arquivo.env`, `echo $SECRET_X`.

**Dados reais de projetos Power BI** (os *valores* das linhas de uma tabela, não a
estrutura):
- `.pbix`, `.pbit` — arquivos binários do Power BI com dados embarcados;
- `.abf` e toda a pasta `.pbi/` (cache local de dados e conexões);
- planilhas e bancos tabulares: `.csv`, `.tsv`, `.xlsx`, `.xls`, `.xlsb`,
  `.parquet`, `.avro`, `.orc`, `.accdb`, `.mdb`, `.sqlite`, `.db`.

## O que NÃO é bloqueado (é o insumo da documentação)

`.tmdl`, `.pbip`, `.pbir`, `.pbism`, `.platform`, os JSONs do relatório
(`report.json`, `page.json`, `visual.json`), e os artefatos do próprio pbidoc
(`_model.json`, `.pbidoc-cache/**/*.json`). Colunas, medidas, relacionamentos, RLS
e queries M são texto de estrutura — precisam continuar legíveis para que a
documentação seja gerada.

## Como isso é aplicado

A política vive numa única fonte: `tools/guardrails/policy.py`. Todas as camadas a
seguir a consultam — nenhuma duplica os padrões:

1. **Hook em tempo de execução** — `tools/guardrails/check.py --hook-claude`
   (registrado em `.claude/settings.json`) e o plugin `.opencode/plugins/pbi-guard.js`
   (que chama `check.py --hook-json`) interceptam toda tool call e negam antes de
   qualquer outra checagem de permissão — inclusive em modos automáticos/sem
   confirmação.
2. **Permissões declarativas** — `permissions.deny` em `.claude/settings.json` e
   `permission.read`/`permission.bash` em `opencode.json` bloqueiam os padrões sem
   exceção legítima (dados binários/tabulares). A exceção de `.env.example` é
   tratada apenas na camada 1, que tem a lógica fina.
3. **Pre-commit bloqueante** — `tools/guardrails/check.py --staged`, primeiro passo
   de `hooks/pre-commit`, impede que um desses arquivos entre no commit. É a única
   parte deste hook que não é "aberta" (todo o resto do pre-commit falha em aviso,
   nunca bloqueia).
4. **Esta skill e `AGENTS.md`** — última instância, para harnesses sem hook.

## Se uma leitura for negada

Isso é o comportamento correto, não um erro para contornar. Relate ao usuário em
uma frase (qual arquivo, por que) e continue o trabalho sem esse arquivo. Nunca:

- tente ler o mesmo arquivo por outro caminho ou comando;
- peça ao usuário para colar o conteúdo do arquivo na conversa;
- copie valores de linhas de tabela para dentro de `_descriptions.json` — a
  documentação descreve estrutura (colunas, medidas, relacionamentos), nunca dados.

## Verificar a política manualmente

```bash
python3 tools/guardrails/check.py --path <caminho>     # exit 0 = permitido, 2 = bloqueado
python3 tools/guardrails/check.py --bash "<comando>"    # idem, para um comando de shell
python3 tools/guardrails/check.py --staged              # verifica o que está em stage
```
