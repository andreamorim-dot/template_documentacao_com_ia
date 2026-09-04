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
}

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


def build(manifest, descrever_colunas=True):
    """Lista de {chave, tipo, hash, campos, contexto} de tudo que exige prosa."""
    itens = []

    est = manifest["estatisticas"]
    ctx_geral = {
        "projeto": manifest["projeto"]["nome"],
        "fontes_dados": manifest["projeto"]["fontes_dados"],
        "estatisticas": est,
        "tabelas": [t["nome"] for t in manifest["tabelas"]],
        "paginas": [p["nome"] for p in manifest["relatorio"]["paginas"]],
    }
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
            if not descrever_colunas and not c["calculada"]:
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

    return itens


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
