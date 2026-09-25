"""Conteúdo da documentação técnica de um **relatório conectado** (sem modelo local).

Um relatório conectado (`projeto.tipo == "relatorio_conectado"`) tem só o `*.Report`, ligado
a um dataset que não está no repositório. Não há tabelas, M, relacionamentos nem RLS para
documentar; o que existe — e é documentado aqui em detalhe — é a conexão com o dataset, as
páginas, os visuais (campos, ordenação, filtros, segmentações), as medidas definidas no
próprio relatório (com DAX), os campos do dataset usados, filtros, bookmarks, navegação,
drillthrough/tooltips, tema, configurações e alertas de qualidade.

Este módulo monta um **modelo neutro de documento** — listas de blocos — que os dois
renderizadores (`render_md_relatorio.py` e `render_docx_relatorio.py`) transformam em
Markdown e em Word, de modo que os dois formatos nunca divergem. Blocos:

    ("h2", texto) ("h3", texto) ("p", texto) ("nota", texto)
    ("kv", [(rotulo, valor), ...])          pares rótulo/valor
    ("tabela", [cabecalho], [[linha], ...])
    ("codigo", texto, linguagem)
    ("lista", [texto, ...])

Política: só estrutura e regras do relatório. Valores de linhas de tabela nunca aparecem
(o extrator já descarta `expansionStates` e o estado salvo dos bookmarks); os valores que
aparecem são as **condições dos filtros**, que são regras do relatório.
"""

import catalog
from render_docx_negocio import TIPO_VISUAL, SEGMENTACOES

PENDENTE = "(descrição pendente)"

TIPO_PAGINA = {"Padrao": "Página padrão", "Tooltip": "Página de dica de ferramenta (tooltip)",
               "Drillthrough": "Página de drillthrough"}

ALERTAS = {
    "tooltip_inexistente": "Página de tooltip inexistente",
    "extensao_sem_uso_em_visual": "Medida de relatório sem uso em visual",
    "bookmark_sem_botao": "Bookmark sem botão",
    "dado_pessoal_exposto": "Coluna com nome de dado pessoal exibida",
    "alt_text_repetido": "Texto alternativo repetido",
    "filtro_divergente_entre_paginas": "Filtro divergente entre páginas",
}

ACAO_BOTAO = {"PageNavigation": "Navegação para página", "Bookmark": "Bookmark", "Back": "Voltar",
              "DrillThrough": "Drillthrough", "WebUrl": "Link externo", "QandA": "Perguntas e respostas"}


def _txt(v, padrao=PENDENTE):
    return v.strip() if isinstance(v, str) and v.strip() else padrao


ROTULO_EXTRA = {"shape": "Forma", "basicShape": "Forma", "textbox": "Caixa de texto",
                "actionButton": "Botão", "pageNavigator": "Navegador de páginas",
                "bookmarkNavigator": "Navegador de bookmarks", "image": "Imagem"}
SEM_ORDENACAO = ("card", "cardVisual", "multiRowCard", "kpi", "gauge")


def _desc(v, chave, campo="descricao"):
    """Prosa de um item; item marcado `revisar` aparece como tal em vez de 'pendente'."""
    texto = v.prosa.get(chave, campo)
    if texto:
        return texto
    return "(sem base para descrever — revisar)" if v.prosa.revisar(chave) else PENDENTE


def _tipo_visual(tipo):
    return TIPO_VISUAL.get(tipo) or ROTULO_EXTRA.get(tipo) or "Visual (%s)" % tipo


def _ref(tabela, campo):
    return "%s[%s]" % (tabela, campo)


def _campo_txt(c):
    """`Rótulo — Soma de tabela[coluna]` (rótulo só quando difere do nome do campo)."""
    base = _ref(c["tabela"], c["campo"])
    if c.get("agregacao"):
        base = "%s de %s" % (c["agregacao"], base)
    if c.get("nivel"):
        base = "%s (níveis de data: %s)" % (base, c["nivel"])
    rot = c.get("rotulo")
    if rot and rot != c["campo"] and not rot.startswith(("Soma de", "Contagem de", "Média de",
                                                         "Mín", "Máx")):
        return "%s — %s" % (rot, base)
    return base


