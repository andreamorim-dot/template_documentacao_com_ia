#!/usr/bin/env python3
"""Gera o template de um modelo de documento a partir de um .docx de referência.

O template é o **próprio arquivo de referência com o corpo esvaziado**: estilos,
fontes embutidas, tema, cabeçalho, rodapé, mídia e configuração de página são
preservados byte a byte. Nenhum texto do documento de referência é reaproveitado.

Modelos:
    tecnico  -> assets/template-tecnico.docx  (glossário de dados técnico)
    relatorio -> assets/template-relatorio.docx (documentação técnica de relatório conectado)
    negocio  -> assets/template-negocio.docx  (documentação de negócio); preserva
                também o parágrafo com o logotipo da capa

Uso:
    python3 make_template.py <referencia.docx> [--modelo tecnico|negocio|relatorio] [destino.docx]
"""

import os
import re
import shutil
import sys
import zipfile

RELS_MANTIDAS = ("styles", "settings", "fontTable", "numbering", "theme", "header", "footer")
MARCADOR = "<!--PBIDOC_BODY-->"
MODELOS = ("tecnico", "negocio", "relatorio")


def destino_padrao(modelo):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets",
                        "template-%s.docx" % modelo)


def _logo_capa(xml):
    """Primeiro parágrafo do corpo que contém uma imagem (o logotipo da capa)."""
    corpo = xml[xml.index("<w:body>") + len("<w:body>"):]
    for m in re.finditer(r"<w:p\b.*?</w:p>", corpo, re.S):
        if "<w:drawing" in m.group(0):
            return m.group(0)
        if "<w:t" in m.group(0) and re.search(r"<w:t[^>]*>[^<]+</w:t>", m.group(0)):
            break                       # já passou da capa sem achar imagem
    return ""


def _abrir_documento(xml):
    m = re.search(r"<w:document\b[^>]*>", xml)
    if not m:
        raise SystemExit("word/document.xml sem elemento <w:document>")
    return m.group(0)


def _sect_pr(xml):
    m = re.search(r"<w:sectPr\b.*?</w:sectPr>", xml, re.S)
    if m:
        return m.group(0)
    m = re.search(r"<w:sectPr\b[^>]*/>", xml)
    return m.group(0) if m else "<w:sectPr/>"


def _filtrar_rels(xml, extras=()):
    inicio = xml.index("<Relationships")
    cabecalho = xml[inicio:xml.index(">", inicio) + 1]
    mantidas = []
    for m in re.finditer(r"<Relationship\b[^>]*/>", xml):
        tag = m.group(0)
        tipo = re.search(r'Type="[^"]*/([^/"]+)"', tag)
        if tipo and (tipo.group(1) in RELS_MANTIDAS
                     or re.search(r'Id="([^"]+)"', tag).group(1) in extras):
            mantidas.append(tag)
    ordem = {t: i for i, t in enumerate(RELS_MANTIDAS)}
    mantidas.sort(key=lambda t: ordem.get(re.search(r'Type="[^"]*/([^/"]+)"', t).group(1), 99))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            + cabecalho + "".join(mantidas) + "</Relationships>")


def build(referencia, destino, modelo="tecnico"):
    if not os.path.isfile(referencia):
        raise SystemExit("Arquivo de referência não encontrado: %s" % referencia)
    os.makedirs(os.path.dirname(os.path.abspath(destino)), exist_ok=True)

    origem = zipfile.ZipFile(referencia)
    doc = origem.read("word/document.xml").decode("utf-8")
    abertura = _abrir_documento(doc)
    sect = _sect_pr(doc)
    logo = _logo_capa(doc) if modelo == "negocio" else ""
    # sem indicadores (bookmarks): o Google Docs desenha uma fita azul em cada um
    logo = re.sub(r"<w:bookmark(?:Start|End)\b[^>]*/>", "", logo)
    # o logotipo mantém a sua relação de imagem; nenhuma outra é reaproveitada
    extras = tuple(re.findall(r'r:embed="([^"]+)"', logo))
    novo_doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                + abertura + "<w:body>" + logo + MARCADOR + sect + "</w:body></w:document>")
    novos_rels = _filtrar_rels(origem.read("word/_rels/document.xml.rels").decode("utf-8"),
                               extras)

    temporario = destino + ".tmp"
    with zipfile.ZipFile(temporario, "w", zipfile.ZIP_DEFLATED) as saida:
        for info in origem.infolist():
            if info.filename == "word/document.xml":
                saida.writestr(info.filename, novo_doc.encode("utf-8"))
            elif info.filename == "word/_rels/document.xml.rels":
                saida.writestr(info.filename, novos_rels.encode("utf-8"))
            else:
                saida.writestr(info, origem.read(info.filename))
    origem.close()
    shutil.move(temporario, destino)
    return destino


def main(argv):
    argv = list(argv)
    modelo = "tecnico"
    if "--modelo" in argv:
        i = argv.index("--modelo")
        if i + 1 >= len(argv) or argv[i + 1] not in MODELOS:
            raise SystemExit("--modelo deve ser um de: %s" % ", ".join(MODELOS))
        modelo = argv[i + 1]
        del argv[i:i + 2]
    if not argv:
        raise SystemExit(__doc__)
    referencia = argv[0]
    destino = argv[1] if len(argv) > 1 else destino_padrao(modelo)
    build(referencia, destino, modelo)
    print("Template gravado em %s" % destino)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
