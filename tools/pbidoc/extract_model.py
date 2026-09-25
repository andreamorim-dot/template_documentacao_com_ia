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


def _ler_json(path):
    try:
        with open(path, encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return None


def _entidade(expr):
    """Nome da tabela de um `{"SourceRef": {"Entity": ...}}` (ou None)."""
    ref = (expr or {}).get("SourceRef") or {}
    return ref.get("Entity") or ref.get("Source")


def _eh_extensao(expr):
    """True se a referência aponta para o esquema de extensões do relatório."""
    return ((expr or {}).get("SourceRef") or {}).get("Schema") == "extension"


# código de `Aggregation.Function` do PBIR -> rótulo (na interface: "Contagem (distinta)" = 2,
# "Contagem" = 5)
AGREGACAO = {0: "Soma", 1: "Média", 2: "Contagem distinta", 3: "Mínimo", 4: "Máximo",
             5: "Contagem", 6: "Mediana", 7: "Desvio padrão", 8: "Variância"}


def _campo(field):
    """Normaliza o `field` de uma projeção/filtro do PBIR em {tabela, campo, tipo}."""
    if not isinstance(field, dict):
        return None
    if "Measure" in field:
        f = field["Measure"]
        return {"tabela": _entidade(f.get("Expression")), "campo": f.get("Property"),
                "tipo": "medida", "extensao": _eh_extensao(f.get("Expression"))}
    if "Column" in field:
        f = field["Column"]
        return {"tabela": _entidade(f.get("Expression")), "campo": f.get("Property"),
                "tipo": "coluna", "extensao": False}
    if "Aggregation" in field:
        interno = _campo((field["Aggregation"] or {}).get("Expression"))
        if interno:
            interno["tipo"] = "agregacao"
            interno["agregacao"] = AGREGACAO.get((field["Aggregation"] or {}).get("Function"))
        return interno
    if "HierarchyLevel" in field:
        f = field["HierarchyLevel"]
        hier = ((f.get("Expression") or {}).get("Hierarchy") or {})
        base = hier.get("Expression") or {}
        variacao = base.get("PropertyVariationSource")
        if variacao:
            # hierarquia automática de data: a coluna é a origem da variação; `nivel` é o
            # nível usado no visual (Ano, Trimestre, Mês, Dia)
            return {"tabela": _entidade(variacao.get("Expression")),
                    "campo": variacao.get("Property"), "tipo": "coluna", "extensao": False,
                    "nivel": f.get("Level")}
        return {"tabela": _entidade(base), "campo": f.get("Level"),
                "tipo": "coluna", "extensao": False}
    return None


def _literal(v):
    lit = (v or {}).get("Literal") or {}
    valor = lit.get("Value")
    if not isinstance(valor, str):
        return None
    valor = valor.strip()
    if len(valor) >= 2 and valor[0] == valor[-1] == "'":
        return valor[1:-1].replace("''", "'")
    if valor.endswith(("L", "D", "M")) and valor[:-1].replace(".", "", 1).lstrip("-").isdigit():
        return valor[:-1]
    if valor.startswith("datetime'"):
        return valor[len("datetime'"):-1][:10]
    return valor


def _lit(bloco):
    """`{"expr": {"Literal": {...}}}` (valor de propriedade de objeto) -> texto."""
    return _literal((bloco or {}).get("expr"))


def _prop(objs, grupo, nome, idx=0):
    try:
        return _lit(objs[grupo][idx]["properties"][nome])
    except (KeyError, IndexError, TypeError):
        return None


COMPARACAO = {0: "=", 1: ">", 2: ">=", 3: "<", 4: "<="}


def _descrever_condicao(cond):
    if not isinstance(cond, dict):
        return None
    if "Not" in cond:
        interno = _descrever_condicao((cond["Not"] or {}).get("Expression"))
        return ("exceto " + interno[3:]) if interno and interno.startswith("em ") else (
            "não (%s)" % interno if interno else None)
    if "In" in cond:
        valores = []
        for linha in (cond["In"] or {}).get("Values") or []:
            for v in linha:
                lit = _literal(v)
                if lit is not None:
                    valores.append(lit)
        return "em " + ", ".join(valores) if valores else None
    if "Comparison" in cond:
        c = cond["Comparison"] or {}
        lit = _literal(c.get("Right"))
        if lit is None:
            return None
        prefixo = "participação no total " if "Arithmetic" in (c.get("Left") or {}) else ""
        return "%s%s %s" % (prefixo, COMPARACAO.get(c.get("ComparisonKind"), "?"), lit)
    for op, rotulo in (("And", " e "), ("Or", " ou ")):
        if op in cond:
            a = _descrever_condicao((cond[op] or {}).get("Left"))
            b = _descrever_condicao((cond[op] or {}).get("Right"))
            if a and b:
                return a + rotulo + b
            return None
    return None


def _achar(obj, chave):
    """Primeiro valor da `chave` em qualquer nível de um JSON aninhado (ou None)."""
    if isinstance(obj, dict):
        if chave in obj:
            return obj[chave]
        for v in obj.values():
            r = _achar(v, chave)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _achar(v, chave)
            if r is not None:
                return r
    return None


UNIDADE_TEMPO = {0: "dia(s)", 1: "semana(s)", 2: "mês(es)", 3: "trimestre(s)", 4: "ano(s)"}


def _condicao_especial(flt):
    """Texto para filtros que não são listas/comparações simples (TopN, data relativa...)."""
    tipo = flt.get("type")
    corpo = flt.get("filter") or {}
    if tipo == "TopN":
        n = _achar(corpo, "Top")
        medida = None
        ordem = _achar(corpo, "OrderBy")
        if isinstance(ordem, list) and ordem:
            m = _campo(((ordem[0] or {}).get("Expression")) or {})
            medida = m and m.get("campo")
        if isinstance(n, int):
            return "Top %d%s" % (n, " por %s" % medida if medida else "")
        return "Top N"
    if tipo in ("RelativeDate", "RelativeTime"):
        qtd = _achar(corpo, "Amount")
        unidade = UNIDADE_TEMPO.get(_achar(corpo, "TimeUnit"))
        if isinstance(qtd, int) and unidade:
            return "período relativo (%d %s)" % (abs(qtd), unidade)
        return "período relativo"
    return None


def _parse_filtros(dono):
    """Filtros de `filterConfig` (relatório, página ou visual)."""
    saida = []
    for flt in ((dono or {}).get("filterConfig") or {}).get("filters") or []:
        campo = _campo(flt.get("field"))
        if not campo or not campo.get("campo"):
            continue
        cond = None
        aplicado = bool(flt.get("filter"))
        if aplicado:
            wheres = (flt["filter"] or {}).get("Where") or []
            partes = [_descrever_condicao(w.get("Condition")) for w in wheres]
            if flt.get("type") in ("TopN", "RelativeDate", "RelativeTime"):
                cond = _condicao_especial(flt)
            elif partes and all(partes):
                cond = "; ".join(partes)
            else:
                cond = "condição avançada"
        saida.append({
            "tabela": campo["tabela"],
            "campo": campo["campo"],
            "tipo_campo": campo["tipo"],
            "tipo_filtro": flt.get("type") or "—",
            "aplicado": aplicado,
            "condicao": cond,
            "criado_como": flt.get("howCreated"),
            "oculto": bool(flt.get("isHiddenInViewMode")),
            "bloqueado": bool(flt.get("isLockedInViewMode")),
        })
    return saida


def _titulo_visual(visual):
    try:
        valor = visual["visualContainerObjects"]["title"][0]["properties"]["text"]["expr"]
    except (KeyError, IndexError, TypeError):
        return None
    lit = _literal(valor)
    return lit or None


def _texto_caixa(objs):
    """Texto de uma caixa de texto (`textbox`): parágrafos separados por quebra de linha."""
    try:
        paragrafos = objs["general"][0]["properties"]["paragraphs"]
    except (KeyError, IndexError, TypeError):
        return None
    linhas = []
    for p in paragrafos or []:
        t = "".join(r.get("value", "") for r in (p or {}).get("textRuns") or [])
        if t.strip():
            linhas.append(t.strip())
    return "\n".join(linhas) or None


def _parse_visual(vis):
    visual = vis.get("visual") or {}
    tipo = _find_visual_type(visual or vis) or "desconhecido"
    objs = visual.get("objects") or {}
    vco = visual.get("visualContainerObjects") or {}
    campos, vistos = [], set()
    estado = ((visual.get("query") or {}).get("queryState") or {})
    for papel in sorted(estado):
        for proj in (estado[papel] or {}).get("projections") or []:
            c = _campo(proj.get("field"))
            if not c or not c.get("campo"):
                continue
            chave = (c["tabela"], c["campo"], papel)
            if chave in vistos:
                if c.get("nivel"):        # outro nível da mesma hierarquia de data
                    for existente in campos:
                        if (existente["tabela"], existente["campo"], existente["papel"]) == chave:
                            niveis = existente.get("nivel") or ""
                            if c["nivel"] not in niveis.split(", "):
                                existente["nivel"] = (niveis + ", " if niveis else "") + c["nivel"]
                continue
            vistos.add(chave)
            c["papel"] = papel
            c["rotulo"] = proj.get("displayName") or proj.get("nativeQueryRef") or c["campo"]
            campos.append(c)
    ordenacao = []
    for s in (((visual.get("query") or {}).get("sortDefinition") or {}).get("sort") or []):
        c = _campo(s.get("field"))
        if c and c.get("campo"):
            ordenacao.append({"tabela": c["tabela"], "campo": c["campo"],
                              "direcao": "crescente" if s.get("direction") == "Ascending"
                              else "decrescente"})
    pos = vis.get("position") or {}
    v = {
        "id": vis.get("name"),
        "tipo": tipo,
        "titulo": _titulo_visual(visual),
        "campos": campos,
        "ordenacao": ordenacao,
        "filtros": _parse_filtros(vis),
        "oculto": bool(vis.get("isHidden")),
        "grupo": vis.get("parentGroupName"),
        "tooltip_pagina": _prop(objs, "visualTooltip", "section")
        or _prop(vco, "visualTooltip", "section"),
        "_pos": (round(pos.get("y") or 0), round(pos.get("x") or 0)),
    }
    if tipo == "slicer":
        v["segmentacao"] = {"modo": _prop(objs, "data", "mode"),
                            "cabecalho": _prop(objs, "header", "text"),
                            "sync": (visual.get("syncGroup") or vis.get("syncGroup") or {}).get("groupName")}
    elif tipo == "textbox":
        v["texto"] = _texto_caixa(objs)
    elif tipo == "actionButton":
        link = (vco.get("visualLink") or [{}])[0].get("properties") or {}
        v["botao"] = {
            "icone": _prop(objs, "icon", "shapeType"),
            "alt": _prop(vco, "general", "altText"),
            "acao": _lit(link.get("type")),
            "tooltip": _lit(link.get("tooltip")),
            "pagina_destino": _lit(link.get("navigationSection")),
            "bookmark": _lit(link.get("bookmark")),
        }
    return v


# nomes de coluna que sugerem dado pessoal (só o NOME; nunca valores)
PESSOAL_RE = re.compile(r"(e-?mail|cpf|cnpj|telefone|celular|nascimento|endere[cç]o|\brg\b)",
                        re.IGNORECASE)
TABELAS_PESSOAIS_RE = re.compile(r"(usu[aá]rio|aluno|cliente|pessoa|funcion[aá]rio|colaborador)",
                                 re.IGNORECASE)


def _coluna_pessoal(tabela, campo):
    if PESSOAL_RE.search(campo or ""):
        return True
    return bool(re.fullmatch(r"(nome|usuario|usuário|login)", (campo or "").lower())
                and TABELAS_PESSOAIS_RE.search(tabela or ""))


def _dax_referencias(dax):
    """Colunas/medidas citadas por uma expressão DAX de extensão (só nomes)."""
    limpo = _strip_dax_comments(dax)
    colunas = set()
    for tbl, col in re.findall(r"'((?:[^']|'')*)'\s*\[([^\]]+)\]", limpo):
        colunas.add("%s[%s]" % (tbl.replace("''", "'"), col))
    for tbl, col in re.findall(r"(?<![\]'\w])([A-Za-z_]\w*)\s*\[([^\]]+)\]", limpo):
        colunas.add("%s[%s]" % (tbl, col))
    sem_tabela = set(re.findall(r"(?<![\w'\]])\[([^\]]+)\]", limpo))
    return sorted(colunas), sorted(sem_tabela)


def _extensoes(report_dir):
    """Medidas definidas no próprio relatório (`definition/reportExtensions.json`)."""
    dados = _ler_json(os.path.join(report_dir, "definition", "reportExtensions.json")) or {}
    saida = []
    for ent in dados.get("entities") or []:
        for m in ent.get("measures") or []:
            dax = m.get("expression") or ""
            cols, meds = _dax_referencias(dax)
            saida.append({
                "tabela": ent.get("name"),
                "nome": m.get("name"),
                "dax": dax,
                "tipo_dado": m.get("dataType"),
                "formato": m.get("formatString"),
                "pasta": m.get("displayFolder"),
                "colunas_citadas": cols,
                "medidas_citadas": meds,
                "hash": _sha1(ent.get("name"), m.get("name"), dax, m.get("formatString") or ""),
            })
    saida.sort(key=lambda e: ((e["pasta"] or "").lower(), (e["nome"] or "").lower()))
    return saida


def _tema(report_dir, report):
    col = (report or {}).get("themeCollection") or {}
    saida = {"base": (col.get("baseTheme") or {}).get("name"),
             "personalizado": (col.get("customTheme") or {}).get("name"), "cores": []}
    if saida["personalizado"]:
        for caminho in glob.glob(os.path.join(report_dir, "StaticResources", "**",
                                              saida["personalizado"] + ".json"), recursive=True):
            tema = _ler_json(caminho) or {}
            saida["cores"] = tema.get("dataColors") or []
            break
    return saida


def _bookmarks(report_dir, ids_pagina):
    """Bookmarks do relatório. Só metadados: o estado salvo (filtros/valores) é ignorado."""
    base = os.path.join(report_dir, "definition", "bookmarks")
    lista = _ler_json(os.path.join(base, "bookmarks.json")) or {}
    ordem = [i.get("name") for i in lista.get("items") or [] if i.get("name")]
    saida = []
    for caminho in sorted(glob.glob(os.path.join(base, "*.bookmark.json"))):
        b = _ler_json(caminho) or {}
        secao = (b.get("explorationState") or {}).get("activeSection")
        opcoes = b.get("options") or {}
        saida.append({
            "id": b.get("name"),
            "nome": b.get("displayName") or b.get("name"),
            "pagina_id": secao,
            "pagina": ids_pagina.get(secao, secao),
            "visuais_alvo": list(opcoes.get("targetVisualNames") or []),
            "apenas_alvos": bool(opcoes.get("targetVisualNames")),
            "ordem": ordem.index(b.get("name")) if b.get("name") in ordem else 999,
        })
    saida.sort(key=lambda b: (b["ordem"], b["nome"] or ""))
    return saida


def _parse_report(report_dir):
    vazio = {"paginas": [], "total_visuais": 0, "filtros": [], "campos_usados": [],
             "extensoes": [], "bookmarks": [], "tema": {}, "configuracoes": {},
             "sync_groups": [], "alertas": []}
    if not report_dir or not os.path.isdir(report_dir):
        return vazio
    pages = []
    order = {}
    data = _ler_json(os.path.join(report_dir, "definition", "pages", "pages.json")) or {}
    for i, name in enumerate(data.get("pageOrder", []) or []):
        order[name] = i
    report = _ler_json(os.path.join(report_dir, "definition", "report.json")) or {}
    filtros_relatorio = _parse_filtros(report)
    extensoes = _extensoes(report_dir)
    ext_nomes = {(e["tabela"], e["nome"]) for e in extensoes}
    usados = {}

    def _usar(tabela, campo, tipo, pagina=None):
        if tabela and campo:
            tipo = "medida" if tipo == "medida" else "coluna"
            chave = (tabela, campo)
            item = usados.setdefault(chave, {"tipo": tipo, "paginas": []})
            if pagina and pagina not in item["paginas"]:
                item["paginas"].append(pagina)

    for f in filtros_relatorio:
        _usar(f["tabela"], f["campo"], f["tipo_campo"], "(relatório)")

    for path in sorted(glob.glob(os.path.join(report_dir, "definition", "pages", "*", "page.json"))):
        page = _ler_json(path)
        if page is None:
            continue
        folder = os.path.basename(os.path.dirname(path))
        nome_pagina = page.get("displayName") or folder
        tipos = {}
        grupos = []
        visuais = []
        for vpath in sorted(glob.glob(os.path.join(os.path.dirname(path), "visuals", "*", "visual.json"))):
            vis = _ler_json(vpath)
            if vis is None:
                continue
            if not vis.get("visual") and vis.get("visualGroup"):
                grupos.append({"id": vis.get("name"),
                               "nome": (vis["visualGroup"] or {}).get("displayName"),
                               "oculto": bool(vis.get("isHidden"))})
                continue
            v = _parse_visual(vis)
            tipos[v["tipo"]] = tipos.get(v["tipo"], 0) + 1
            visuais.append(v)
        visuais.sort(key=lambda v: (v["_pos"], v["id"] or ""))
        for v in visuais:
            del v["_pos"]
            for c in v["campos"]:
                _usar(c["tabela"], c["campo"], c["tipo"], nome_pagina)
            for f in v["filtros"]:
                _usar(f["tabela"], f["campo"], f["tipo_campo"], nome_pagina)
        filtros_pagina = _parse_filtros(page)
        for f in filtros_pagina:
            _usar(f["tabela"], f["campo"], f["tipo_campo"], nome_pagina)
        binding = page.get("pageBinding") or {}
        drill = None
        if binding:
            drill = {"tipo": binding.get("type"), "escopo": binding.get("referenceScope"),
                     "campos": [c for c in (
                         _campo((p or {}).get("fieldExpr")) for p in binding.get("parameters") or [])
                         if c and c.get("campo")]}
        assinatura = json.dumps([page.get("displayName"), page.get("type"),
                                 [(v["tipo"], v["titulo"], [(c["tabela"], c["campo"], c["papel"])
                                                           for c in v["campos"]])
                                  for v in visuais]],
                                sort_keys=True, ensure_ascii=False)
        pages.append({
            "qtd_grupos": len(grupos),
            "grupos": grupos,
            "id": folder,
            "nome": nome_pagina,
            "largura": page.get("width"),
            "altura": page.get("height"),
            "oculta": (page.get("visibility") == "HiddenInViewMode"),
            "tipo": page.get("type") or "Padrao",
            "exibicao": page.get("displayOption"),
            "drillthrough": drill,
            "qtd_visuais": sum(tipos.values()),
            "tipos_visuais": dict(sorted(tipos.items())),
            "ordem": order.get(folder, 999),
            "visuais": visuais,
            "filtros": filtros_pagina,
            "hash": _sha1(assinatura),
        })
    pages.sort(key=lambda p: (p["ordem"], p["nome"]))
    ids_pagina = {p["id"]: p["nome"] for p in pages}
    bookmarks = _bookmarks(report_dir, ids_pagina)

    # ---- resolução de origem (extensão do relatório x dataset) e alertas
    campos_usados = []
    for (t, c), info in sorted(usados.items()):
        campos_usados.append({"tabela": t, "campo": c, "tipo": info["tipo"],
                              "origem": "extensao" if (t, c) in ext_nomes else "dataset",
                              "paginas": info["paginas"]})
    alertas = []
    for p in pages:
        for v in p["visuais"]:
            if v["tooltip_pagina"] and v["tooltip_pagina"] not in ids_pagina:
                alertas.append({"tipo": "tooltip_inexistente", "pagina": p["nome"],
                                "visual": v["titulo"] or v["tipo"],
                                "detalhe": "aponta para a página de tooltip '%s', que não existe"
                                % v["tooltip_pagina"]})
    usados_ext = {(c["tabela"], c["campo"]) for c in campos_usados if c["origem"] == "extensao"}
    citadas = {m for e in extensoes for m in e["medidas_citadas"]}
    for e in extensoes:
        if (e["tabela"], e["nome"]) not in usados_ext and e["nome"] not in citadas:
            alertas.append({"tipo": "extensao_sem_uso_em_visual", "pagina": None, "visual": None,
                            "detalhe": "a medida de relatório '%s' não aparece em nenhum visual "
                                       "nem filtro (pode ser usada só em bookmarks ou estar "
                                       "obsoleta)" % e["nome"]})
    alvos_bookmark = {v["botao"]["bookmark"] for p in pages for v in p["visuais"]
                      if v.get("botao") and v["botao"].get("bookmark")}
    for b in bookmarks:
        if b["id"] not in alvos_bookmark:
            alertas.append({"tipo": "bookmark_sem_botao", "pagina": b["pagina"], "visual": None,
                            "detalhe": "o bookmark '%s' não é acionado por nenhum botão" % b["nome"]})
    for c in campos_usados:
        if c["tipo"] == "coluna" and _coluna_pessoal(c["tabela"], c["campo"]):
            alertas.append({"tipo": "dado_pessoal_exposto", "pagina": ", ".join(c["paginas"]),
                            "visual": None,
                            "detalhe": "a coluna %s[%s] tem nome de dado pessoal e é exibida no "
                                       "relatório" % (c["tabela"], c["campo"])})
    alts = {}
    for p in pages:
        for v in p["visuais"]:
            a = (v.get("botao") or {}).get("alt")
            if a:
                alts[a] = alts.get(a, 0) + 1
    for a, n in sorted(alts.items()):
        if n > 3:
            alertas.append({"tipo": "alt_text_repetido", "pagina": None, "visual": None,
                            "detalhe": "%d botões usam o mesmo texto alternativo '%s' (acessibilidade)"
                                       % (n, a)})
    divergentes = {}
    for p in pages:
        for f in p["filtros"]:
            if f["aplicado"] and f["condicao"]:
                divergentes.setdefault((f["tabela"], f["campo"]), {}).setdefault(
                    f["condicao"], []).append(p["nome"])
    for (t, c), conds in sorted(divergentes.items()):
        if len(conds) > 1:
            alertas.append({"tipo": "filtro_divergente_entre_paginas", "pagina": None, "visual": None,
                            "detalhe": "o filtro de %s[%s] tem condições diferentes por página: %s"
                                       % (t, c, "; ".join("%s (%s)" % (k, ", ".join(v))
                                                          for k, v in sorted(conds.items())))})
    sync = {}
    for p in pages:
        for v in p["visuais"]:
            g = (v.get("segmentacao") or {}).get("sync")
            if g:
                sync.setdefault(g, []).append(p["nome"])
    return {
        "paginas": pages,
        "total_visuais": sum(p["qtd_visuais"] for p in pages),
        "filtros": filtros_relatorio,
        "campos_usados": campos_usados,
        "extensoes": extensoes,
        "bookmarks": bookmarks,
        "tema": _tema(report_dir, report),
        "configuracoes": {k: v for k, v in (report.get("settings") or {}).items()
                          if not isinstance(v, (dict, list))},
        "sync_groups": [{"grupo": g, "paginas": sorted(set(ps))} for g, ps in sorted(sync.items())],
        "alertas": alertas,
    }


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


TIPOS = ("completo", "modelo", "relatorio_conectado")


def _tipo(sm, rp):
    """Tipo do projeto PBIP:

    - `completo`: modelo semântico local + relatório;
    - `modelo`: só o modelo semântico (sem relatório);
    - `relatorio_conectado`: só o relatório, ligado a um dataset remoto/externo
      (`definition.pbir` com `byConnection`, ou `byPath` para um modelo fora da pasta).
    """
    if sm and rp:
        return "completo"
    return "modelo" if sm else "relatorio_conectado"


def find_project(root):
    """Localiza o .pbip, o SemanticModel e o Report a partir da raiz do projeto.

    Um projeto pode ter só o `*.Report` (relatório conectado a um dataset); nesse caso
    `semantic_model` é None e o nome vem da pasta `<nome>.Report`.
    """
    pbips = sorted(glob.glob(os.path.join(root, "*.pbip")))
    sm = sorted(glob.glob(os.path.join(root, "*.SemanticModel")))
    rp = sorted(glob.glob(os.path.join(root, "*.Report")))
    if not sm and not rp:
        raise SystemExit("Nenhuma pasta *.SemanticModel ou *.Report encontrada em %s" % root)
    if sm:
        name = os.path.basename(sm[0])[:-len(".SemanticModel")]
    else:
        name = os.path.basename(rp[0])[:-len(".Report")]
    return {
        "nome": name,
        "pasta": os.path.basename(os.path.abspath(root)),
        "pbip": pbips[0] if pbips else None,
        "semantic_model": sm[0] if sm else None,
        "report": rp[0] if rp else None,
        "tipo": _tipo(bool(sm), bool(rp)),
    }


def descobrir(repo_root, projetos_dir="projetos"):
    """Lista os projetos PBIP do repositório: pares `(nome, caminho)`.

    Procura primeiro em `<repo_root>/<projetos_dir>/*/`, um projeto por
    subpasta (cada uma contendo um `*.SemanticModel` e/ou um `*.Report`). Se nenhum
    for encontrado ali, cai de volta para um único projeto na raiz do
    repositório — compatibilidade com um repositório de projeto único.
    """
    def _eh_projeto(pasta):
        return bool(glob.glob(os.path.join(pasta, "*.SemanticModel"))
                    or glob.glob(os.path.join(pasta, "*.Report")))

    base = os.path.join(repo_root, projetos_dir)
    encontrados = []
    if os.path.isdir(base):
        for nome in sorted(os.listdir(base)):
            caminho = os.path.join(base, nome)
            if os.path.isdir(caminho) and _eh_projeto(caminho):
                encontrados.append((nome, caminho))
    if not encontrados and _eh_projeto(repo_root):
        proj = find_project(repo_root)
        encontrados.append((proj["nome"], repo_root))
    return encontrados


def _dataset(proj):
    """Como o relatório se liga ao dataset: `definition.pbir` (`datasetReference`).

    Devolve só metadados de conexão (servidor, catálogo, id do modelo, modo de acesso) e,
    para relatório conectado, os nomes das tabelas do dataset que aparecem no
    `semanticModelDiagramLayout.json`. Nunca lê a pasta de cache local do Power BI nem
    dados.
    """
    saida = {"referencia": None, "servidor": None, "catalogo": None, "modelo_id": None,
             "modo_acesso": None, "seguranca": None, "caminho": None, "tabelas": []}
    rp = proj["report"]
    if not rp:
        return saida
    ref = (_ler_json(os.path.join(rp, "definition.pbir")) or {}).get("datasetReference") or {}
    if "byConnection" in ref:
        conn = ref["byConnection"] or {}
        saida["referencia"] = "byConnection"
        partes = {}
        for trecho in (conn.get("connectionString") or "").split(";"):
            if "=" in trecho:
                k, v = trecho.split("=", 1)
                partes[k.strip().lower()] = v.strip()
        saida["servidor"] = partes.get("data source")
        saida["catalogo"] = partes.get("initial catalog") or conn.get("pbiModelDatabaseName")
        saida["modelo_id"] = partes.get("semanticmodelid") or conn.get("pbiServiceModelId")
        saida["modo_acesso"] = partes.get("access mode")
        saida["seguranca"] = partes.get("integrated security")
    elif "byPath" in ref:
        saida["referencia"] = "byPath"
        saida["caminho"] = (ref["byPath"] or {}).get("path")
    if not proj["semantic_model"]:
        layout = _ler_json(os.path.join(rp, "semanticModelDiagramLayout.json")) or {}
        nomes = set()
        for diagrama in layout.get("diagrams") or []:
            for no in diagrama.get("nodes") or []:
                if no.get("nodeIndex"):
                    nomes.add(no["nodeIndex"])
        saida["tabelas"] = sorted(nomes, key=str.lower)
    return saida


def _estatisticas_relatorio(relatorio):
    return {"paginas": len(relatorio["paginas"]), "visuais": relatorio["total_visuais"],
            "extensoes": len(relatorio.get("extensoes") or []),
            "bookmarks": len(relatorio.get("bookmarks") or []),
            "alertas": len(relatorio.get("alertas") or [])}


def _extract_conectado(proj):
    """Manifesto de um relatório conectado: não há TMDL, só o que o relatório revela."""
    relatorio = _parse_report(proj["report"])
    dataset = _dataset(proj)
    fontes = []
    if dataset["catalogo"]:
        fontes.append("Dataset %s (Power BI)" % dataset["catalogo"])
    est = {"tabelas": 0, "colunas": 0, "colunas_calculadas": 0, "medidas": 0,
           "relacionamentos": 0, "relacionamentos_auto_data": 0, "tabelas_auto_data": 0,
           "parametros": 0, "perfis_rls": 0, "tabelas_dataset": len(dataset["tabelas"])}
    est.update(_estatisticas_relatorio(relatorio))
    return {
        "schema_version": SCHEMA_VERSION,
        "projeto": {
            "nome": proj["nome"], "pasta": proj["pasta"], "tipo": proj["tipo"],
            "pbip": os.path.basename(proj["pbip"]) if proj["pbip"] else None,
            "semantic_model": None,
            "report": os.path.basename(proj["report"]),
            "dataset": dataset,
            "nivel_compatibilidade": None, "culture": None, "fontes_dados": fontes,
            "inteligencia_tempo_automatica": False,
        },
        "tabelas": [], "medidas": [], "relacionamentos": [], "parametros": [],
        "perfis_rls": [], "relatorio": relatorio, "estatisticas": est,
    }


def extract(root):
    proj = find_project(root)
    if not proj["semantic_model"]:
        return _extract_conectado(proj)
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

    relatorio = _parse_report(proj["report"])
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "projeto": {
            "nome": proj["nome"],
            "pasta": proj["pasta"],
            "tipo": proj["tipo"],
            "dataset": _dataset(proj),
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
        "relatorio": relatorio,
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
        },
    }
    manifest["estatisticas"].update(_estatisticas_relatorio(relatorio))
    return manifest


def dump(manifest, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2, sort_keys=False)
        fh.write("\n")
