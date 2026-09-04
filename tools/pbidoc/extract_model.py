"""Extrai um projeto PBIP (TMDL + PBIR) para um manifesto JSON determinístico.

Nenhuma decisão editorial é tomada aqui: o resultado é sempre o mesmo para a mesma
entrada. Toda a prosa fica em `_descriptions.json`, escrito pela skill.

Um repositório pode conter vários projetos PBIP, um por subpasta de
`projetos/` — veja `descobrir()`. `find_project()` e `extract()` continuam
operando sobre um único diretório de projeto, como antes.
"""

import glob
import hashlib
import json
import os
import re

import mlang
import tmdl_parser as T

SCHEMA_VERSION = 1
AUTO_DATE_RE = re.compile(r"^(LocalDateTable_|DateTableTemplate_)")


def _sha1(*parts):
    h = hashlib.sha1()
    for p in parts:
        h.update((p or "").encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:16]


def _is_auto_date(name):
    return bool(name and AUTO_DATE_RE.match(name))


def _strip_dax_comments(dax):
    if not dax:
        return ""
    out = re.sub(r"/\*.*?\*/", " ", dax, flags=re.S)
    out = re.sub(r"//[^\n]*", " ", out)
    return out


def _bool(v, default=False):
    if v is None:
        return default
    return str(v).strip().lower() in ("true", "1", "yes")


# --------------------------------------------------------------------------- tabelas


def _parse_column(node):
    calc = bool(node.value)
    return {
        "hash": _sha1(node.name, node.prop("dataType") or "", node.value or ""),
        "nome": node.name,
        "tipo": node.prop("dataType") or ("calculada" if calc else "desconhecido"),
        "formato": node.prop("formatString"),
        "resumir_por": node.prop("summarizeBy"),
        "coluna_origem": node.prop("sourceColumn"),
        "ordenar_por": node.prop("sortByColumn"),
        "oculta": _bool(node.prop("isHidden")),
        "calculada": calc,
        "dax": node.value if calc else None,
        "descricao_tmdl": node.description,
        "chave": _bool(node.prop("isKey")),
    }


def _parse_hierarchy(node):
    return {
        "nome": node.name,
        "niveis": [
            {"nome": lv.name, "coluna": lv.prop("column")}
            for lv in node.find("level")
        ],
    }


def _parse_table(node, path):
    columns = [_parse_column(c) for c in node.find("column")]
    partitions = []
    for p in node.find("partition"):
        src = p.first("source")
        code = (src.value if src else None) or ""
        partitions.append({
            "nome": p.name,
            "tipo": p.value,
            "modo": p.prop("mode"),
            "codigo_m": code,
            "passos": mlang.split_steps(code),
            "sql": mlang.extract_sql(code),
            "origem": mlang.detect_source(code),
        })
    m_all = "\n".join(p["codigo_m"] for p in partitions)
    origem = mlang.detect_source(m_all)
    table = {
        "nome": node.name,
        "arquivo": os.path.basename(path),
        "oculta": _bool(node.prop("isHidden")),
        "auto_data": _is_auto_date(node.name),
        "descricao_tmdl": node.description,
        "origem": origem,
        "modo_armazenamento": partitions[0]["modo"] if partitions else None,
        "colunas": columns,
        "hierarquias": [_parse_hierarchy(h) for h in node.find("hierarchy")],
        "particoes": partitions,
        "qtd_colunas": len(columns),
        "qtd_colunas_calculadas": sum(1 for c in columns if c["calculada"]),
    }
    table["hash"] = _sha1(
        node.name,
        "|".join("%s:%s:%s" % (c["nome"], c["tipo"], c["dax"] or "") for c in columns),
        m_all,
    )
    table["hash_m"] = _sha1(node.name, m_all)
    return table


def _parse_measure(node, table_name):
    dax = node.value or ""
    return {
        "nome": node.name,
        "tabela": table_name,
        "dax": dax,
        "formato": node.prop("formatString"),
        "pasta": node.prop("displayFolder"),
        "oculta": _bool(node.prop("isHidden")),
        "descricao_tmdl": node.description,
        "hash": _sha1(node.name, dax, node.prop("formatString") or ""),
    }


