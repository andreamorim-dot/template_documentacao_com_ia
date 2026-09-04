"""Fonte única de verdade dos padrões bloqueados de leitura.

Duas categorias, ambas OBRIGATÓRIAS e válidas **independentemente de qual
skill está ativa** — o bloqueio vale mesmo se nenhuma skill foi acionada:

1. **Segredos** — `.env`/`.env.*` (exceto `.env.example`/`.sample`/
   `.template`/`.dist`/`.tmpl`), dotfiles de shell (`.bashrc`, `.zshrc`,
   `.profile`, `.envrc`...), `.netrc`, `.pgpass`, `.npmrc`,
   `.git-credentials`, chaves privadas (`id_rsa*`, `*.pem`, `*.key`, ...) e
   comandos que despejam variáveis de ambiente (`env`, `printenv`,
   `export -p`, `/proc/*/environ`, `source .env`, `echo $SECRET_X`).

2. **Dados reais do Power BI** — arquivos que carregam os *valores* das
   linhas de uma tabela: `.pbix`, `.pbit`, `.abf` (inclui `.pbi/cache.abf`),
   toda a pasta de trabalho local `.pbi/` (guarda cache de dados e
   conexões), e planilhas/bancos tabulares (`.csv`, `.xlsx`, `.parquet`,
   `.sqlite`, ...).

**O que NÃO é bloqueado** — é o insumo da documentação e precisa continuar
legível: `*.tmdl`, `*.pbip`, `*.pbir`, `*.pbism`, `*.platform`, os JSONs do
relatório (`report.json`, `page.json`, `visual.json`), e os artefatos do
próprio pbidoc (`_model.json`, `.pbidoc-cache/**/*.json`). Metadados —
colunas, medidas, relacionamentos, RLS, queries M — são texto de estrutura,
nunca os valores das linhas.

Usado por `tools/guardrails/check.py` (hook do Claude Code, plugin do
OpenCode e `--staged` do pre-commit) e citado como referência normativa em
`AGENTS.md` e `.claude/skills/guardrails/SKILL.md`. Não duplique estes
padrões em outro lugar — importe deste módulo.
"""

import os
import re

# --------------------------------------------------------------------- segredos

ALLOW_SUFFIX_RE = re.compile(r"\.(example|sample|template|dist|tmpl)$", re.IGNORECASE)

SEGREDO_EXATO = {
    ".bashrc", ".bash_profile", ".bash_login", ".bash_logout", ".profile",
    ".zshrc", ".zprofile", ".zshenv", ".zlogin", ".zlogout",
    ".envrc", ".netrc", ".pgpass", ".my.cnf", ".pypirc", ".npmrc",
    ".git-credentials", "credentials", ".credentials.json",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
}
SEGREDO_SUFIXO = (".pem", ".key", ".p12", ".pfx", ".credentials")

# ---------------------------------------------------------------- dados reais PBI

# binários que embarcam dados (não apenas metadados de estrutura)
DADOS_PBI_SUFIXO = (".pbix", ".pbit", ".abf")

# planilhas/bancos tabulares — valores reais, nunca necessários para documentar
DADOS_TABULARES_SUFIXO = (
    ".csv", ".tsv", ".xlsx", ".xls", ".xlsb", ".parquet", ".avro", ".orc",
    ".accdb", ".mdb", ".sqlite", ".sqlite3", ".db",
)

DADOS_EXT_TODAS = DADOS_PBI_SUFIXO + DADOS_TABULARES_SUFIXO

# extensões de metadados que a documentação precisa ler — nunca bloquear
METADADOS_SUFIXO = (
    ".tmdl", ".pbip", ".pbir", ".pbism", ".platform", ".json", ".md",
)


def _basename(raw):
    return os.path.basename(str(raw).strip().strip("'\"").rstrip("/"))


def _partes(raw):
    norm = str(raw).strip().strip("'\"").replace("\\", "/")
    return [p for p in norm.split("/") if p not in ("", ".")]


def eh_env_liberado(basename):
    return bool(ALLOW_SUFFIX_RE.search(basename))


def motivo_segredo_basename(raw):
    """Retorna o motivo do bloqueio se `raw` for um arquivo de segredo, ou
    None se for permitido."""
    b = _basename(raw)
    if not b:
        return None
    if eh_env_liberado(b):
        return None
    if b == ".env" or b.startswith(".env."):
        return "arquivo .env (segredos de ambiente)"
    if b in SEGREDO_EXATO:
        return "arquivo de credenciais/configuração de shell"
    low = b.lower()
    if any(low.endswith(s) for s in SEGREDO_SUFIXO):
        return "chave ou credencial privada"
    return None


def motivo_dados_pbi(raw):
    """Retorna o motivo do bloqueio se `raw` for um arquivo de DADOS reais
    de um projeto Power BI (não metadados), ou None se for permitido."""
    partes = _partes(raw)
    if not partes:
        return None
    b = partes[-1]
    low = b.lower()
    if any(low.endswith(s) for s in DADOS_PBI_SUFIXO):
        return "arquivo binário do Power BI com dados embarcados (%s)" % b
    if ".pbi" in partes:
        return "pasta de trabalho local do Power BI (.pbi/) — cache de dados/conexões"
    if any(low.endswith(s) for s in DADOS_TABULARES_SUFIXO):
        return "arquivo de dados tabulares (%s)" % b
    return None


