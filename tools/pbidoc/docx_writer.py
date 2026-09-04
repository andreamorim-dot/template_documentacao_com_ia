"""Geração do corpo (`<w:body>`) de um .docx no vocabulário visual do template.

As constantes de fonte e cor abaixo são a **paleta padrão** (neutra, sem marca de
nenhum cliente) usada quando um projeto não define a sua própria. Qualquer equipe
pode sobrescrevê-las por `.pbidoc.json` (globalmente ou por projeto) numa seção
`estilo_docx`, sem tocar neste arquivo — veja `aplicar_estilo()` abaixo, chamada uma
vez por `render_docx.render()`. As demais propriedades visuais (tema, cabeçalho com
logotipo, rodapé, fontes embutidas) vêm de `tools/pbidoc/assets/template.docx`,
gerado localmente a partir do documento de referência de cada equipe — veja
`make_template.py`.

Padrão de fábrica:

    Heading1  Calibri bold 20pt #1f2937    corpo     Calibri Light 12pt justificado
    Heading2  Calibri bold 16pt #2563eb    rótulo    Calibri bold 12pt
    Heading3  Calibri 14pt #374151         código    Consolas 9pt sobre #f3f4f6
"""

import hashlib
import os
import re
import zipfile

MARCADOR = "<!--PBIDOC_BODY-->"

FONTE = "Calibri"
FONTE_LEVE = "Calibri Light"
FONTE_MONO = "Consolas"

COR_TITULO = "1f2937"
COR_SUBTITULO = "2563eb"
COR_TEXTO = "111827"
COR_SUAVE = "6b7280"
COR_H3 = "374151"
COR_CODIGO_FUNDO = "f3f4f6"
COR_BORDA = "d1d5db"
COR_BRANCO = "ffffff"

# largura útil da página do template: 11909 - 1440 - 1440
LARGURA_UTIL = 9029

_CHAVES_ESTILO = ("fonte", "fonte_leve", "fonte_mono", "cor_titulo", "cor_subtitulo",
                   "cor_texto", "cor_suave", "cor_h3", "cor_codigo_fundo", "cor_borda",
                   "cor_branco")


def aplicar_estilo(estilo):
    """Sobrescreve a paleta/fontes a partir de `estilo_docx` do `.pbidoc.json`
    (mesclado global -> projeto, como o resto da configuração). Chaves aceitas:
    `fonte`, `fonte_leve`, `fonte_mono`, `cor_titulo`, `cor_subtitulo`, `cor_texto`,
    `cor_suave`, `cor_h3`, `cor_codigo_fundo`, `cor_borda`, `cor_branco`. Cores em
    hex sem `#` (ex.: `"2563eb"`). Chamar antes de montar o `Body`."""
    global FONTE, FONTE_LEVE, FONTE_MONO
    global COR_TITULO, COR_SUBTITULO, COR_TEXTO, COR_SUAVE, COR_H3
    global COR_CODIGO_FUNDO, COR_BORDA, COR_BRANCO
    if not estilo:
        return
    FONTE = estilo.get("fonte", FONTE)
    FONTE_LEVE = estilo.get("fonte_leve", FONTE_LEVE)
    FONTE_MONO = estilo.get("fonte_mono", FONTE_MONO)
    COR_TITULO = estilo.get("cor_titulo", COR_TITULO)
    COR_SUBTITULO = estilo.get("cor_subtitulo", COR_SUBTITULO)
    COR_TEXTO = estilo.get("cor_texto", COR_TEXTO)
    COR_SUAVE = estilo.get("cor_suave", COR_SUAVE)
    COR_H3 = estilo.get("cor_h3", COR_H3)
    COR_CODIGO_FUNDO = estilo.get("cor_codigo_fundo", COR_CODIGO_FUNDO)
    COR_BORDA = estilo.get("cor_borda", COR_BORDA)
    COR_BRANCO = estilo.get("cor_branco", COR_BRANCO)