# ---------------------------------------------------------------- relacionamentos


def _split_ref(ref):
    if not ref:
        return None, None
    ref = ref.strip()
    m = re.match(r"^'((?:[^']|'')*)'\.(.+)$", ref)
    if m:
        return m.group(1).replace("''", "'"), m.group(2).strip("'")
    if "." in ref:
        t, c = ref.split(".", 1)
        return t.strip("'"), c.strip("'")
    return ref, None


def _parse_relationship(node):
    ft, fc = _split_ref(node.prop("fromColumn"))
    tt, tc = _split_ref(node.prop("toColumn"))
    rel = {
        "id": node.name,
        "tabela_origem": ft,
        "coluna_origem": fc,
        "tabela_destino": tt,
        "coluna_destino": tc,
        "cardinalidade_origem": node.prop("fromCardinality", "many"),
        "cardinalidade_destino": node.prop("toCardinality", "one"),
        "filtro_cruzado": node.prop("crossFilteringBehavior", "singleDirection"),
        "filtro_seguranca": node.prop("securityFilteringBehavior"),
        "ativo": _bool(node.prop("isActive"), True),
        "comportamento_data": node.prop("joinOnDateBehavior"),
        "auto_data": _is_auto_date(ft) or _is_auto_date(tt),
    }
    rel["hash"] = _sha1(ft, fc, tt, tc, rel["filtro_cruzado"], str(rel["ativo"]))
    return rel


# ------------------------------------------------------------------- parâmetros


def _parse_expression(node):
    raw = node.value or ""
    meta = ""
    idx = raw.find(" meta [")
    if idx >= 0:
        valor, meta = raw[:idx].strip(), raw[idx:]
    else:
        valor = raw.strip()
    tipo = re.search(r'Type="([^"]+)"', meta)
    return {
        "nome": node.name,
        "valor": valor,
        "tipo": tipo.group(1) if tipo else None,
        "parametro": "IsParameterQuery=true" in meta,
        "obrigatorio": "IsParameterQueryRequired=true" in meta,
        "descricao_tmdl": node.description,
        "hash": _sha1(node.name, valor),
    }


# ------------------------------------------------------------------------ roles


def _parse_role(node):
    perms = [
        {"tabela": p.name, "dax": (p.value or "").strip()}
        for p in node.find("tablePermission")
    ]
    return {
        "nome": node.name,
        "permissao_modelo": node.prop("modelPermission"),
        "permissoes": perms,
        "hash": _sha1(node.name, "|".join(p["tabela"] + ":" + p["dax"] for p in perms)),
    }


# --------------------------------------------------------------------- relatório


