"""Compara o manifesto novo com o anterior e diz o que precisa de prosa nova.

Saída (`changes.json`) é o **único** payload que chega ao modelo no modo incremental.
"""

import json
import os

import catalog


def _load(path):
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return None


def compute(manifest, descriptions, descrever_colunas=True, limite=None, escopo="tecnico"):
    objetos = (descriptions or {}).get("objetos", {}) or {}
    itens = catalog.build(manifest, descrever_colunas=descrever_colunas, escopo=escopo)

    pendentes, chaves_atuais = [], set()
    contagem = {"novo": 0, "alterado": 0, "pendente": 0}
    for item in itens:
        chaves_atuais.add(item["chave"])
        anterior = objetos.get(item["chave"])
        if anterior is None:
            estado = "novo"
        elif anterior.get("hash") != item["hash"]:
            estado = "alterado"
        elif not catalog.preenchido(anterior, item["tipo"]):
            estado = "pendente"
        else:
            continue
        contagem[estado] += 1
        registro = dict(item)
        registro["estado"] = estado
        pendentes.append(registro)

    # obsoleta é só a descrição que nenhum escopo usa: rodar o técnico não pode
    # apagar a prosa das páginas escrita para o documento de negócio
    validas = catalog.chaves_validas(manifest, descrever_colunas) | chaves_atuais
    removidos = sorted(k for k in objetos if k not in validas)

    truncado = False
    if limite and len(pendentes) > limite:
        ordem = {"alterado": 0, "novo": 1, "pendente": 2}
        pendentes.sort(key=lambda r: (ordem[r["estado"]], r["chave"]))
        pendentes = pendentes[:limite]
        truncado = True

    return {
        "modo": "completo" if not objetos else "incremental",
        "escopo": escopo,
        "tipo_projeto": manifest["projeto"].get("tipo") or "completo",
        "projeto": manifest["projeto"]["nome"],
        "resumo": {
            "novos": contagem["novo"],
            "alterados": contagem["alterado"],
            "pendentes": contagem["pendente"],
            "removidos": len(removidos),
            "total_a_escrever": len(pendentes),
            "truncado": truncado,
        },
        "itens": pendentes,
        "removidos": removidos,
    }


def dump(changes, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(changes, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def purge(descriptions, removidos):
    """Remove do `_descriptions.json` as entradas de objetos que não existem mais."""
    for k in removidos:
        descriptions.get("objetos", {}).pop(k, None)
    return descriptions