def _filtro_txt(f):
    txt = "%s %s" % (_ref(f["tabela"], f["campo"]), f["condicao"]) if f["aplicado"] and f["condicao"] \
        else "%s (sem valor definido — o usuário escolhe)" % _ref(f["tabela"], f["campo"])
    marcas = []
    if f.get("criado_como") == "Drillthrough":
        marcas.append("drillthrough")
    if f.get("oculto"):
        marcas.append("oculto")
    if f.get("bloqueado"):
        marcas.append("bloqueado")
    return txt + (" [%s]" % ", ".join(marcas) if marcas else "")


def _decorativo(v):
    return v["tipo"] in catalog.DECORATIVOS


def _nome_visual(v):
    return v.get("titulo") or (v.get("segmentacao") or {}).get("cabecalho") or _tipo_visual(v["tipo"])


class Visao:
    """Índices reutilizados pelas seções."""

    def __init__(self, man, cfg, prosa):
        self.man, self.cfg, self.prosa = man, cfg, prosa
        self.proj = man["projeto"]
        self.rel = man["relatorio"]
        self.ds = self.proj.get("dataset") or {}
        self.paginas = self.rel["paginas"]
        self.nomes_pagina = {p["id"]: p["nome"] for p in self.paginas}
        self.extensoes = self.rel.get("extensoes") or []
        self.ext_chaves = {(e["tabela"], e["nome"]) for e in self.extensoes}
        self.usados = self.rel.get("campos_usados") or []
        self.pessoais = {(a["detalhe"]) for a in self.rel.get("alertas") or []
                         if a["tipo"] == "dado_pessoal_exposto"}

    def eh_pessoal(self, tabela, campo):
        return any(_ref(tabela, campo) in d for d in self.pessoais)


# ---------------------------------------------------------------------- seções


def secao_informacoes(v):
    p, ds, cfg, est = v.proj, v.ds, v.cfg, v.man["estatisticas"]
    blocos = [("nota", "Este projeto contém apenas o **relatório** (`%s`), conectado a um dataset "
                       "que não está no repositório. Tabelas, código DAX das medidas do dataset, "
                       "relacionamentos, RLS e consultas Power Query pertencem ao dataset e não "
                       "são documentados aqui; o que se sabe dele é o que o relatório revela "
                       "(nomes e uso dos campos)." % (p["report"] or "—"))]
    kv = [("Projeto", p["nome"]),
          ("Tipo de projeto", "Relatório conectado a dataset"),
          ("Relatório", p["report"] or "—"),
          ("Dataset (modelo semântico)", ds.get("catalogo") or "—"),
          ("Identificador do modelo", ds.get("modelo_id") or "—"),
          ("Servidor", ds.get("servidor") or "—"),
          ("Modo de acesso", ds.get("modo_acesso") or "—")]
    if ds.get("referencia") == "byPath":
        kv.append(("Modelo referenciado por caminho", ds.get("caminho") or "—"))
    if cfg.get("link_relatorio"):
        kv.append(("Link do relatório", cfg["link_relatorio"]))
    if cfg.get("frequencia_atualizacao"):
        kv.append(("Frequência de atualização", cfg["frequencia_atualizacao"]))
    blocos.append(("kv", kv))
    if cfg.get("objetivo"):
        blocos += [("h3", "Objetivo"), ("p", cfg["objetivo"].strip())]
    blocos += [("h3", "Visão geral"), ("p", _txt(v.prosa.visao_geral()))]

    paginas = v.paginas
    tipos = {}
    for pg in paginas:
        for vis in pg["visuais"]:
            tipos[vis["tipo"]] = tipos.get(vis["tipo"], 0) + 1
    dados = sum(n for t, n in tipos.items() if t not in catalog.DECORATIVOS)
    n_col = sum(1 for c in v.usados if c["tipo"] == "coluna" and c["origem"] == "dataset")
    n_med = sum(1 for c in v.usados if c["tipo"] == "medida" and c["origem"] == "dataset")
    tabelas_usadas = {c["tabela"] for c in v.usados if c["origem"] == "dataset"}
    blocos += [("h3", "O relatório em números"), ("tabela", ["Item", "Quantidade"], [
        ["Páginas", len(paginas)],
        ["  visíveis (padrão)", sum(1 for x in paginas if not x["oculta"] and x["tipo"] != "Tooltip")],
        ["  ocultas", sum(1 for x in paginas if x["oculta"])],
        ["  de tooltip", sum(1 for x in paginas if x["tipo"] == "Tooltip")],
        ["  com drillthrough", sum(1 for x in paginas if x.get("drillthrough"))],
        ["Visuais (total)", est["visuais"]],
        ["  de dados (gráficos, tabelas, cartões, segmentações)", dados],
        ["  decorativos/navegação (formas, caixas de texto, botões, navegador de páginas)",
         est["visuais"] - dados],
        ["Medidas definidas no relatório", len(v.extensoes)],
        ["Medidas do dataset usadas", n_med],
        ["Colunas do dataset usadas", n_col],
        ["Tabelas do dataset usadas", len(tabelas_usadas)],
        ["Tabelas do dataset (diagrama do relatório)", len(ds.get("tabelas") or [])],
        ["Bookmarks", len(v.rel.get("bookmarks") or [])],
        ["Alertas de qualidade", len(v.rel.get("alertas") or [])],
    ])]
    por_rotulo = {}
    for t, n in tipos.items():
        por_rotulo[_tipo_visual(t)] = por_rotulo.get(_tipo_visual(t), 0) + n
    blocos += [("h3", "Tipos de visual"),
               ("tabela", ["Tipo", "Quantidade"],
                [[r, n] for r, n in sorted(por_rotulo.items(), key=lambda x: (-x[1], x[0]))])]
    return blocos