def _find_visual_type(obj):
    if isinstance(obj, dict):
        for key in ("visualType", "type"):
            v = obj.get(key)
            if isinstance(v, str) and v:
                return v
        for v in obj.values():
            r = _find_visual_type(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_visual_type(v)
            if r:
                return r
    return None


def _parse_report(report_dir):
    if not report_dir or not os.path.isdir(report_dir):
        return {"paginas": [], "total_visuais": 0}
    pages = []
    order = {}
    pages_json = os.path.join(report_dir, "definition", "pages", "pages.json")
    if os.path.isfile(pages_json):
        try:
            with open(pages_json, encoding="utf-8-sig") as fh:
                data = json.load(fh)
            for i, name in enumerate(data.get("pageOrder", []) or []):
                order[name] = i
        except (ValueError, OSError):
            pass
    for path in sorted(glob.glob(os.path.join(report_dir, "definition", "pages", "*", "page.json"))):
        try:
            with open(path, encoding="utf-8-sig") as fh:
                page = json.load(fh)
        except (ValueError, OSError):
            continue
        folder = os.path.basename(os.path.dirname(path))
        tipos = {}
        grupos = 0
        for vpath in sorted(glob.glob(os.path.join(os.path.dirname(path), "visuals", "*", "visual.json"))):
            try:
                with open(vpath, encoding="utf-8-sig") as fh:
                    vis = json.load(fh)
            except (ValueError, OSError):
                continue
            if not vis.get("visual") and vis.get("visualGroup"):
                grupos += 1          # contêiner de agrupamento, não é um visual
                continue
            t = _find_visual_type(vis.get("visual") or vis) or "desconhecido"
            tipos[t] = tipos.get(t, 0) + 1
        pages.append({
            "qtd_grupos": grupos,
            "id": folder,
            "nome": page.get("displayName") or folder,
            "largura": page.get("width"),
            "altura": page.get("height"),
            "oculta": (page.get("visibility") == "HiddenInViewMode"),
            "qtd_visuais": sum(tipos.values()),
            "tipos_visuais": dict(sorted(tipos.items())),
            "ordem": order.get(folder, 999),
        })
    pages.sort(key=lambda p: (p["ordem"], p["nome"]))
    return {"paginas": pages, "total_visuais": sum(p["qtd_visuais"] for p in pages)}


# ------------------------------------------------------------------ dependências


def _dependencies(dax, measure_names, columns_by_table):
    clean = _strip_dax_comments(dax)
    medidas, colunas = set(), set()
    for tbl, col in re.findall(r"'((?:[^']|'')*)'\s*\[([^\]]+)\]", clean):
        colunas.add("%s[%s]" % (tbl.replace("''", "'"), col))
    for tbl, col in re.findall(r"(?<![\]'\w])([A-Za-z_][\w]*)\s*\[([^\]]+)\]", clean):
        colunas.add("%s[%s]" % (tbl, col))
    for name in re.findall(r"(?<![\w'\]])\[([^\]]+)\]", clean):
        if name in measure_names:
            medidas.add(name)
    colunas = {c for c in colunas
               if c.split("[")[0] in columns_by_table
               and c.split("[")[1].rstrip("]") in columns_by_table[c.split("[")[0]]}
    return {"medidas": sorted(medidas), "colunas": sorted(colunas)}


# ----------------------------------------------------------------------- pública


def find_project(root):
    """Localiza o .pbip, o SemanticModel e o Report a partir da raiz do projeto."""
    pbips = sorted(glob.glob(os.path.join(root, "*.pbip")))
    sm = sorted(glob.glob(os.path.join(root, "*.SemanticModel")))
    rp = sorted(glob.glob(os.path.join(root, "*.Report")))
    if not sm:
        raise SystemExit("Nenhuma pasta *.SemanticModel encontrada em %s" % root)
    name = os.path.basename(sm[0])[:-len(".SemanticModel")]
    return {
        "nome": name,
        "pbip": pbips[0] if pbips else None,
        "semantic_model": sm[0],
        "report": rp[0] if rp else None,
    }


def descobrir(repo_root, projetos_dir="projetos"):
    """Lista os projetos PBIP do repositório: pares `(nome, caminho)`.

    Procura primeiro em `<repo_root>/<projetos_dir>/*/`, um projeto por
    subpasta (cada uma contendo um `*.SemanticModel`). Se nenhum for
    encontrado ali, cai de volta para um único projeto na raiz do
    repositório — compatibilidade com um repositório de projeto único.
    """
    base = os.path.join(repo_root, projetos_dir)
    encontrados = []
    if os.path.isdir(base):
        for nome in sorted(os.listdir(base)):
            caminho = os.path.join(base, nome)
            if os.path.isdir(caminho) and glob.glob(os.path.join(caminho, "*.SemanticModel")):
                encontrados.append((nome, caminho))
    if not encontrados and glob.glob(os.path.join(repo_root, "*.SemanticModel")):
        proj = find_project(repo_root)
        encontrados.append((proj["nome"], repo_root))
    return encontrados


def extract(root):
    proj = find_project(root)
    defdir = os.path.join(proj["semantic_model"], "definition")

    model_nodes = T.parse_file(os.path.join(defdir, "model.tmdl"))
    model = next((n for n in model_nodes if n.kind == "model"), None)
    annotations = {n.name: (n.value or "") for n in model_nodes if n.kind == "annotation"}
    order = []
    if "PBI_QueryOrder" in annotations:
        try:
            order = json.loads(annotations["PBI_QueryOrder"])
        except ValueError:
            order = []

    compat = None
    dbfile = os.path.join(defdir, "database.tmdl")
    if os.path.isfile(dbfile):
        db = T.parse_file(dbfile)
        if db:
            compat = db[0].prop("compatibilityLevel")

    tables, measures, auto_date_tables = [], [], 0
    for path in sorted(glob.glob(os.path.join(defdir, "tables", "*.tmdl"))):
        for node in T.parse_file(path):
            if node.kind != "table":
                continue
            if _is_auto_date(node.name):
                auto_date_tables += 1
                continue
            tables.append(_parse_table(node, path))
            for mnode in node.find("measure"):
                measures.append(_parse_measure(mnode, node.name))

    rank = {n: i for i, n in enumerate(order)}
    tables.sort(key=lambda t: (rank.get(t["nome"], 999), t["nome"].lower()))
    measures.sort(key=lambda m: (m["tabela"].lower(), (m["pasta"] or "").lower(), m["nome"].lower()))

    rels_all = []
    relfile = os.path.join(defdir, "relationships.tmdl")
    if os.path.isfile(relfile):
        rels_all = [_parse_relationship(n) for n in T.parse_file(relfile)
                    if n.kind == "relationship"]
    rels = [r for r in rels_all if not r["auto_data"]]
    rels.sort(key=lambda r: ((r["tabela_origem"] or "").lower(), (r["tabela_destino"] or "").lower(),
                             (r["coluna_origem"] or "").lower()))

    params = []
    expfile = os.path.join(defdir, "expressions.tmdl")
    if os.path.isfile(expfile):
        params = [_parse_expression(n) for n in T.parse_file(expfile) if n.kind == "expression"]

    roles = []
    for path in sorted(glob.glob(os.path.join(defdir, "roles", "*.tmdl"))):
        roles.extend(_parse_role(n) for n in T.parse_file(path) if n.kind == "role")
    roles.sort(key=lambda r: r["nome"].lower())

    measure_names = {m["nome"] for m in measures}
    columns_by_table = {t["nome"]: {c["nome"] for c in t["colunas"]} for t in tables}
    for m in measures:
        m["depende_de"] = _dependencies(m["dax"], measure_names, columns_by_table)
    for t in tables:
        for c in t["colunas"]:
            if c["calculada"]:
                c["depende_de"] = _dependencies(c["dax"], measure_names, columns_by_table)

    fontes = sorted({
        "%s (%s)" % (t["origem"].get("tipo"), t["origem"].get("projeto"))
        for t in tables if t["origem"].get("tipo") and t["origem"]["tipo"] != "desconhecida"
    })

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "projeto": {
            "nome": proj["nome"],
            "pbip": os.path.basename(proj["pbip"]) if proj["pbip"] else None,
            "semantic_model": os.path.basename(proj["semantic_model"]),
            "report": os.path.basename(proj["report"]) if proj["report"] else None,
            "nivel_compatibilidade": compat,
            "culture": model.prop("culture") if model else None,
            "fontes_dados": fontes,
            "inteligencia_tempo_automatica": annotations.get("__PBI_TimeIntelligenceEnabled") == "1",
        },
        "tabelas": tables,
        "medidas": measures,
        "relacionamentos": rels,
        "parametros": params,
        "perfis_rls": roles,
        "relatorio": _parse_report(proj["report"]),
        "estatisticas": {
            "tabelas": len(tables),
            "colunas": sum(t["qtd_colunas"] for t in tables),
            "colunas_calculadas": sum(t["qtd_colunas_calculadas"] for t in tables),
            "medidas": len(measures),
            "relacionamentos": len(rels),
            "relacionamentos_auto_data": len(rels_all) - len(rels),
            "tabelas_auto_data": auto_date_tables,
            "parametros": len(params),
            "perfis_rls": len(roles),
            "paginas": len(_parse_report(proj["report"])["paginas"]),
        },
    }
    manifest["estatisticas"]["paginas"] = len(manifest["relatorio"]["paginas"])
    manifest["estatisticas"]["visuais"] = manifest["relatorio"]["total_visuais"]
    return manifest


def dump(manifest, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2, sort_keys=False)
        fh.write("\n")
