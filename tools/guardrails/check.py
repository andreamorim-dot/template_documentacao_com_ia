#!/usr/bin/env python3
"""check.py — gatekeeper único dos guardrails obrigatórios.

Todas as camadas de bloqueio (hook do Claude Code, plugin do OpenCode,
`--staged` do pre-commit, e testes manuais) chamam este script; a política
em si vive em `policy.py`. Nada disso depende de qual skill está ativa —
os padrões valem sempre.

Modos:

    check.py --hook-claude          lê um evento PreToolUse do Claude Code no
                                     stdin, devolve a decisão em JSON no stdout.
                                     Roda em TODOS os modos, inclusive
                                     bypassPermissions. Falha interna => permite
                                     (fail-open: nunca trava o assistente).

    check.py --hook-json            lê {"tool": "...", "args": {...}} no stdin
                                     (usado pelo plugin do OpenCode), devolve
                                     {"deny": bool, "reason": str} no stdout.
                                     Mesmo fail-open do modo acima.

    check.py --hook-antigravity     lê um evento PreToolUse do Antigravity no stdin
                                     (`{"toolCall": {"name", "args"}}`) e devolve
                                     `{"decision": "deny"|"allow", "reason"}`. Mesmo
                                     fail-open dos modos acima.

    check.py --path CAMINHO         testa um caminho isolado.
                                     exit 0 = permitido, exit 2 = bloqueado.

    check.py --bash "comando"       testa um comando de shell isolado.
                                     exit 0 = permitido, exit 2 = bloqueado.

    check.py --staged               varre `git diff --cached --name-only` e
                                     bloqueia o commit (exit 1) se algum arquivo
                                     em stage violar a política. Ao contrário dos
                                     hooks, este modo falha FECHADO: qualquer erro
                                     interno também bloqueia o commit — é a única
                                     camada realmente obrigatória em `git commit`,
                                     então um bug aqui não pode virar um jeito
                                     silencioso de vazar dado. Escape manual:
                                     PBIDOC_SKIP=1 git commit.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import policy  # noqa: E402

# Chaves de tool_input que podem conter caminhos (Claude Code e a maioria dos
# harnesses que seguem esse mesmo formato de tool call).
PATH_KEYS = ("file_path", "path", "notebook_path", "filePath", "file", "paths",
             "filename", "target_file", "old_path", "new_path",
             # Antigravity: view_file, write_to_file/replace_file_content, grep_search,
             # list_dir, find_by_name
             "AbsolutePath", "TargetFile", "SearchPath", "DirectoryPath", "SearchDirectory")

# ferramentas que executam um comando de shell: `Bash` (Claude Code), `bash` (OpenCode),
# `run_command` (Antigravity, argumento `CommandLine`)
SHELL_TOOLS = ("bash", "run_command")


def _collect_paths(ti):
    out = []
    for k in PATH_KEYS:
        v = ti.get(k)
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, list):
            out += [x for x in v if isinstance(x, str)]
    return out


def _decisao_para(tool_name, tool_input):
    """Motivo do bloqueio (ou None) para uma tool call genérica.

    Nomes de tool variam por harness (Claude Code usa "Bash"/"Read"; o
    OpenCode usa "bash"/"read" em minúsculas; o Antigravity usa "run_command"/
    "view_file") — a comparação abaixo é case-insensitive e cobre todos sem
    duplicar esta função.
    """
    if not isinstance(tool_input, dict):
        return None
    if (tool_name or "").lower() in SHELL_TOOLS:
        cmd = tool_input.get("command") or tool_input.get("CommandLine") or ""
        if isinstance(cmd, str):
            return policy.motivo_bloqueio_bash(cmd)
        return None
    for caminho in _collect_paths(tool_input):
        motivo = policy.motivo_bloqueio_caminho(caminho)
        if motivo:
            return "%s — %s" % (motivo, caminho)
    return None


def _modo_hook_claude():
    """PreToolUse do Claude Code: JSON `{hookSpecificOutput: {permissionDecision}}`."""
    try:
        data = json.loads(sys.stdin.read())
        tool = data.get("tool_name", "") or ""
        ti = data.get("tool_input")
        motivo = _decisao_para(tool, ti)
        if motivo:
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Bloqueado pelos guardrails: %s." % motivo,
            }}))
    except SystemExit:
        raise
    except Exception:
        pass  # fail-open: nunca travar o assistente por erro interno do guard
    sys.exit(0)


def _modo_hook_json():
    """Formato genérico `{tool, args}` -> `{deny, reason}` (plugin do OpenCode)."""
    try:
        data = json.loads(sys.stdin.read())
        tool = data.get("tool", "") or ""
        args = data.get("args") or {}
        motivo = _decisao_para(tool, args)
        if motivo:
            print(json.dumps({"deny": True,
                              "reason": "Bloqueado pelos guardrails: %s." % motivo}))
        else:
            print(json.dumps({"deny": False}))
    except SystemExit:
        raise
    except Exception:
        print(json.dumps({"deny": False}))  # fail-open
    sys.exit(0)


def _modo_hook_antigravity():
    """PreToolUse do Antigravity: `{toolCall:{name,args}}` -> `{decision, reason}`."""
    try:
        data = json.loads(sys.stdin.read())
        call = data.get("toolCall") or {}
        motivo = _decisao_para(call.get("name", "") or "", call.get("args"))
        if motivo:
            print(json.dumps({"decision": "deny",
                              "reason": "Bloqueado pelos guardrails: %s." % motivo}))
        else:
            print(json.dumps({"decision": "allow"}))
    except SystemExit:
        raise
    except Exception:
        print(json.dumps({"decision": "allow"}))  # fail-open
    sys.exit(0)


def _modo_path(caminho):
    motivo = policy.motivo_bloqueio_caminho(caminho)
    if motivo:
        print("BLOQUEADO: %s (%s)" % (caminho, motivo), file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


def _modo_bash(cmd):
    motivo = policy.motivo_bloqueio_bash(cmd)
    if motivo:
        print("BLOQUEADO: %s" % motivo, file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


def _modo_staged():
    try:
        saida = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            capture_output=True, text=True, check=True)
    except Exception as exc:
        print("guardrails: não foi possível listar os arquivos em stage (%s) — "
              "commit bloqueado por segurança. Use PBIDOC_SKIP=1 para contornar "
              "manualmente." % exc, file=sys.stderr)
        sys.exit(1)

    bloqueados = []
    for caminho in (l for l in saida.stdout.splitlines() if l.strip()):
        motivo = policy.motivo_bloqueio_caminho(caminho)
        if motivo:
            bloqueados.append((caminho, motivo))

    if bloqueados:
        print("guardrails: commit bloqueado — arquivo(s) proibido(s) em stage:",
              file=sys.stderr)
        for caminho, motivo in bloqueados:
            print("  - %s (%s)" % (caminho, motivo), file=sys.stderr)
        print("Remova-os do stage (git restore --staged <arquivo>) antes de "
              "commitar.", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    modo = argv[0]
    if modo == "--hook-claude":
        _modo_hook_claude()
    elif modo == "--hook-antigravity":
        _modo_hook_antigravity()
    elif modo == "--hook-json":
        _modo_hook_json()
    elif modo == "--path" and len(argv) > 1:
        _modo_path(argv[1])
    elif modo == "--bash" and len(argv) > 1:
        _modo_bash(argv[1])
    elif modo == "--staged":
        _modo_staged()
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