def _tabela_visuais(pg, nomes):
    linhas = []
    for vis in pg["visuais"]:
        if _decorativo(vis) or vis["tipo"] in SEGMENTACOES:
            continue
        campos = "; ".join(_campo_txt(c) for c in vis["campos"]) or "—"
        ordem = "; ".join("%s (%s)" % (_ref(o["tabela"], o["campo"]), o["direcao"])
                          for o in vis["ordenacao"]) if vis["tipo"] not in SEM_ORDENACAO else ""
        ordem = ordem or "—"
        filtros = "; ".join(_filtro_txt(f) for f in vis["filtros"]) or "—"
        extra = []
        if vis.get("tooltip_pagina"):
            extra.append("tooltip: página '%s'" % nomes.get(vis["tooltip_pagina"], vis["tooltip_pagina"]))
        if vis.get("oculto"):
            extra.append("oculto")
        if vis.get("grupo"):
            extra.append("em grupo")
        linhas.append([_nome_visual(vis) + (" (%s)" % ", ".join(extra) if extra else ""),
                       _tipo_visual(vis["tipo"]), campos, ordem, filtros])
    return linhas


def secao_paginas(v):
    blocos = [("nota", "Uma seção por página, na ordem de navegação do relatório. Elementos "
                       "decorativos (formas, caixas de texto, botões de navegação) não são "
                       "listados individualmente; os textos escritos pelo autor aparecem em "
                       "'Textos da página'.")]
    for pg in v.paginas:
        blocos.append(("h2", pg["nome"]))
        info = [("Tipo", TIPO_PAGINA.get(pg["tipo"], pg["tipo"])),
                ("Visibilidade", "Oculta (não aparece na navegação)" if pg["oculta"] else "Visível"),
                ("Tamanho", "%s × %s (%s)" % (pg.get("largura") or "—", pg.get("altura") or "—",
                                              pg.get("exibicao") or "ajuste padrão")),
                ("Visuais", "%d (%d grupo(s))" % (pg["qtd_visuais"], pg["qtd_grupos"]))]
        if pg.get("drillthrough"):
            d = pg["drillthrough"]
            info.append(("Drillthrough", "por %s (escopo: %s)" % (
                ", ".join(_ref(c["tabela"], c["campo"]) for c in d["campos"]) or "—",
                d.get("escopo") or "página")))
        blocos.append(("kv", info))
        blocos += [("h3", "Descrição"), ("p", _txt(v.prosa.pagina(pg["nome"])))]

        textos = []
        for vis in pg["visuais"]:
            if vis.get("texto"):
                textos.append("Texto: " + vis["texto"].replace("\n", " · "))
            b = vis.get("botao") or {}
            if b.get("tooltip"):
                textos.append("Dica de botão: " + b["tooltip"])
        textos = list(dict.fromkeys(textos))
        if textos:
            blocos += [("h3", "Textos da página"), ("lista", textos)]

        linhas = _tabela_visuais(pg, v.nomes_pagina)
        if linhas:
            blocos += [("h3", "Visuais de dados"),
                       ("tabela", ["Visual", "Tipo", "Campos", "Ordenação", "Filtros do visual"],
                        linhas)]
        seg = [[vis.get("titulo") or (vis["segmentacao"].get("cabecalho")) or "—",
                _ref(vis["campos"][0]["tabela"], vis["campos"][0]["campo"]) if vis["campos"] else "—",
                vis["segmentacao"].get("modo") or "—", vis["segmentacao"].get("sync") or "—",
                "; ".join(_filtro_txt(f) for f in vis["filtros"]) or "—"]
               for vis in pg["visuais"] if vis["tipo"] in SEGMENTACOES and vis.get("segmentacao")]
        if seg:
            blocos += [("h3", "Segmentações de dados"),
                       ("tabela", ["Segmentação", "Campo", "Modo", "Grupo de sincronização",
                                   "Valor salvo/filtro"], seg)]
        if pg["filtros"]:
            blocos += [("h3", "Filtros da página"),
                       ("lista", [_filtro_txt(f) for f in pg["filtros"]])]
        nav = []
        for vis in pg["visuais"]:
            b = vis.get("botao") or {}
            if vis["tipo"] == "pageNavigator":
                nav.append("Navegador de páginas (mostra as páginas visíveis)")
            elif vis["tipo"] == "actionButton" and b.get("acao") and not b.get("tooltip"):
                dest = b.get("pagina_destino")
                if dest:
                    dest = v.nomes_pagina.get(dest, dest)
                nav.append("Botão '%s' → %s" % (ACAO_BOTAO.get(b["acao"], b["acao"]),
                                                dest or b.get("bookmark") or "ação sem destino"))
        nav = list(dict.fromkeys(nav))
        if nav:
            blocos += [("h3", "Navegação"), ("lista", nav)]
    return blocos


