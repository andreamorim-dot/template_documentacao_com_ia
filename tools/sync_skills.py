#!/usr/bin/env python3
"""sync_skills — espelha `.claude/skills/` em `.agents/skills/`.

As skills têm **uma única fonte**: `.claude/skills/` (é onde o Claude Code as lê e onde
a equipe as edita). O Antigravity (e outros harnesses neutros, como Codex) lê skills de
`.agents/skills/`, então esta pasta é uma **cópia gerada** — nunca edite nada nela.
Cópia (e não symlink) de propósito: symlinks no git exigem configuração especial no
Windows e quebram em `/mnt/c` no WSL.

Uso:
    python3 tools/sync_skills.py            copia .claude/skills -> .agents/skills
    python3 tools/sync_skills.py --check    não escreve; sai com 1 se estiverem divergentes

O hook `hooks/pre-commit` roda o sync (e faz `git add .agents/skills`) a cada commit;
`--check` serve para CI. Só stdlib.
"""

import os
import shutil
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGEM = os.path.join(RAIZ, ".claude", "skills")
DESTINO = os.path.join(RAIZ, ".agents", "skills")
IGNORAR = {"__pycache__", ".DS_Store"}

AVISO = """# .agents/skills — cópia gerada, não edite

Esta pasta é um espelho de `.claude/skills/`, mantido por `tools/sync_skills.py` para
que o Antigravity (e outros harnesses que leem `.agents/skills/`) enxerguem as mesmas
skills do Claude Code. Qualquer alteração feita aqui é sobrescrita.

Para mudar uma skill, edite `.claude/skills/<skill>/` e rode:

```bash
python3 tools/sync_skills.py
```

(o `hooks/pre-commit` faz isso automaticamente a cada commit).
"""


def _arquivos(base):
    """{caminho relativo (com /): caminho absoluto} de todos os arquivos sob `base`."""
    achados = {}
    if not os.path.isdir(base):
        return achados
    for atual, dirs, nomes in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d not in IGNORAR)
        for nome in sorted(nomes):
            if nome in IGNORAR or nome.endswith(".pyc"):
                continue
            absoluto = os.path.join(atual, nome)
            achados[os.path.relpath(absoluto, base).replace(os.sep, "/")] = absoluto
    return achados


def _ler(caminho):
    with open(caminho, "rb") as fh:
        return fh.read()


def planejar():
    """Devolve (para_gravar, para_remover): listas de caminhos relativos ao destino."""
    origem = _arquivos(ORIGEM)
    destino = _arquivos(DESTINO)
    esperado = {rel: _ler(abs_) for rel, abs_ in origem.items()}
    esperado["README.md"] = AVISO.encode("utf-8")

    gravar = [rel for rel, dados in esperado.items()
              if rel not in destino or _ler(destino[rel]) != dados]
    remover = [rel for rel in destino if rel not in esperado]
    return sorted(gravar), sorted(remover), esperado


def sincronizar():
    gravar, remover, esperado = planejar()
    for rel in gravar:
        alvo = os.path.join(DESTINO, *rel.split("/"))
        os.makedirs(os.path.dirname(alvo), exist_ok=True)
        with open(alvo, "wb") as fh:
            fh.write(esperado[rel])
    for rel in remover:
        os.remove(os.path.join(DESTINO, *rel.split("/")))
    # remove pastas vazias que sobraram
    for atual, dirs, nomes in os.walk(DESTINO, topdown=False):
        if atual != DESTINO and not os.listdir(atual):
            shutil.rmtree(atual, ignore_errors=True)
    return gravar, remover


def main(argv):
    if not os.path.isdir(ORIGEM):
        print("sync_skills: %s não existe" % os.path.relpath(ORIGEM, RAIZ), file=sys.stderr)
        return 1
    if "--check" in argv:
        gravar, remover, _ = planejar()
        if gravar or remover:
            print("sync_skills: .agents/skills está desatualizado em relação a .claude/skills:",
                  file=sys.stderr)
            for rel in gravar:
                print("  desatualizado/ausente: %s" % rel, file=sys.stderr)
            for rel in remover:
                print("  sobrando: %s" % rel, file=sys.stderr)
            print("Rode: python3 tools/sync_skills.py", file=sys.stderr)
            return 1
        print("sync_skills: .agents/skills está em dia.")
        return 0
    gravar, remover = sincronizar()
    if not gravar and not remover:
        print("sync_skills: nada a fazer (.agents/skills já está em dia).")
    else:
        print("sync_skills: %d arquivo(s) atualizado(s), %d removido(s) em .agents/skills."
              % (len(gravar), len(remover)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
