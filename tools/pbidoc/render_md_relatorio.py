"""Renderiza a documentação Markdown de um relatório conectado. 100% determinístico.

Mesmo conteúdo do Word (`render_docx_relatorio.py`): ambos vêm de `relatorio_view.documento`.
Arquivos: `README.md` (visão geral + índice) e um por tema, cada um com botão de retorno.
"""

import config
import relatorio_view as RV
import render_common as rc
from render_md import NOTA_GERADO, VOLTAR, _codigo, _tabela

ARQ_PRINCIPAL = "README.md"
ARQUIVOS = {
    "paginas": ("01-paginas.md", "📄 Páginas e visuais",
                "Cada página do relatório: descrição, visuais com campos, ordenação e filtros, "
                "segmentações, filtros da página e navegação."),
    "medidas": ("02-medidas.md", "📊 Medidas",
                "Medidas definidas no relatório (com DAX) e medidas do dataset usadas."),
    "campos": ("03-campos-do-dataset.md", "🗃️ Campos do dataset",
               "Tabelas e campos do dataset que o relatório usa, onde aparecem e o que "
               "significam; tabelas sem uso."),
    "filtros": ("04-filtros-e-navegacao.md", "🔎 Filtros, bookmarks e navegação",
                "Filtros de relatório e de página, sincronização de segmentações, bookmarks, "
                "drillthrough e tooltips."),
    "conexao": ("05-conexao-e-alertas.md", "🔌 Conexão, tema e alertas",
                "Conexão com o dataset, tema, configurações e alertas de qualidade."),
}


def _blocos_md(blocos, h3="###"):
    """Converte blocos neutros em Markdown. `h2` -> `##`, `h3` -> `###`."""
    L = []
    for b in blocos:
        tipo = b[0]
        if tipo == "h2":
            L += ["## " + b[1], ""]
        elif tipo == "h3":
            L += [h3 + " " + b[1], ""]
        elif tipo == "p":
            L += [b[1], ""]
        elif tipo == "nota":
            L += ["> " + b[1].replace("\n", "\n> "), ""]
        elif tipo == "kv":
            L += [_tabela(["Propriedade", "Valor"], [[k, "`%s`" % v if k in ("Projeto",) else v]
                                                       for k, v in b[1]]), ""]
        elif tipo == "tabela":
            L += [_tabela(b[1], b[2]), ""]
        elif tipo == "codigo":
            L += [_codigo(b[1], b[2] if len(b) > 2 else ""), ""]
        elif tipo == "lista":
            L += ["- " + str(i).replace("\n", " ") for i in b[1]] + [""]
    return L


def subtitulo(cfg):
    """Subtítulo do documento: o padrão do modelo semântico não serve para um relatório."""
    sub = cfg.get("subtitulo")
    return "Documentação Técnica do Relatório" if not sub or sub == config.PADRAO["subtitulo"] else sub


def _readme(man, cfg, secoes):
    L = ["# %s" % cfg["titulo"], "", "**%s**" % subtitulo(cfg), "",
         "_Atualizado em %s_" % rc.PLACEHOLDER_DATA, ""]
    L += _blocos_md(secoes["informacoes"], h3="##")
    L += ["## Índice", ""]
    L.append(_tabela(["Documento", "O que contém"], [
        ["**[%s](./%s)**" % (titulo, arq), desc] for arq, titulo, desc in ARQUIVOS.values()]))
    L += ["", "## Como esta documentação é mantida", "",
          "Extraída dos arquivos do relatório (PBIR) por `tools/pbidoc/pbidoc.py`; só os textos "
          "descritivos (`_descriptions.json`) são escritos por um assistente de IA.", "",
          NOTA_GERADO, ""]
    return "\n".join(L)


def render(man, cfg, descriptions):
    prosa = rc.Prosa(descriptions)
    doc = {chave: blocos for chave, _t, blocos in RV.documento(man, cfg, prosa)}
    arquivos = {ARQ_PRINCIPAL: _readme(man, cfg, doc)}
    for chave, (arq, titulo, _desc) in ARQUIVOS.items():
        corpo = ["# %s" % titulo.split(" ", 1)[1], "", VOLTAR, ""]
        corpo += _blocos_md(doc[chave])
        corpo += [VOLTAR, "", NOTA_GERADO, ""]
        arquivos[arq] = "\n".join(corpo)
    return arquivos