def _usado_em(c):
    return ", ".join(c.get("paginas") or []) or "—"


def secao_medidas(v):
    blocos = []
    if v.extensoes:
        blocos.append(("h2", "Medidas definidas no relatório"))
        blocos.append(("nota", "Medidas de relatório (`reportExtensions.json`) existem só neste "
                               "relatório: não pertencem ao dataset e o DAX abaixo é o código "
                               "real delas."))
        usos = {(c["tabela"], c["campo"]): c for c in v.usados if c["origem"] == "extensao"}
        for e in v.extensoes:
            blocos.append(("h3", "%s[%s]" % (e["tabela"], e["nome"])))
            blocos.append(("kv", [("Pasta de exibição", e.get("pasta") or "—"),
                                  ("Formato", e.get("formato") or "—"),
                                  ("Tipo de dado", e.get("tipo_dado") or "—"),
                                  ("Usada em", _usado_em(usos.get((e["tabela"], e["nome"]), {})))]))
            chave = catalog.key_medida(e["tabela"], e["nome"])
            blocos.append(("p", "**Descrição:** " + _desc(v, chave)))
            regra = v.prosa.get(chave, "regra")
            if regra:
                blocos.append(("p", "**Regra de cálculo:** " + regra))
            blocos.append(("codigo", e["dax"], "dax"))
            dep = []
            if e["medidas_citadas"]:
                dep.append("medidas: " + ", ".join(e["medidas_citadas"]))
            if e["colunas_citadas"]:
                dep.append("colunas: " + ", ".join(e["colunas_citadas"]))
            if dep:
                blocos.append(("p", "**Depende de:** " + "; ".join(dep)))
    ds_med = [c for c in v.usados if c["tipo"] == "medida" and c["origem"] == "dataset"]
    if ds_med:
        blocos.append(("h2", "Medidas do dataset usadas no relatório"))
        blocos.append(("nota", "O código DAX destas medidas está no dataset, fora deste "
                               "repositório: aqui constam apenas o nome, o significado (deduzido "
                               "do uso) e onde aparecem."))
        blocos.append(("tabela", ["Medida", "Tabela", "Descrição", "Usada em"], [
            [c["campo"], c["tabela"],
             _desc(v, catalog.key_medida(c["tabela"], c["campo"])),
             _usado_em(c)] for c in ds_med]))
    if not blocos:
        blocos.append(("p", "O relatório não usa medidas."))
    return blocos


