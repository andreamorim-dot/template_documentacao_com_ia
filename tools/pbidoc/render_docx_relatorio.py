"""Renderiza a documentação técnica de um relatório conectado num único .docx.

Mesmo conteúdo do Markdown (`render_md_relatorio.py`): tudo vem de
`relatorio_view.documento`. O visual é o do glossário técnico (`docx_writer.Body`); o
template é `assets/template-relatorio.docx` (gerado de
`docs/templates/Modelo - Documentacao de Relatorio.docx`) ou, na falta dele, o
`template-tecnico.docx`, que tem o mesmo casco visual.
"""

import os
import re

import docx_writer as W
import relatorio_view as RV
import render_common as rc
from render_md_relatorio import subtitulo

NOME_TEMPLATE = "template-relatorio.docx"
NOME_ALTERNATIVO = "template-tecnico.docx"


def _template_path():
    assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    proprio = os.path.join(assets, NOME_TEMPLATE)
    alternativo = os.path.join(assets, NOME_ALTERNATIVO)
    return proprio if os.path.isfile(proprio) or not os.path.isfile(alternativo) else alternativo


def _limpo(texto):
    """Remove marcações Markdown (`**negrito**`, crases) para o texto do Word."""
    return re.sub(r"`([^`]*)`", r"\1", str(texto if texto is not None else "")).replace("**", "")


def _pesos(cabecalho, linhas):
    """Larguras proporcionais ao conteúdo (limitadas), para tabelas legíveis."""
    n = len(cabecalho)
    pesos = []
    for i in range(n):
        maior = max([len(str(cabecalho[i]))] + [len(str(l[i])) for l in linhas if i < len(l)])
        pesos.append(min(max(maior, 6), 60))
    return pesos


def _bloco(b, bloco):
    tipo = bloco[0]
    if tipo == "h2":
        b.heading(2, bloco[1])
    elif tipo == "h3":
        b.heading(3, bloco[1])
    elif tipo == "p":
        m = re.match(r"\*\*(.+?):\*\*\s*(.*)$", bloco[1], re.S)
        if m:
            b.rotulo(m.group(1), _limpo(m.group(2)))
        else:
            b.paragrafo(_limpo(bloco[1]))
    elif tipo == "nota":
        b.paragrafo(_limpo(bloco[1]), italico=True, sz=20, cor=W.COR_SUAVE)
    elif tipo == "kv":
        b.tabela(["Propriedade", "Valor"], [[_limpo(k), _limpo(v)] for k, v in bloco[1]],
                 pesos=[1, 3])
    elif tipo == "tabela":
        cab, linhas = bloco[1], [[_limpo(c) for c in l] for l in bloco[2]]
        b.tabela(cab, linhas, pesos=_pesos(cab, linhas))
    elif tipo == "codigo":
        b.codigo(bloco[1])
    elif tipo == "lista":
        for item in bloco[1]:
            b.marcador(_limpo(item))


def render(man, cfg, descriptions, destino, meta):
    template = _template_path()
    if not os.path.isfile(template):
        raise SystemExit(
            "Template ausente: %s\nGere-o com:\n"
            "  python3 tools/pbidoc/make_template.py "
            "\"docs/templates/Modelo - Documentacao de Relatorio.docx\" --modelo relatorio"
            % os.path.join(os.path.dirname(template), NOME_TEMPLATE))

    W.aplicar_estilo(cfg.get("estilo_docx"))
    prosa = rc.Prosa(descriptions)
    secoes = RV.documento(man, cfg, prosa)
    b = W.Body()
    b.titulo_capa(cfg["titulo"])
    b.subtitulo_capa(subtitulo(cfg))
    b.meta_capa("Criado em %s | Atualizado em: %s"
                % (meta.get("criado_em", rc.hoje()), meta.get("atualizado_em", rc.hoje())))
    if cfg.get("elaborado_por"):
        b.meta_capa("Elaborado por: %s" % cfg["elaborado_por"])
    if cfg.get("revisado_por"):
        b.meta_capa("Revisado por: %s" % cfg["revisado_por"])
    b.meta_capa("Gerado automaticamente a partir do projeto Power BI %s"
                % (man["projeto"]["pbip"] or man["projeto"]["report"]))
    b.espaco(240)

    b.heading(1, "Índice", chave="sec_indice")
    for chave, titulo, _blocos in secoes:
        b.link_interno(titulo, "sec_" + chave)
    b.espaco(120)

    for chave, titulo, blocos in secoes:
        b.heading(1, titulo, chave="sec_" + chave, quebra_antes=True)
        for bloco in blocos:
            _bloco(b, bloco)

    nome = "%s - Documentação do Relatório.docx" % cfg["titulo"]
    os.makedirs(destino, exist_ok=True)
    caminho = os.path.join(destino, nome)
    corpo = b.xml()
    if W.inalterado(template, caminho, corpo):
        return None
    W.gravar(template, caminho, corpo)
    return nome
