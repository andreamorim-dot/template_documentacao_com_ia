"""Catálogo de objetos documentáveis: a ponte entre o manifesto e `_descriptions.json`.

Cada objeto tem uma **chave estável** (`medida::Medidas::qtd_respostas`), um **hash**
da sua definição e os **campos de prosa** que a skill deve preencher. Se o hash muda,
a descrição precisa ser reescrita; se não muda, ela é reaproveitada de graça.
"""

import hashlib
import json

# campos de prosa esperados por tipo de objeto
CAMPOS = {
    "visao_geral": ["texto"],
    "tabela": ["descricao", "grao", "papel"],
    "coluna": ["descricao"],
    "medida": ["descricao", "regra"],
    "m": ["resumo", "passos"],
    "parametro": ["descricao"],
    "rls": ["descricao"],
    "pagina": ["descricao"],
}

# escopos de documentação: o técnico (md + glossário .docx) e o de negócio, que
# acrescenta as páginas do relatório e as colunas exibidas nos visuais
ESCOPOS = ("tecnico", "negocio")
DECORATIVOS = ("shape", "basicShape", "textbox", "image", "actionButton", "pageNavigator",
               "bookmarkNavigator")

PAPEIS = ("fato", "dimensao", "auxiliar", "parametro", "medidas")