def secao_campos(v):
    ds = [c for c in v.usados if c["origem"] == "dataset"]
    por_tabela = {}
    for c in ds:
        por_tabela.setdefault(c["tabela"], []).append(c)
    blocos = [("nota", "Campos do dataset que aparecem em visuais, segmentações e filtros. Tipos "
                       "de dado, relacionamentos e regras de cálculo não estão disponíveis "
                       "neste projeto. ⚠ marca colunas cujo nome sugere dado pessoal.")]
    for tabela in sorted(por_tabela, key=str.lower):
        blocos.append(("h2", tabela))
        linhas = []
        for c in sorted(por_tabela[tabela], key=lambda x: (x["tipo"], x["campo"].lower())):
            chave = (catalog.key_medida if c["tipo"] == "medida" else catalog.key_coluna)(
                c["tabela"], c["campo"])
            linhas.append([c["campo"] + (" ⚠" if v.eh_pessoal(c["tabela"], c["campo"]) else ""),
                           "medida" if c["tipo"] == "medida" else "coluna",
                           _desc(v, chave), _usado_em(c)])
        blocos.append(("tabela", ["Campo", "Tipo", "Descrição", "Usado em"], linhas))
    nao_usadas = [t for t in (v.ds.get("tabelas") or []) if t not in por_tabela]
    if nao_usadas:
        blocos += [("h2", "Tabelas do dataset sem uso neste relatório"),
                   ("nota", "Tabelas presentes no diagrama do relatório que nenhum visual, "
                            "segmentação ou filtro referencia (podem ser auxiliares, de "
                            "relacionamento ou de outros relatórios)."),
                   ("lista", nao_usadas)]
    return blocos


