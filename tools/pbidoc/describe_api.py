#!/usr/bin/env python3
"""Plano B: escreve as descrições via Claude API em vez do assistente local.

Usado apenas quando `PBIDOC_BACKEND=api` (por exemplo em CI, onde não há sessão
interativa do assistente). Requer `pip install anthropic` e `ANTHROPIC_API_KEY`.

O guia de estilo enviado como system prompt é **o mesmo arquivo** que a skill lê
(`.claude/skills/pbi-doc-md/reference/estilo.md`), então a saída sai no mesmo padrão
pelos dois caminhos.

    python3 tools/pbidoc/describe_api.py --projeto vendas --model sonnet
"""

import argparse
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ESTILO = os.path.join(RAIZ, ".claude", "skills", "pbi-doc-md", "reference", "estilo.md")

ALIASES = {
    "opus": "claude-opus-5",
    "sonnet": "claude-sonnet-5",
    "haiku": "claude-haiku-4-5",
    "fable": "claude-fable-5-1",
}

CAMPOS = ("descricao", "regra", "grao", "papel", "resumo", "texto")

ESQUEMA = {
    "type": "object",
    "properties": {
        "descricoes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chave": {"type": "string"},
                    "descricao": {"type": "string"},
                    "regra": {"type": "string"},
                    "grao": {"type": "string"},
                    "papel": {"type": "string"},
                    "resumo": {"type": "string"},
                    "texto": {"type": "string"},
                    "passos": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "nome": {"type": "string"},
                                "explicacao": {"type": "string"},
                            },
                            "required": ["nome", "explicacao"],
                            "additionalProperties": False,
                        },
                    },
                    "revisar": {"type": "boolean"},
                },
                "required": ["chave", "descricao", "regra", "grao", "papel",
                             "resumo", "texto", "passos", "revisar"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["descricoes"],
    "additionalProperties": False,
}

INSTRUCAO = (
    "Você documenta modelos de dados do Power BI. Escreva as descrições dos objetos "
    "listados a seguir seguindo LITERALMENTE o guia de estilo do system prompt.\n\n"
    "Devolva um item por objeto, com a `chave` exatamente como recebida. Preencha "
    "apenas os campos pedidos em `campos`; deixe os demais como string vazia (ou "
    "lista vazia, em `passos`). Em `passos`, use exatamente os nomes recebidos em "
    "`contexto.passos`. Se não houver base para descrever um objeto, marque "
    "`revisar: true` e deixe os campos vazios. Em itens `pagina`, descreva apenas o que "
    "os visuais listados mostram, sem inventar objetivo ou público."
)


def _lote(itens, tamanho):
    for i in range(0, len(itens), tamanho):
        yield itens[i:i + tamanho]


def _payload(item):
    """Reduz o item ao mínimo necessário — cada byte aqui é token pago."""
    return {"chave": item["chave"], "tipo": item["tipo"],
            "campos": item["campos"], "contexto": item["contexto"]}


def _normalizar(registro):
    """Converte um item da resposta para o formato de lote do `pbidoc merge`."""
    entrada = {}
    for campo in CAMPOS:
        valor = registro.get(campo)
        if isinstance(valor, str) and valor.strip():
            entrada[campo] = valor.strip()
    passos = registro.get("passos")
    if isinstance(passos, list) and passos:
        mapa = {p.get("nome"): p.get("explicacao", "") for p in passos
                if isinstance(p, dict) and p.get("nome")}
        if mapa:
            entrada["passos"] = mapa
    if registro.get("revisar"):
        entrada["revisar"] = True
    return entrada


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--projeto", required=True,
                   help="nome do projeto (subpasta de projetos/), o mesmo usado em "
                        "`pbidoc.py --projeto NOME diff`")
    p.add_argument("--model", default=os.environ.get("PBIDOC_MODEL", "sonnet"))
    p.add_argument("--lote", type=int, default=40, help="objetos por requisição")
    p.add_argument("--max-tokens", type=int, default=16000)
    args = p.parse_args(argv)

    cache = os.path.join(RAIZ, ".pbidoc-cache", args.projeto)
    changes_path = os.path.join(cache, "changes.json")

    try:
        import anthropic
    except ImportError:
        raise SystemExit("O backend de API exige a SDK oficial: pip install anthropic")

    if not os.path.isfile(changes_path):
        raise SystemExit(
            "%s ausente — rode antes: pbidoc.py --projeto %s extract && "
            "pbidoc.py --projeto %s diff" % (changes_path, args.projeto, args.projeto))
    with open(changes_path, encoding="utf-8") as fh:
        changes = json.load(fh)
    itens = changes.get("itens") or []
    if not itens:
        print("Nada a descrever.")
        return 0

    if not os.path.isfile(ESTILO):
        raise SystemExit("Guia de estilo não encontrado: %s" % ESTILO)
    with open(ESTILO, encoding="utf-8") as fh:
        estilo = fh.read()

    modelo = ALIASES.get(args.model, args.model)
    extras = {}
    if not modelo.startswith("claude-haiku-4-5"):
        extras["thinking"] = {"type": "adaptive"}

    client = anthropic.Anthropic()
    os.makedirs(cache, exist_ok=True)
    total = 0

    for indice, grupo in enumerate(_lote(itens, args.lote), 1):
        corpo = INSTRUCAO + "\n\n```json\n" + json.dumps(
            [_payload(i) for i in grupo], ensure_ascii=False, indent=1) + "\n```"
        try:
            resposta = client.messages.create(
                model=modelo,
                max_tokens=args.max_tokens,
                system=[{"type": "text", "text": estilo,
                         "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": corpo}],
                output_config={"format": {"type": "json_schema", "schema": ESQUEMA}},
                **extras,
            )
        except anthropic.NotFoundError as exc:
            raise SystemExit("Modelo inexistente (%s): %s" % (modelo, exc))
        except anthropic.RateLimitError as exc:
            raise SystemExit("Limite de requisições atingido: %s" % exc)
        except anthropic.APIStatusError as exc:
            raise SystemExit("Erro %s da API: %s" % (exc.status_code, exc))
        except anthropic.APIConnectionError as exc:
            raise SystemExit("Falha de conexão com a API: %s" % exc)

        if resposta.stop_reason == "refusal":
            print("  lote %d recusado pelo modelo; pulando" % indice, file=sys.stderr)
            continue

        texto = "".join(b.text for b in resposta.content if b.type == "text")
        try:
            dados = json.loads(texto)
        except ValueError:
            print("  lote %d devolveu JSON inválido; pulando" % indice, file=sys.stderr)
            continue

        objetos = {}
        for registro in dados.get("descricoes", []):
            chave = registro.get("chave")
            if not chave:
                continue
            entrada = _normalizar(registro)
            if entrada:
                objetos[chave] = entrada
        if not objetos:
            continue

        destino = os.path.join(cache, "patch-api-%02d.json" % indice)
        with open(destino, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"objetos": objetos}, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        total += len(objetos)
        print("  lote %d/%d: %d descrições -> %s"
              % (indice, (len(itens) + args.lote - 1) // args.lote,
                 len(objetos), os.path.relpath(destino, RAIZ)))

    print("Total: %d descrições geradas via API (%s)." % (total, modelo))
    print("Mescle com: python3 tools/pbidoc/pbidoc.py merge "
          ".pbidoc-cache/%s/patch-api-*.json --limpar" % args.projeto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
