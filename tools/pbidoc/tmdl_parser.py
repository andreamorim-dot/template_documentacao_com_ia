"""Parser genérico de arquivos TMDL (Tabular Model Definition Language).

TMDL é indentado por TABs. Cada linha é uma *declaração* (`table X`, `measure Y = ...`)
ou uma *propriedade* (`dataType: string`). Valores podem ser multilinha em dois formatos:

    measure X = ```
            <linhas>
            ```

    column Y =
            <linhas mais indentadas que as propriedades>

Este módulo não conhece nada de Power BI: devolve apenas a árvore de nós.
"""

import re

DECL_KIND_RE = re.compile(r"^([A-Za-z_][\w]*)\s*(.*)$", re.S)
PROP_RE = re.compile(r"^([A-Za-z_][\w]*):[ \t]*(.*)$", re.S)


class Node:
    """Um nó da árvore TMDL."""

    __slots__ = ("kind", "name", "value", "props", "children", "description")

    def __init__(self, kind, name=None, value=None, description=None):
        self.kind = kind
        self.name = name
        self.value = value
        self.props = {}
        self.children = []
        self.description = description

    def find(self, kind):
        return [c for c in self.children if c.kind == kind]

    def first(self, kind):
        for c in self.children:
            if c.kind == kind:
                return c
        return None

    def prop(self, key, default=None):
        return self.props.get(key, default)

    def __repr__(self):  # pragma: no cover - debug
        return "Node(%s, %r, props=%d, children=%d)" % (
            self.kind, self.name, len(self.props), len(self.children))


def _indent_of(line):
    n = 0
    for ch in line:
        if ch == "\t":
            n += 1
        else:
            break
    return n


def _dedent(lines):
    """Remove a indentação comum (em TABs) de um bloco de valor."""
    real = [l for l in lines if l.strip()]
    if not real:
        return ""
    base = min(_indent_of(l) for l in real)
    out = []
    for l in lines:
        out.append(l[base:] if len(l) >= base else l.lstrip("\t"))
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out).replace("\t", "    ")


def _split_lhs(lhs):
    """`measure 'Nome com espaço'` -> ('measure', 'Nome com espaço')."""
    lhs = lhs.strip()
    m = DECL_KIND_RE.match(lhs)
    if not m:
        return lhs, None
    kind, rest = m.group(1), m.group(2).strip()
    if len(rest) >= 2 and rest.startswith("'") and rest.endswith("'"):
        return kind, rest[1:-1].replace("''", "'")
    return kind, (rest or None)


def parse(text):
    """Devolve a lista de nós de nível 0 do documento TMDL."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    nodes, _ = _parse_block(lines, 0, 0)
    return nodes


def _parse_block(lines, i, indent):
    """Lê os nós com indentação `indent`; devolve (nós, próximo índice)."""
    nodes = []
    pending_desc = []
    while i < len(lines):
        raw = lines[i]
        if not raw.strip():
            i += 1
            continue
        cur = _indent_of(raw)
        if cur < indent:
            break
        content = raw[cur:].rstrip()

        # comentário de documentação `/// texto` -> vira description do próximo nó
        if content.startswith("///"):
            pending_desc.append(content[3:].strip())
            i += 1
            continue
        if content.startswith("//"):
            i += 1
            continue

        prop = PROP_RE.match(content)
        if prop:
            nodes.append(("__prop__", prop.group(1), prop.group(2).strip()))
            i += 1
            continue

        eq = content.find("=")
        if eq >= 0:
            lhs, rhs = content[:eq].rstrip(), content[eq + 1:].strip()
        else:
            lhs, rhs = content, None
        kind, name = _split_lhs(lhs)

        value = None
        i += 1
        if rhs == "```":
            # valor multilinha delimitado por crases
            buf = []
            while i < len(lines) and lines[i].strip() != "```":
                buf.append(lines[i])
                i += 1
            i += 1  # consome o fechamento
            value = _dedent(buf)
        elif rhs == "":
            # valor multilinha implícito: linhas mais indentadas que as propriedades
            buf = []
            j = i
            while j < len(lines):
                if not lines[j].strip():
                    buf.append(lines[j])
                    j += 1
                    continue
                if _indent_of(lines[j]) >= cur + 2:
                    buf.append(lines[j])
                    j += 1
                    continue
                break
            if any(b.strip() for b in buf):
                value = _dedent(buf)
                i = j
        elif rhs is not None:
            value = rhs

        node = Node(kind, name, value,
                    " ".join(pending_desc).strip() or None)
        pending_desc = []

        children, i = _parse_block(lines, i, cur + 1)
        for c in children:
            if isinstance(c, tuple):
                node.props[c[1]] = c[2]
            else:
                node.children.append(c)
        nodes.append(node)

    # nós de nível superior nunca devolvem propriedades soltas para o chamador
    if indent == 0:
        return [n for n in nodes if not isinstance(n, tuple)], i
    return nodes, i


def parse_file(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        return parse(fh.read())
