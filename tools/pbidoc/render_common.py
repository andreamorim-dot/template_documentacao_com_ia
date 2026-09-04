"""Peças compartilhadas pelos renderizadores Markdown e DOCX."""

import datetime
import hashlib
import json
import os
import re
import unicodedata

import catalog

PLACEHOLDER_DATA = "@@PBIDOC_DATA@@"

PAPEL_ROTULO = {
    "fato": "Fato",
    "dimensao": "Dimensão",
    "auxiliar": "Auxiliar",
    "parametro": "Parâmetro",
    "medidas": "Medidas",
}

TIPO_ROTULO = {
    "string": "Texto",
    "int64": "Número inteiro",
    "double": "Número decimal",
    "decimal": "Decimal fixo",
    "dateTime": "Data/hora",
    "boolean": "Booleano",
    "binary": "Binário",
    "calculada": "Coluna calculada",
    "desconhecido": "—",
}

CARD_ROTULO = {("many", "one"): "Muitos para um (N:1)",
               ("one", "one"): "Um para um (1:1)",
               ("one", "many"): "Um para muitos (1:N)",
               ("many", "many"): "Muitos para muitos (N:N)"}

FILTRO_ROTULO = {
    "singleDirection": "Única direção",
    "bothDirections": "Ambas as direções",
    "automatic": "Automático",
    "oneDirection": "Única direção",
}


def hoje():
    return datetime.date.today().strftime("%d/%m/%Y")


def slug(texto, usados=None):
    """Âncora no padrão GitHub."""
    s = unicodedata.normalize("NFC", (texto or "").strip().lower())
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"[\s]+", "-", s) or "secao"
    if usados is not None:
        base, i = s, 1
        while s in usados:
            s = "%s-%d" % (base, i)
            i += 1
        usados.add(s)
    return s


def tipo_rotulo(tipo):
    return TIPO_ROTULO.get(tipo, tipo or "—")


def cardinalidade(rel):
    return CARD_ROTULO.get(
        (rel.get("cardinalidade_origem", "many"), rel.get("cardinalidade_destino", "one")),
        "%s para %s" % (rel.get("cardinalidade_origem"), rel.get("cardinalidade_destino")))


def filtro_rotulo(valor):
    return FILTRO_ROTULO.get(valor, valor or "—")


class Prosa:
    """Acesso somente-leitura ao `_descriptions.json`, com fallback silencioso."""

    def __init__(self, dados):
        self.objetos = (dados or {}).get("objetos", {}) or {}

    def get(self, chave, campo, padrao=""):
        entrada = self.objetos.get(chave)
        if not isinstance(entrada, dict):
            return padrao
        valor = entrada.get(campo)
        if isinstance(valor, str):
            return valor.strip() or padrao
        if valor is None:
            return padrao
        return valor

    def revisar(self, chave):
        entrada = self.objetos.get(chave)
        return bool(isinstance(entrada, dict) and entrada.get("revisar"))

    def tabela(self, nome, campo="descricao", padrao=""):
        return self.get(catalog.key_tabela(nome), campo, padrao)

    def coluna(self, tabela, col, padrao=""):
        return self.get(catalog.key_coluna(tabela, col), "descricao", padrao)

    def medida(self, tabela, nome, campo="descricao", padrao=""):
        return self.get(catalog.key_medida(tabela, nome), campo, padrao)

    def m(self, tabela, campo="resumo", padrao=""):
        return self.get(catalog.key_m(tabela), campo, padrao)

    def passo(self, tabela, passo, padrao=""):
        passos = self.get(catalog.key_m(tabela), "passos", {})
        if isinstance(passos, dict):
            v = passos.get(passo)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return padrao

    def parametro(self, nome, padrao=""):
        return self.get(catalog.key_parametro(nome), "descricao", padrao)

    def rls(self, nome, padrao=""):
        return self.get(catalog.key_rls(nome), "descricao", padrao)

    def visao_geral(self, padrao=""):
        return self.get("visao_geral", "texto", padrao)


def carregar_json(path, padrao=None):
    if path and os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (ValueError, OSError):
            return padrao
    return padrao


def salvar_json(path, dados):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def assinar(*partes):
    """Assinatura estável do conteúdo que origina a documentação."""
    h = hashlib.sha1()
    for parte in partes:
        h.update(json.dumps(parte, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def datar(conteudos, meta_path, assinatura):
    """Substitui o placeholder de data mantendo `atualizado_em` estável.

    A data só avança quando o modelo ou as descrições mudam — assim reexecutar o
    render sem alterações não gera diff no git, e gerar só um dos formatos não
    mexe na data do outro.
    """
    meta = carregar_json(meta_path, None) or {}
    agora = hoje()
    if meta.get("hash_conteudo") != assinatura:
        meta = {
            "criado_em": meta.get("criado_em") or agora,
            "atualizado_em": agora,
            "hash_conteudo": assinatura,
        }
    return ({n: c.replace(PLACEHOLDER_DATA, meta["atualizado_em"]) for n, c in conteudos.items()},
            meta)


def escrever(destino, conteudos):
    """Grava só o que mudou; devolve a lista de arquivos efetivamente escritos."""
    os.makedirs(destino, exist_ok=True)
    escritos = []
    for nome, texto in sorted(conteudos.items()):
        path = os.path.join(destino, nome)
        anterior = None
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                anterior = fh.read()
        if anterior != texto:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(texto)
            escritos.append(nome)
    return escritos