def secao_filtros_navegacao(v):
    blocos = [("h2", "Filtros do relatório")]
    if v.rel["filtros"]:
        blocos.append(("lista", [_filtro_txt(f) for f in v.rel["filtros"]]))
    else:
        blocos.append(("p", "Nenhum filtro em nível de relatório."))

    linhas = []
    for pg in v.paginas:
        for f in pg["filtros"]:
            linhas.append([pg["nome"], _ref(f["tabela"], f["campo"]), f["tipo_filtro"],
                           f["condicao"] if f["aplicado"] and f["condicao"] else "(livre)",
                           f.get("criado_como") or "—"])
    blocos.append(("h2", "Filtros por página"))
    if linhas:
        blocos.append(("tabela", ["Página", "Campo", "Tipo", "Condição", "Criado como"], linhas))
    else:
        blocos.append(("p", "Nenhuma página tem filtros próprios."))

    if v.rel.get("sync_groups"):
        blocos += [("h2", "Sincronização de segmentações"),
                   ("tabela", ["Grupo", "Páginas em que atua"],
                    [[g["grupo"], ", ".join(g["paginas"])] for g in v.rel["sync_groups"]])]

    marc = v.rel.get("bookmarks") or []
    blocos.append(("h2", "Bookmarks"))
    if marc:
        acionados = {}
        for pg in v.paginas:
            for vis in pg["visuais"]:
                b = (vis.get("botao") or {}).get("bookmark")
                if b:
                    acionados.setdefault(b, []).append("%s › %s" % (pg["nome"], _nome_visual(vis)))
        blocos.append(("tabela", ["Bookmark", "Página", "Visuais afetados", "Acionado por"], [
            [b["nome"], b["pagina"] or "—",
             "%d visual(is)" % len(b["visuais_alvo"]) if b["apenas_alvos"] else "todos",
             "; ".join(acionados.get(b["id"], [])) or "nenhum botão"] for b in marc]))
    else:
        blocos.append(("p", "O relatório não tem bookmarks."))

    drill = [p for p in v.paginas if p.get("drillthrough")]
    tips = [p for p in v.paginas if p["tipo"] == "Tooltip"]
    blocos.append(("h2", "Drillthrough e tooltips"))
    itens = ["Drillthrough: página '%s' por %s" % (
        p["nome"], ", ".join(_ref(c["tabela"], c["campo"]) for c in p["drillthrough"]["campos"]))
        for p in drill]
    for p in tips:
        usos = ["%s › %s" % (pg["nome"], _nome_visual(vis)) for pg in v.paginas
                for vis in pg["visuais"] if vis.get("tooltip_pagina") == p["id"]]
        itens.append("Tooltip: página '%s'%s" % (p["nome"], " usada por " + "; ".join(usos)
                                                  if usos else " (não usada por nenhum visual)"))
    blocos.append(("lista", itens) if itens else ("p", "Nenhuma página de drillthrough ou tooltip."))
    return blocos


def secao_conexao_alertas(v):
    ds, tema, rel = v.ds, v.rel.get("tema") or {}, v.rel
    blocos = [("h2", "Conexão com o dataset"), ("kv", [
        ("Tipo de referência", {"byConnection": "Conexão a modelo publicado (byConnection)",
                                "byPath": "Caminho local (byPath)"}.get(ds.get("referencia"), "—")),
        ("Servidor", ds.get("servidor") or "—"), ("Catálogo (dataset)", ds.get("catalogo") or "—"),
        ("Identificador do modelo", ds.get("modelo_id") or "—"),
        ("Modo de acesso", ds.get("modo_acesso") or "—"),
        ("Autenticação", ds.get("seguranca") or "—")])]
    blocos.append(("h2", "Tema"))
    blocos.append(("kv", [("Tema base", tema.get("base") or "—"),
                          ("Tema personalizado", tema.get("personalizado") or "—"),
                          ("Cores de dados", ", ".join(tema.get("cores") or []) or "—")]))
    if rel.get("configuracoes"):
        blocos += [("h2", "Configurações do relatório"),
                   ("tabela", ["Configuração", "Valor"],
                    [[k, str(val)] for k, val in sorted(rel["configuracoes"].items())])]
    blocos.append(("h2", "Alertas de qualidade"))
    if rel.get("alertas"):
        blocos.append(("nota", "Inconsistências e pontos de atenção detectados automaticamente "
                               "nos arquivos do relatório."))
        blocos.append(("tabela", ["Alerta", "Onde", "Detalhe"], [
            [ALERTAS.get(a["tipo"], a["tipo"]),
             " › ".join(x for x in (a.get("pagina"), a.get("visual")) if x) or "—", a["detalhe"]]
            for a in rel["alertas"]]))
    else:
        blocos.append(("p", "Nenhum alerta."))
    return blocos


def documento(man, cfg, prosa):
    """[(chave, titulo, blocos)] na ordem do documento."""
    v = Visao(man, cfg, prosa)
    return [
        ("informacoes", "Informações gerais", secao_informacoes(v)),
        ("paginas", "Páginas e visuais", secao_paginas(v)),
        ("medidas", "Medidas", secao_medidas(v)),
        ("campos", "Campos do dataset", secao_campos(v)),
        ("filtros", "Filtros, bookmarks e navegação", secao_filtros_navegacao(v)),
        ("conexao", "Conexão, tema e alertas", secao_conexao_alertas(v)),
    ]
