"""Geração do corpo (`<w:body>`) de um .docx no vocabulário visual do template.

As constantes de fonte e cor abaixo são a **paleta padrão** (neutra, sem marca de
nenhum cliente) usada quando um projeto não define a sua própria. Qualquer equipe
pode sobrescrevê-las por `.pbidoc.json` (globalmente ou por projeto) numa seção
`estilo_docx`, sem tocar neste arquivo — veja `aplicar_estilo()` abaixo, chamada uma
vez por `render_docx.render()`. As demais propriedades visuais (tema, cabeçalho com
logotipo, rodapé, fontes embutidas) vêm de `tools/pbidoc/assets/template-tecnico.docx`
e `template-negocio.docx`, gerados localmente a partir dos documentos-modelo de
cada equipe (`docs/templates/`) — veja `make_template.py`.

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

# Documento de negócio: o modelo traz Lato embutida e um verde de marca; são o padrão
# do modelo, e também configuráveis (`fonte_neg`, `fonte_neg_leve`, `cor_neg_*`).
FONTE_NEG = "Lato"
FONTE_NEG_LEVE = "Lato Light"
COR_NEG_TITULO = "38761d"       # Heading1 do modelo de negócio
COR_NEG_DESTAQUE = "76b900"     # Heading2, título da capa e subtítulos em parágrafo
FONTE_TOC = "Arial"
PREENCHER = "PREENCHER"

_CHAVES_ESTILO = ("fonte", "fonte_leve", "fonte_mono", "cor_titulo", "cor_subtitulo",
                   "cor_texto", "cor_suave", "cor_h3", "cor_codigo_fundo", "cor_borda",
                   "cor_branco", "fonte_neg", "fonte_neg_leve", "cor_neg_titulo",
                   "cor_neg_destaque", "fonte_toc")


def aplicar_estilo(estilo):
    """Sobrescreve a paleta/fontes a partir de `estilo_docx` do `.pbidoc.json`
    (mesclado global -> projeto, como o resto da configuração). Chaves aceitas:
    `fonte`, `fonte_leve`, `fonte_mono`, `cor_titulo`, `cor_subtitulo`, `cor_texto`,
    `cor_suave`, `cor_h3`, `cor_codigo_fundo`, `cor_borda`, `cor_branco` e, para o
    documento de negócio, `fonte_neg`, `fonte_neg_leve`, `fonte_toc`, `cor_neg_titulo`,
    `cor_neg_destaque`. Cores em hex sem `#` (ex.: `"2563eb"`). Chamar antes de montar o `Body`."""
    global FONTE, FONTE_LEVE, FONTE_MONO
    global COR_TITULO, COR_SUBTITULO, COR_TEXTO, COR_SUAVE, COR_H3
    global COR_CODIGO_FUNDO, COR_BORDA, COR_BRANCO
    global FONTE_NEG, FONTE_NEG_LEVE, COR_NEG_TITULO, COR_NEG_DESTAQUE, FONTE_TOC
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
    FONTE_NEG = estilo.get("fonte_neg", FONTE_NEG)
    FONTE_NEG_LEVE = estilo.get("fonte_neg_leve", FONTE_NEG_LEVE)
    COR_NEG_TITULO = estilo.get("cor_neg_titulo", COR_NEG_TITULO)
    COR_NEG_DESTAQUE = estilo.get("cor_neg_destaque", COR_NEG_DESTAQUE)
    FONTE_TOC = estilo.get("fonte_toc", FONTE_TOC)


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


def rpr(fonte=None, sz=24, cor=None, negrito=False, italico=False, mono=False,
        realce=None):
    # defaults lidos aqui (não no `def`) para `aplicar_estilo()` valer em toda chamada
    fonte = fonte if fonte is not None else FONTE_LEVE
    partes = [_fontes(FONTE_MONO if mono else fonte)]
    if negrito:
        partes.append('<w:b w:val="1"/><w:bCs w:val="1"/>')
    if italico:
        partes.append('<w:i w:val="1"/><w:iCs w:val="1"/>')
    if cor:
        partes.append('<w:color w:val="%s"/>' % cor)
    partes.append('<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (sz, sz))
    if realce:
        partes.append('<w:highlight w:val="%s"/>' % realce)
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
    """Acumula o XML do corpo do documento (vocabulário do glossário técnico)."""

    def cor_cabecalho_tabela(self):
        return COR_TITULO

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
                                    cor=COR_BRANCO, fundo=self.cor_cabecalho_tabela(), fonte=FONTE))
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


# ------------------------------------------------------------ documento de negócio


class BodyNegocio(Body):
    """Vocabulário do modelo "Documentação de Negócio" (fonte/cores: FONTE_NEG*, COR_NEG_*).

    Os títulos usam só `pStyle` (a formatação vem do `styles.xml` do template);
    o corpo é Lato 11 pt justificado e as listas usam os marcadores do
    `numbering.xml` do próprio modelo (numId 1, 2 e 3).
    """

    def cor_cabecalho_tabela(self):
        return COR_NEG_TITULO

    def __init__(self):
        super().__init__()
        self._sumario = []

    def _r(self, texto, negrito=False, cor=None, sz=None, fonte=None, realce=None,
           italico=False, mono=False):
        fonte = fonte if fonte is not None else FONTE_NEG
        partes = [_fontes(FONTE_MONO if mono else fonte)]
        if negrito:
            partes.append('<w:b w:val="1"/><w:bCs w:val="1"/>')
        if italico:
            partes.append('<w:i w:val="1"/><w:iCs w:val="1"/>')
        if cor:
            partes.append('<w:color w:val="%s"/>' % cor)
        if sz:
            partes.append('<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (sz, sz))
        if realce:
            partes.append('<w:highlight w:val="%s"/>' % realce)
        partes.append('<w:rtl w:val="0"/>')
        corpo = []
        for i, linha in enumerate(str(texto or "").split("\n")):
            if i:
                corpo.append("<w:br/>")
            corpo.append('<w:t xml:space="preserve">%s</w:t>' % esc(linha))
        return "<w:r><w:rPr>%s</w:rPr>%s</w:r>" % ("".join(partes), "".join(corpo))

    def pendente_run(self, oque, fonte=None, sz=None):
        """Marcador pesquisável para o que não pode ser extraído do PBIP."""
        fonte = fonte if fonte is not None else FONTE_NEG
        return self._r("[%s: %s]" % (PREENCHER, oque), negrito=True, realce="yellow",
                       fonte=fonte, sz=sz)

    def _conteudo(self, partes, fonte=None, sz=None, negrito=False):
        """`partes`: texto, ou lista de str / ("pendente", oque) / ("negrito", texto)."""
        fonte = fonte if fonte is not None else FONTE_NEG
        if isinstance(partes, tuple) and partes and partes[0] in ("pendente", "negrito", "mono"):
            partes = [partes]
        elif not isinstance(partes, (list, tuple)):
            partes = [partes]
        xml = []
        for p in partes:
            if isinstance(p, tuple) and p[0] == "pendente":
                xml.append(self.pendente_run(p[1], fonte=fonte, sz=sz))
            elif isinstance(p, tuple) and p[0] == "negrito":
                xml.append(self._r(p[1], negrito=True, fonte=fonte, sz=sz))
            elif isinstance(p, tuple) and p[0] == "mono":
                xml.append(self._r(p[1], mono=True, sz=sz or 20))
            else:
                xml.append(self._r(p, negrito=negrito, fonte=fonte, sz=sz))
        return "".join(xml)

    # ------------------------------------------------------------------ capa
    def titulo_capa(self, texto):
        self._p('<w:pPr><w:rPr/></w:pPr>', "")
        self._p('<w:pPr><w:rPr/></w:pPr>',
                self._r(texto, negrito=True, cor=COR_NEG_DESTAQUE, sz=40))
        self._p('<w:pPr><w:rPr/></w:pPr>', "")

    def sumario(self):
        """Reserva o lugar do sumário; preenchido em `xml()` com os títulos do documento."""
        self._partes.append(None)

    # ------------------------------------------------------------------ títulos
    def heading(self, nivel, texto, chave=None, quebra_antes=False):
        nivel = max(1, min(6, nivel))
        chave = chave or "neg_h%d_%d_%s" % (nivel, len(self._sumario), texto)
        ppr = ['<w:pPr><w:pStyle w:val="Heading%d"/>' % nivel]
        if quebra_antes:
            ppr.append('<w:pageBreakBefore w:val="1"/>')
        ppr.append("<w:rPr/></w:pPr>")
        marca = self._bookmark_xml(chave)
        if marca:
            self._sumario.append((nivel, texto, nome_bookmark(chave)))
        self._p("".join(ppr),
                marca + '<w:r><w:rPr><w:rtl w:val="0"/></w:rPr>'
                        '<w:t xml:space="preserve">%s</w:t></w:r>' % esc(texto))

    def destaque(self, texto):
        """Subtítulo em parágrafo (ex.: "Ferramenta de BI"), Lato bold 12 pt verde."""
        self._p('<w:pPr><w:spacing w:after="200" w:lineRule="auto"/><w:jc w:val="both"/>'
                '<w:rPr/></w:pPr>',
                self._r(texto, negrito=True, cor=COR_NEG_DESTAQUE, sz=24))

    # ------------------------------------------------------------------ corpo
    def paragrafo(self, partes="", negrito=False, italico=False, sz=None, **_):
        if italico:
            conteudo = self._r(partes, italico=True, sz=sz)
        else:
            conteudo = self._conteudo(partes, sz=sz, negrito=negrito)
        self._p('<w:pPr><w:spacing w:after="200" w:lineRule="auto"/><w:jc w:val="both"/>'
                '<w:rPr/></w:pPr>', conteudo)

    def rotulo(self, rotulo, partes, sz=None):
        """`**Rótulo**: texto` em Lato, como "Área de Negócio: …" no modelo."""
        self._p('<w:pPr><w:spacing w:after="200" w:lineRule="auto"/><w:jc w:val="both"/>'
                '<w:rPr/></w:pPr>',
                self._r(rotulo, negrito=True, sz=sz) + self._r(": ", sz=sz)
                + self._conteudo(partes, sz=sz))

    def item(self, partes, nivel=0, num_id=3, rotulo=None, leve=False):
        """Item de lista com marcador do `numbering.xml` do template."""
        fonte = FONTE_NEG_LEVE if leve else FONTE_NEG
        sz = 24 if leve else None
        recuo = 720 + 720 * nivel
        conteudo = ""
        if rotulo:
            conteudo += self._r(rotulo + ": ", negrito=True, fonte=fonte, sz=sz)
        conteudo += self._conteudo(partes, fonte=fonte, sz=sz)
        self._p('<w:pPr><w:numPr><w:ilvl w:val="%d"/><w:numId w:val="%d"/></w:numPr>'
                '<w:spacing w:after="120" w:lineRule="auto"/>'
                '<w:ind w:left="%d" w:hanging="360"/><w:jc w:val="both"/><w:rPr/></w:pPr>'
                % (nivel, num_id, recuo), conteudo)

    def vazio(self):
        self._p('<w:pPr><w:rPr/></w:pPr>', "")

    # ------------------------------------------------------------------ sumário
    def _sumario_xml(self):
        if not self._sumario:
            return ""
        estilo = ('<w:rFonts w:ascii="{f}" w:cs="{f}" w:eastAsia="{f}" w:hAnsi="{f}"/>{b}'
                  '<w:color w:val="000000"/><w:sz w:val="22"/><w:szCs w:val="22"/>'
                  '<w:u w:val="none"/>')
        paras = []
        n = len(self._sumario)
        for i, (nivel, texto, alvo) in enumerate(self._sumario):
            b = '<w:b w:val="1"/><w:bCs w:val="1"/>' if nivel == 1 else ""
            rpr_ = estilo.format(f=FONTE_TOC, b=b)
            ind = '<w:ind w:left="%d" w:firstLine="0"/>' % (360 * (nivel - 1)) if nivel > 1 else ""
            inicio = ""
            if i == 0:
                inicio = ('<w:r><w:fldChar w:fldCharType="begin"/>'
                          '<w:instrText xml:space="preserve"> TOC \\h \\u \\z \\n \\t '
                          '&quot;Heading 1,1,Heading 2,2,Heading 3,3,&quot;</w:instrText>'
                          '<w:fldChar w:fldCharType="separate"/></w:r>')
            fim = '<w:r><w:fldChar w:fldCharType="end"/></w:r>' if i == n - 1 else ""
            paras.append(
                '<w:p><w:pPr><w:widowControl w:val="0"/>'
                '<w:spacing w:before="60" w:line="240" w:lineRule="auto"/>%s</w:pPr>'
                '%s<w:hyperlink w:anchor="%s"><w:r><w:rPr>%s<w:rtl w:val="0"/></w:rPr>'
                '<w:t xml:space="preserve">%s</w:t></w:r></w:hyperlink>%s</w:p>'
                % (ind, inicio, alvo, rpr_, esc(texto), fim))
        return ('<w:sdt><w:sdtPr><w:docPartObj><w:docPartGallery w:val="Table of Contents"/>'
                '<w:docPartUnique w:val="1"/></w:docPartObj></w:sdtPr><w:sdtContent>%s'
                '</w:sdtContent></w:sdt>' % "".join(paras))

    def xml(self):
        toc = self._sumario_xml()
        return "".join(toc if p is None else p for p in self._partes)


class Mono(str):
    """Marca um valor de célula para ser renderizado em fonte monoespaçada."""


def documento(template_path, body_xml):
    """`word/document.xml` final: o do template com o marcador trocado pelo corpo."""
    with zipfile.ZipFile(template_path) as z:
        doc = z.read("word/document.xml").decode("utf-8")
    if MARCADOR not in doc:
        raise SystemExit("Template inválido: marcador %s ausente." % MARCADOR)
    return doc.replace(MARCADOR, body_xml)


def inalterado(template_path, destino, body_xml):
    """True se `destino` já tem exatamente este conteúdo (evita blob novo no git)."""
    if not os.path.isfile(destino):
        return False
    try:
        with zipfile.ZipFile(destino) as z:
            atual = z.read("word/document.xml").decode("utf-8")
    except (OSError, KeyError, zipfile.BadZipFile):
        return False
    return atual == documento(template_path, body_xml)


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
