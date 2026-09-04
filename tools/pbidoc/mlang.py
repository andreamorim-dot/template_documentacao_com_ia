"""Utilitários para a linguagem M (Power Query): quebra em passos e detecção de origem."""

import re

_OPEN = "([{"
_CLOSE = ")]}"


def _scan(text):
    """Gera (índice, caractere, profundidade) ignorando conteúdo de strings e comentários."""
    depth = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            i += 1
            while i < n:
                if text[i] == '"':
                    if i + 1 < n and text[i + 1] == '"':
                        i += 2
                        continue
                    break
                i += 1
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            i = (j + 2) if j >= 0 else n
            continue
        if ch in _OPEN:
            depth += 1
        elif ch in _CLOSE:
            depth -= 1
        yield i, ch, depth
        i += 1


def split_steps(m_code):
    """Quebra `let ... in ...` na lista de passos [{'nome', 'expressao'}]."""
    if not m_code:
        return []
    text = m_code.strip()
    m = re.match(r"^\s*let\b", text)
    if not m:
        return []
    body_start = m.end()

    # localiza o `in` final em profundidade 0
    in_pos = None
    for i, ch, depth in _scan(text):
        if i < body_start or depth != 0 or ch != "i":
            continue
        if text[i:i + 2] == "in" and (i == 0 or not text[i - 1].isalnum()):
            after = text[i + 2:i + 3]
            if after == "" or not (after.isalnum() or after == "_"):
                in_pos = i
    if in_pos is None:
        in_pos = len(text)
    body = text[body_start:in_pos]

    # vírgulas de profundidade 0 separam os passos
    cuts = [i for i, ch, depth in _scan(body) if ch == "," and depth == 0]
    parts, prev = [], 0
    for c in cuts:
        parts.append(body[prev:c])
        prev = c + 1
    parts.append(body[prev:])

    steps = []
    for raw in parts:
        chunk = raw.strip()
        if not chunk:
            continue
        eq = None
        for i, ch, depth in _scan(chunk):
            if ch == "=" and depth == 0:
                nxt = chunk[i + 1:i + 2]
                if nxt not in (">", "="):
                    eq = i
                    break
        if eq is None:
            continue
        name = chunk[:eq].strip()
        if name.startswith('#"') and name.endswith('"'):
            name = name[2:-1]
        steps.append({"nome": name, "expressao": chunk[eq + 1:].strip()})
    return steps


def detect_source(m_code):
    """Extrai a origem de dados declarada no código M."""
    if not m_code:
        return {}
    src = {"tipo": "desconhecida"}
    bq = re.search(r'GoogleBigQuery\.Database\(\[BillingProject="([^"]+)"\]', m_code)
    if bq:
        src["tipo"] = "Google BigQuery"
        src["projeto"] = bq.group(1)
    sch = re.search(r'\{\[Name="([^"]+)",\s*Kind="Schema"\]\}', m_code)
    if sch:
        src["schema"] = sch.group(1)
    tbl = re.search(r'\{\[Name="([^"]+)",\s*Kind="Table"\]\}', m_code)
    if tbl:
        src["objeto"] = tbl.group(1)
    src["consulta_nativa"] = "Value.NativeQuery" in m_code
    for ref in re.findall(r"`([A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+)`", m_code):
        src.setdefault("objetos_sql", [])
        if ref not in src["objetos_sql"]:
            src["objetos_sql"].append(ref)
    if "RangeStart" in m_code and "RangeEnd" in m_code:
        src["atualizacao_incremental"] = True
    return src


def extract_sql(m_code):
    """Devolve as consultas SQL embutidas em strings do M, se houver."""
    if not m_code or "SELECT" not in m_code.upper():
        return []
    out = []
    for lit in re.findall(r'"((?:[^"]|"")*)"', m_code, re.S):
        if re.search(r"\bSELECT\b", lit, re.I) and re.search(r"\bFROM\b", lit, re.I):
            out.append(lit.replace('""', '"').strip())
    return out