def esc(texto):
    if texto is None:
        return ""
    return (str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def nome_bookmark(chave):
    """Nome de indicador válido no Word: letras/dígitos/_ e no máximo 40 caracteres."""
    base = re.sub(r"[^0-9A-Za-z_]", "_", chave or "")
    if not base or not base[0].isalpha():
        base = "b_" + base
    if len(base) > 32:
        base = base[:32]
    sufixo = hashlib.sha1((chave or "").encode("utf-8")).hexdigest()[:6]
    return "%s_%s" % (base, sufixo)


def _fontes(nome):
    return ('<w:rFonts w:ascii="{0}" w:cs="{0}" w:eastAsia="{0}" w:hAnsi="{0}"/>'.format(nome))


def rpr(fonte=None, sz=24, cor=None, negrito=False, italico=False, mono=False):
    # `fonte`/`FONTE_MONO` são lidos aqui (não como default de parâmetro) para que
    # `aplicar_estilo()` — que reatribui os globais do módulo — valha em toda chamada,
    # mesmo as que já estavam "prontas" antes da configuração ser aplicada.
    fonte = fonte if fonte is not None else FONTE_LEVE
    partes = [_fontes(FONTE_MONO if mono else fonte)]
    if negrito:
        partes.append('<w:b w:val="1"/><w:bCs w:val="1"/>')
    if italico:
        partes.append('<w:i w:val="1"/><w:iCs w:val="1"/>')
    if cor:
        partes.append('<w:color w:val="%s"/>' % cor)
    partes.append('<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (sz, sz))
    partes.append('<w:rtl w:val="0"/>')
    return "<w:rPr>%s</w:rPr>" % "".join(partes)


def run(texto, **kw):
    if texto is None:
        texto = ""
    partes = str(texto).split("\n")
    corpo = []
    for i, linha in enumerate(partes):
        if i:
            corpo.append("<w:br/>")
        corpo.append('<w:t xml:space="preserve">%s</w:t>' % esc(linha))
    return "<w:r>%s%s</w:r>" % (rpr(**kw), "".join(corpo))


class Body:
    """Acumula o XML do corpo do documento."""

    def __init__(self):
        self._partes = []
        self._bookmark_id = 0
        self._bookmarks = set()

    # ------------------------------------------------------------------ blocos
    def raw(self, xml):
        self._partes.append(xml)

    def _p(self, ppr, conteudo):
        self._partes.append("<w:p>%s%s</w:p>" % (ppr, conteudo))

    def _bookmark_xml(self, chave):
        if not chave:
            return ""
        nome = nome_bookmark(chave)
        if nome in self._bookmarks:
            return ""
        self._bookmarks.add(nome)
        self._bookmark_id += 1
        i = self._bookmark_id
        return ('<w:bookmarkStart w:colFirst="0" w:colLast="0" w:name="%s" w:id="%d"/>'
                '<w:bookmarkEnd w:id="%d"/>' % (nome, i, i))

    def paragrafo(self, texto="", fonte=None, sz=24, cor=None, negrito=False,
                  italico=False, alinhamento="both", espaco_depois=200, linha=276,
                  quebra_antes=False):
        fonte = fonte if fonte is not None else FONTE_LEVE
        cor = cor if cor is not None else COR_TEXTO
        ppr = ["<w:pPr>"]
        if quebra_antes:
            ppr.append('<w:pageBreakBefore w:val="1"/>')
        ppr.append('<w:spacing w:after="%d" w:line="%d" w:lineRule="auto"/>' % (espaco_depois, linha))
        ppr.append('<w:jc w:val="%s"/>' % alinhamento)
        ppr.append("</w:pPr>")
        self._p("".join(ppr),
                run(texto, fonte=fonte, sz=sz, cor=cor, negrito=negrito, italico=italico))

    def titulo_capa(self, texto):
        self._p('<w:pPr><w:spacing w:line="360" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr>',
                run(texto, fonte=FONTE, sz=40, cor=COR_TITULO, negrito=True))

    def subtitulo_capa(self, texto):
        self._p('<w:pPr><w:spacing w:line="360" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr>',
                run(texto, fonte=FONTE, sz=32, cor=COR_TITULO, italico=True))

    def meta_capa(self, texto):
        self._p('<w:pPr><w:spacing w:line="360" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr>',
                run(texto, fonte=FONTE, sz=20, cor=COR_SUAVE))

    def heading(self, nivel, texto, chave=None, quebra_antes=False):
        estilo = "Heading%d" % max(1, min(6, nivel))
        ppr = ["<w:pPr>", '<w:pStyle w:val="%s"/>' % estilo]
        if quebra_antes:
            ppr.append('<w:pageBreakBefore w:val="1"/>')
        if nivel == 2:
            ppr.append('<w:spacing w:line="276" w:lineRule="auto"/>')
        ppr.append("</w:pPr>")
        if nivel == 1:
            r = run(texto, fonte=FONTE, sz=40, cor=COR_TITULO, negrito=True)
        elif nivel == 2:
            r = run(texto, fonte=FONTE, sz=32, cor=COR_SUBTITULO, negrito=True)
        elif nivel == 3:
            r = run(texto, fonte=FONTE, sz=28, cor=COR_H3)
        else:
            r = run(texto, fonte=FONTE, sz=24, cor=COR_SUAVE, negrito=True)
        self._p("".join(ppr), self._bookmark_xml(chave) + r)

    def rotulo(self, rotulo, texto, sz=24):
        """Parágrafo no padrão do glossário: `**Rótulo**: texto`."""
        conteudo = (run(rotulo, fonte=FONTE, sz=sz, cor=COR_TEXTO, negrito=True)
                    + run(": ", fonte=FONTE_LEVE, sz=sz, cor=COR_TEXTO)
                    + run(texto, fonte=FONTE_LEVE, sz=sz, cor=COR_TEXTO))
        self._p('<w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/>'
                '<w:jc w:val="both"/></w:pPr>', conteudo)

    def marcador(self, texto, nivel=0):
        """Item de lista simples (recuo manual, sem depender de numbering.xml)."""
        recuo = 360 + 360 * nivel
        self._p('<w:pPr><w:spacing w:after="60" w:line="276" w:lineRule="auto"/>'
                '<w:ind w:left="%d" w:hanging="180"/><w:jc w:val="both"/></w:pPr>' % recuo,
                run("• ", fonte=FONTE_LEVE, sz=22, cor=COR_SUAVE)
                + run(texto, fonte=FONTE_LEVE, sz=22, cor=COR_TEXTO))

    def numerado(self, indice, rotulo, texto):
        self._p('<w:pPr><w:spacing w:after="60" w:line="276" w:lineRule="auto"/>'
                '<w:ind w:left="360" w:hanging="360"/><w:jc w:val="both"/></w:pPr>',
                run("%d. " % indice, fonte=FONTE, sz=22, cor=COR_SUBTITULO, negrito=True)
                + run(rotulo, fonte=FONTE, sz=22, cor=COR_TEXTO, negrito=True, mono=True)
                + run(" — ", fonte=FONTE_LEVE, sz=22, cor=COR_TEXTO)
                + run(texto, fonte=FONTE_LEVE, sz=22, cor=COR_TEXTO))

    def codigo(self, texto, sz=18):
        corpo = (texto or "").rstrip().replace("\t", "    ")
        borda = ('<w:pBdr>'
                 '<w:top w:val="single" w:sz="6" w:space="4" w:color="%(c)s"/>'
                 '<w:left w:val="single" w:sz="6" w:space="4" w:color="%(c)s"/>'
                 '<w:bottom w:val="single" w:sz="6" w:space="4" w:color="%(c)s"/>'
                 '<w:right w:val="single" w:sz="6" w:space="4" w:color="%(c)s"/>'
                 '</w:pBdr>' % {"c": COR_BORDA})
        ppr = ('<w:pPr><w:keepLines w:val="1"/>%s'
               '<w:shd w:val="clear" w:fill="%s"/>'
               '<w:spacing w:after="200" w:before="60" w:line="240" w:lineRule="auto"/>'
               '<w:jc w:val="left"/></w:pPr>' % (borda, COR_CODIGO_FUNDO))
        self._p(ppr, run(corpo, sz=sz, cor=COR_TEXTO, mono=True))

    def espaco(self, altura=120):
        self._p('<w:pPr><w:spacing w:after="%d" w:line="240" w:lineRule="auto"/></w:pPr>' % altura,
                "")

    def link_interno(self, texto, chave, sz=22):
        alvo = nome_bookmark(chave)
        conteudo = ('<w:hyperlink w:anchor="%s">%s</w:hyperlink>'
                    % (alvo, run(texto, fonte=FONTE_LEVE, sz=sz, cor=COR_SUBTITULO)))
        self._p('<w:pPr><w:spacing w:after="40" w:line="240" w:lineRule="auto"/>'
                '<w:ind w:left="240"/><w:jc w:val="left"/></w:pPr>', conteudo)

    # ------------------------------------------------------------------ tabelas
    def tabela(self, cabecalho, linhas, pesos=None, sz=18):
        n = len(cabecalho)
        pesos = pesos or [1] * n
        total = float(sum(pesos)) or 1.0
        larguras = [int(LARGURA_UTIL * p / total) for p in pesos]
        larguras[-1] = LARGURA_UTIL - sum(larguras[:-1])

        borda = "".join(
            '<w:%s w:val="single" w:sz="4" w:space="0" w:color="%s"/>' % (lado, COR_BORDA)
            for lado in ("top", "left", "bottom", "right", "insideH", "insideV"))
        xml = ['<w:tbl><w:tblPr><w:tblStyle w:val="TableNormal"/>'
               '<w:tblW w:w="%d" w:type="dxa"/>'
               '<w:tblBorders>%s</w:tblBorders>'
               '<w:tblLayout w:type="fixed"/>'
               '<w:tblCellMar><w:top w:w="60" w:type="dxa"/><w:left w:w="100" w:type="dxa"/>'
               '<w:bottom w:w="60" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar>'
               '</w:tblPr><w:tblGrid>%s</w:tblGrid>'
               % (LARGURA_UTIL, borda,
                  "".join('<w:gridCol w:w="%d"/>' % w for w in larguras))]

        xml.append('<w:tr><w:trPr><w:cantSplit w:val="1"/><w:tblHeader/></w:trPr>')
        for i, titulo in enumerate(cabecalho):
            xml.append(self._celula(titulo, larguras[i], sz=sz, negrito=True,
                                    cor=COR_BRANCO, fundo=COR_TITULO, fonte=FONTE))
        xml.append("</w:tr>")

        for j, linha in enumerate(linhas):
            fundo = "fafafa" if j % 2 else None
            xml.append("<w:tr>")
            for i in range(n):
                valor = linha[i] if i < len(linha) else ""
                mono = isinstance(valor, Mono)
                xml.append(self._celula(str(valor), larguras[i], sz=sz, fundo=fundo, mono=mono))
            xml.append("</w:tr>")
        xml.append("</w:tbl>")
        self._partes.append("".join(xml))
        self.espaco(80)

    @staticmethod
    def _celula(texto, largura, sz=18, negrito=False, cor=None, fundo=None,
                fonte=None, mono=False):
        cor = cor if cor is not None else COR_TEXTO
        fonte = fonte if fonte is not None else FONTE_LEVE
        shd = '<w:shd w:val="clear" w:fill="%s"/>' % fundo if fundo else ""
        return ('<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/>%s'
                '<w:vAlign w:val="top"/></w:tcPr>'
                '<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
                '<w:jc w:val="left"/></w:pPr>%s</w:p></w:tc>'
                % (largura, shd,
                   run(texto, fonte=fonte, sz=sz, cor=cor, negrito=negrito, mono=mono)))

    def xml(self):
        return "".join(self._partes)


class Mono(str):
    """Marca um valor de célula para ser renderizado em fonte monoespaçada."""


def corpo_de(caminho):
    """Devolve o corpo já gravado num .docx, ou None se o arquivo não existir."""
    if not os.path.isfile(caminho):
        return None
    try:
        with zipfile.ZipFile(caminho) as z:
            doc = z.read("word/document.xml").decode("utf-8")
    except (OSError, KeyError, zipfile.BadZipFile):
        return None
    inicio = doc.find("<w:body>")
    fim = doc.find("<w:sectPr")
    if inicio < 0 or fim < 0:
        return None
    return doc[inicio + len("<w:body>"):fim]


def gravar(template_path, destino, body_xml):
    """Copia o template trocando apenas o corpo de `word/document.xml`."""
    origem = zipfile.ZipFile(template_path)
    doc = origem.read("word/document.xml").decode("utf-8")
    if MARCADOR not in doc:
        origem.close()
        raise SystemExit("Template inválido: marcador %s ausente." % MARCADOR)
    doc = doc.replace(MARCADOR, body_xml)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as saida:
        for info in origem.infolist():
            if info.filename == "word/document.xml":
                saida.writestr(info.filename, doc.encode("utf-8"))
            else:
                saida.writestr(info, origem.read(info.filename))
    origem.close()
    return destino