def motivo_bloqueio_caminho(raw):
    """Motivo do bloqueio para um caminho de arquivo, ou None se permitido."""
    return motivo_segredo_basename(raw) or motivo_dados_pbi(raw)


# ---------------------------------------------------------------- comandos Bash

_ALLOW = r"(?!\.(?:example|sample|template|dist|tmpl)\b)"
ENV_FILE_RE = re.compile(r"(?<![\w./-])\.env" + _ALLOW + r"(?:\.[\w.-]+)?", re.IGNORECASE)
RC_FILE_RE = re.compile(
    r"\.(?:bashrc|bash_profile|bash_login|bash_logout|profile|zshrc|zprofile|zshenv|"
    r"zlogin|zlogout|envrc|netrc|pgpass|pypirc|npmrc|git-credentials)\b", re.IGNORECASE)
MYCNF_RE = re.compile(r"\.my\.cnf\b", re.IGNORECASE)
KEY_FILE_RE = re.compile(
    r"\b(?:id_rsa|id_dsa|id_ecdsa|id_ed25519)\b|\.(?:pem|p12|pfx)\b", re.IGNORECASE)
CRED_FILE_RE = re.compile(
    r"/credentials\b"
    r"|(?<![\w-])credentials\.json\b"
    r"|[\w-]\.credentials\b"
    r"|(?<![\w./-])\.credentials\b",
    re.IGNORECASE)
CRED_READ_RE = re.compile(
    r"(?<![\w./-])(?:cat|less|more|head|tail|tac|nl|source|\.|xxd|od|strings|bat|cp|mv|scp)\b"
    r"[^\n;|&]*?(?<![\w-])credentials\b", re.IGNORECASE)

PRINTENV_RE = re.compile(r"(?<![\w./-])printenv\b", re.IGNORECASE)
ENV_DUMP_RE = re.compile(r"(?<![\w./-])env\s*(?:$|[|;&><])")
SETLIKE_DUMP_RE = re.compile(
    r"(?<![\w./-])(?:set|export|declare|typeset)\s*(?:$|[|;&><])"
    r"|(?<![\w./-])(?:export|declare|typeset)\s+-[a-z]*p\b", re.IGNORECASE)
COMPGEN_RE = re.compile(r"(?<![\w./-])compgen\s+-[a-z]*[ev]", re.IGNORECASE)
PROC_ENVIRON_RE = re.compile(r"/proc/[^/\s]+/environ")
SOURCE_ENV_RE = re.compile(r"(?:^|[|;&]|\s)(?:source|\.)\s+\S*\.env" + _ALLOW, re.IGNORECASE)

_SENS_VAR = (r"(?:SECRET|TOKEN|KEY|PASSWORD|PASSWD|PWD|CREDENTIAL|API|PRIVATE|AUTH|"
             r"ACCESS_?KEY|CLIENT_?SECRET|DB_?PASS|DATABASE_URL|DSN|CONN|SESSION|COOKIE)")
ECHO_SECRET_RE = re.compile(
    r"(?<![\w./-])(?:echo|printf|print)\b[^\n]*\$\{?[A-Za-z0-9_]*" + _SENS_VAR + r"[A-Za-z0-9_]*\}?",
    re.IGNORECASE)

_EXT_PADRAO = "|".join(re.escape(e) for e in DADOS_EXT_TODAS)
DADOS_EXT_RE = re.compile(r"[\w./-]+(?:" + _EXT_PADRAO + r")(?![\w.-])", re.IGNORECASE)
DADOS_PBI_DIR_RE = re.compile(r"(?<![\w.-])\.pbi/", re.IGNORECASE)


def motivo_bloqueio_bash(cmd):
    """Motivo do bloqueio para um comando Bash, ou None se permitido."""
    if ENV_FILE_RE.search(cmd):
        return "acesso a arquivo .env (.env.example é liberado)"
    if RC_FILE_RE.search(cmd) or MYCNF_RE.search(cmd):
        return "leitura de configuração de shell/credenciais"
    if KEY_FILE_RE.search(cmd):
        return "leitura de chaves privadas"
    if CRED_FILE_RE.search(cmd) or CRED_READ_RE.search(cmd):
        return "leitura de arquivo de credenciais"
    if PROC_ENVIRON_RE.search(cmd):
        return "leitura de /proc/<pid>/environ"
    if PRINTENV_RE.search(cmd) or ENV_DUMP_RE.search(cmd):
        return "dump de variáveis de ambiente (env/printenv)"
    if SETLIKE_DUMP_RE.search(cmd) or COMPGEN_RE.search(cmd):
        return "listagem/dump de variáveis de ambiente"
    if SOURCE_ENV_RE.search(cmd):
        return "carregar (source) um arquivo .env"
    if ECHO_SECRET_RE.search(cmd):
        return "impressão de valor de variável de ambiente sensível"
    if DADOS_PBI_DIR_RE.search(cmd):
        return "acesso à pasta de trabalho local do Power BI (.pbi/)"
    m = DADOS_EXT_RE.search(cmd)
    if m:
        return "acesso a arquivo de dados reais do Power BI (%s)" % m.group(0)
    return None