def _sha1(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def key_tabela(t):
    return "tabela::%s" % t


def key_coluna(t, c):
    return "coluna::%s.%s" % (t, c)


def key_medida(t, m):
    return "medida::%s::%s" % (t, m)


def key_m(t):
    return "m::%s" % t


def key_parametro(p):
    return "parametro::%s" % p


def key_rls(r):
    return "rls::%s" % r


def key_pagina(p):
    return "pagina::%s" % p


def colunas_do_relatorio(manifest):
    """{(tabela, coluna)} das colunas usadas em visuais e filtros do relatório."""
    return {(c["tabela"], c["campo"]) for c in manifest["relatorio"].get("campos_usados", [])
            if c["tipo"] == "coluna"}


def medidas_do_relatorio(manifest):
    return {(c["tabela"], c["campo"]) for c in manifest["relatorio"].get("campos_usados", [])
            if c["tipo"] == "medida"}


def build(manifest, descrever_colunas=True, escopo="tecnico"):
    """Lista de {chave, tipo, hash, campos, contexto} de tudo que exige prosa.

    `escopo="negocio"` acrescenta as páginas do relatório e força a descrição das
    colunas usadas nos visuais (o "Dicionário de dados" do documento de negócio).

    Projeto `relatorio_conectado` (relatório sem modelo local): não há tabelas/M/RLS; o
    catálogo é a visão geral, as páginas (em qualquer escopo), as medidas definidas no
    relatório (`reportExtensions.json`, com DAX) e os campos do dataset usados nos
    visuais/filtros (só nome e uso — o dataset não está no repositório).
    """
    if escopo not in ESCOPOS:
        raise ValueError("escopo inválido: %r" % escopo)
    negocio = escopo == "negocio"
    tipo_projeto = manifest["projeto"].get("tipo") or "completo"
    conectado = tipo_projeto == "relatorio_conectado"
    do_relatorio = colunas_do_relatorio(manifest) if negocio else set()
    itens = []

    est = manifest["estatisticas"]
    dataset = manifest["projeto"].get("dataset") or {}
    ctx_geral = {
        "projeto": manifest["projeto"]["nome"],
        "tipo_projeto": tipo_projeto,
        "fontes_dados": manifest["projeto"]["fontes_dados"],
        "estatisticas": est,
        "tabelas": ([t["nome"] for t in manifest["tabelas"]]
                    or list(dataset.get("tabelas") or [])),
        "paginas": [p["nome"] for p in manifest["relatorio"]["paginas"]],
    }
    if conectado:
        ctx_geral["dataset"] = dataset.get("catalogo")
        ctx_geral["medidas_do_relatorio"] = [e["nome"] for e in
                                             manifest["relatorio"].get("extensoes") or []]
    # o hash da visão geral ignora as contagens: acrescentar uma medida não deve
    # obrigar a reescrever o texto de abertura, só uma mudança estrutural deve
    assinatura_geral = {k: v for k, v in ctx_geral.items() if k != "estatisticas"}
    itens.append({
        "chave": "visao_geral",
        "tipo": "visao_geral",
        "hash": _sha1(json.dumps(assinatura_geral, sort_keys=True, ensure_ascii=False)),
        "campos": CAMPOS["visao_geral"],
        "contexto": ctx_geral,
    })

    for t in manifest["tabelas"]:
        itens.append({
            "chave": key_tabela(t["nome"]),
            "tipo": "tabela",
            "hash": t["hash"],
            "campos": CAMPOS["tabela"],
            "contexto": {
                "nome": t["nome"],
                "origem": t["origem"],
                "modo": t["modo_armazenamento"],
                "qtd_colunas": t["qtd_colunas"],
                "colunas": [c["nome"] for c in t["colunas"]],
                "descricao_tmdl": t["descricao_tmdl"],
                "papeis_validos": list(PAPEIS),
            },
        })
        if t["particoes"]:
            itens.append({
                "chave": key_m(t["nome"]),
                "tipo": "m",
                "hash": t["hash_m"],
                "campos": CAMPOS["m"],
                "contexto": {
                    "tabela": t["nome"],
                    "passos": [s["nome"] for p in t["particoes"] for s in p["passos"]],
                    "codigo_m": "\n\n".join(p["codigo_m"] for p in t["particoes"]),
                },
            })
        for c in t["colunas"]:
            if (not descrever_colunas and not c["calculada"]
                    and (t["nome"], c["nome"]) not in do_relatorio):
                continue
            itens.append({
                "chave": key_coluna(t["nome"], c["nome"]),
                "tipo": "coluna",
                "hash": c["hash"],
                "campos": CAMPOS["coluna"],
                "contexto": {
                    "tabela": t["nome"],
                    "nome": c["nome"],
                    "tipo_dado": c["tipo"],
                    "calculada": c["calculada"],
                    "dax": c["dax"],
                },
            })

    for m in manifest["medidas"]:
        itens.append({
            "chave": key_medida(m["tabela"], m["nome"]),
            "tipo": "medida",
            "hash": m["hash"],
            "campos": CAMPOS["medida"],
            "contexto": {
                "nome": m["nome"],
                "tabela": m["tabela"],
                "formato": m["formato"],
                "pasta": m["pasta"],
                "dax": m["dax"],
                "depende_de": m.get("depende_de", {}),
            },
        })

    for p in manifest["parametros"]:
        itens.append({
            "chave": key_parametro(p["nome"]),
            "tipo": "parametro",
            "hash": p["hash"],
            "campos": CAMPOS["parametro"],
            "contexto": {"nome": p["nome"], "valor": p["valor"], "tipo_dado": p["tipo"],
                         "descricao_tmdl": p["descricao_tmdl"]},
        })

    for r in manifest["perfis_rls"]:
        itens.append({
            "chave": key_rls(r["nome"]),
            "tipo": "rls",
            "hash": r["hash"],
            "campos": CAMPOS["rls"],
            "contexto": {
                "nome": r["nome"],
                "permissao_modelo": r["permissao_modelo"],
                "tabelas_filtradas": [p["tabela"] for p in r["permissoes"]],
                "dax_exemplo": r["permissoes"][0]["dax"] if r["permissoes"] else None,
            },
        })

    # medidas definidas no próprio relatório (extensões), com DAX
    existentes = {(m["tabela"], m["nome"]) for m in manifest["medidas"]}
    for e in manifest["relatorio"].get("extensoes") or []:
        if (e["tabela"], e["nome"]) in existentes:
            continue
        itens.append({
            "chave": key_medida(e["tabela"], e["nome"]),
            "tipo": "medida",
            "hash": e["hash"],
            "campos": CAMPOS["medida"],
            "contexto": {
                "nome": e["nome"], "tabela": e["tabela"], "formato": e["formato"],
                "pasta": e["pasta"], "dax": e["dax"],
                "depende_de": {"medidas": e["medidas_citadas"], "colunas": e["colunas_citadas"]},
                "origem": "medida definida no relatório (não existe no dataset)",
            },
        })

    if conectado:
        # campos do dataset usados no relatório: só há nome e uso, nunca definição
        for c in manifest["relatorio"].get("campos_usados") or []:
            if c.get("origem") == "extensao":
                continue
            eh_medida = c["tipo"] == "medida"
            chave = (key_medida if eh_medida else key_coluna)(c["tabela"], c["campo"])
            itens.append({
                "chave": chave,
                "tipo": "medida" if eh_medida else "coluna",
                "hash": _sha1("dataset|%s|%s|%s" % (c["tipo"], c["tabela"], c["campo"])),
                "campos": CAMPOS["medida" if eh_medida else "coluna"],
                "contexto": {
                    "tabela": c["tabela"], "nome": c["campo"],
                    "origem": "dataset (definição não disponível neste projeto)",
                    "tipo_dado": None, "calculada": False, "dax": None, "formato": None,
                    "usado_em": c.get("paginas") or [],
                },
            })

    if negocio or conectado:
        for p in manifest["relatorio"]["paginas"]:
            visuais = [v for v in p.get("visuais", []) if v["tipo"] not in DECORATIVOS]
            textos = [v["texto"] for v in p.get("visuais", []) if v.get("texto")]
            textos += [v["botao"]["tooltip"] for v in p.get("visuais", [])
                       if v.get("botao") and v["botao"].get("tooltip")]
            itens.append({
                "chave": key_pagina(p["nome"]),
                "tipo": "pagina",
                "hash": p.get("hash") or _sha1(p["nome"]),
                "campos": CAMPOS["pagina"],
                "contexto": {
                    "nome": p["nome"],
                    "tipo_pagina": p.get("tipo"),
                    "oculta": p.get("oculta"),
                    "visuais": [{"tipo": v["tipo"], "titulo": v["titulo"],
                                 "campos": ["%s[%s]" % (c["tabela"], c["campo"])
                                            for c in v["campos"]]}
                                for v in visuais],
                    # textos escritos pelo autor do relatório (cabeçalhos e dicas de KPI):
                    # base legítima para descrever o que a página mostra
                    "textos_do_autor": sorted(set(textos)),
                    "filtros_da_pagina": ["%s[%s] %s" % (f["tabela"], f["campo"], f["condicao"])
                                          for f in p.get("filtros", [])
                                          if f["aplicado"] and f["condicao"]],
                    "drillthrough": bool(p.get("drillthrough")),
                },
            })

    return itens


def chaves_validas(manifest, descrever_colunas=True):
    """Chaves de todos os escopos: o que estiver fora disso é descrição obsoleta."""
    return {i["chave"] for i in build(manifest, descrever_colunas, escopo="negocio")}


def preenchido(entrada, tipo):
    """True se a entrada de `_descriptions.json` já tem prosa utilizável."""
    if not isinstance(entrada, dict):
        return False
    if entrada.get("revisar"):
        return True  # marcado para revisão humana: não reprocessar
    for campo in CAMPOS.get(tipo, []):
        valor = entrada.get(campo)
        if campo == "passos":
            if isinstance(valor, dict) and valor:
                return True
            continue
        if isinstance(valor, str) and valor.strip():
            return True
    return False


def vazio(projeto):
    return {"schema_version": 1, "projeto": projeto, "objetos": {}}
