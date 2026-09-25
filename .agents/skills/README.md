# .agents/skills — cópia gerada, não edite

Esta pasta é um espelho de `.claude/skills/`, mantido por `tools/sync_skills.py` para
que o Antigravity (e outros harnesses que leem `.agents/skills/`) enxerguem as mesmas
skills do Claude Code. Qualquer alteração feita aqui é sobrescrita.

Para mudar uma skill, edite `.claude/skills/<skill>/` e rode:

```bash
python3 tools/sync_skills.py
```

(o `hooks/pre-commit` faz isso automaticamente a cada commit).
