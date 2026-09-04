"""Renderiza a documentação completa num único .docx, no template visual de referência."""

import os
import re

import catalog
import docx_writer as W
import render_common as rc

PENDENTE = "(descrição pendente)"
NOME_TEMPLATE = "template.docx"


def _template_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", NOME_TEMPLATE)


def _txt(valor):
    return valor.strip() if valor and str(valor).strip() else PENDENTE


def _uma_linha(valor):
    return re.sub(r"\s*\n\s*", " ", str(valor or "")).strip() or "—"


def _objetos_origem(origem):
    origem = origem or {}
    if origem.get("objetos_sql"):
        return ", ".join(origem["objetos_sql"])
    if origem.get("objeto"):
        return "%s.%s" % (origem.get("schema") or "", origem["objeto"])
    return "—"


# ------------------------------------------------------------------------- seções


def _capa(b, man, cfg, meta):
    b.titulo_capa(cfg["titulo"])
    b.subtitulo_capa(cfg["subtitulo"])
    b.meta_capa("Criado em %s | Atualizado em: %s"
                % (meta.get("criado_em", rc.hoje()), meta.get("atualizado_em", rc.hoje())))
    if cfg.get("elaborado_por"):
        b.meta_capa("Elaborado por: %s" % cfg["elaborado_por"])
    if cfg.get("revisado_por"):
        b.meta_capa("Revisado por: %s" % cfg["revisado_por"])
    b.meta_capa("Gerado automaticamente a partir do projeto Power BI %s"
                % (man["projeto"]["pbip"] or man["projeto"]["semantic_model"]))
    b.espaco(240)


def _objetivo(b, cfg):
    b.heading(1, "Objetivo", chave="sec_objetivo")
    texto = cfg.get("objetivo") or (
        "Este documento descreve o modelo de dados do projeto Power BI, para que as regras de "
        "negócio, a origem dos dados e os cálculos aplicados sejam compreendidos da mesma forma "
        "por todas as pessoas envolvidas. O conteúdo é gerado automaticamente a partir dos "
        "arquivos do projeto e acompanha cada alteração publicada.")
    b.paragrafo(texto)


def _informacoes(b, man, cfg):
    b.heading(1, "Informações gerais", chave="sec_infos")
    proj = man["projeto"]
    est = man["estatisticas"]
    linhas = [
        ["Projeto", W.Mono(proj["nome"])],
        ["Modelo semântico", W.Mono(proj["semantic_model"] or "—")],
        ["Relatório", W.Mono(proj["report"] or "—")],
        ["Fontes de dados", ", ".join(proj["fontes_dados"]) or "—"],
        ["Idioma do modelo", proj["culture"] or "—"],
        ["Nível de compatibilidade", str(proj["nivel_compatibilidade"] or "—")],
    ]
    if cfg.get("link_relatorio"):
        linhas.append(["Link do relatório", cfg["link_relatorio"]])
    if cfg.get("frequencia_atualizacao"):
        linhas.append(["Frequência de atualização", cfg["frequencia_atualizacao"]])
    b.tabela(["Propriedade", "Valor"], linhas, pesos=[1, 2])

    b.heading(3, "O modelo em números")
    b.tabela(["Item", "Quantidade"], [
        ["Tabelas", str(est["tabelas"])],
        ["Colunas", str(est["colunas"])],
        ["Colunas calculadas", str(est["colunas_calculadas"])],
        ["Medidas DAX", str(est["medidas"])],
        ["Relacionamentos", str(est["relacionamentos"])],
        ["Parâmetros do Power Query", str(est["parametros"])],
        ["Perfis de segurança (RLS)", str(est["perfis_rls"])],
        ["Páginas do relatório", str(est["paginas"])],
        ["Visuais no relatório", str(est["visuais"])],
    ], pesos=[3, 1])

    if man["relatorio"]["paginas"]:
        b.heading(3, "Páginas do relatório")
        b.tabela(["Página", "Dimensões", "Visuais", "Principais tipos de visual"],
                 [[p["nome"], "%d × %d" % (p["largura"] or 0, p["altura"] or 0),
                   str(p["qtd_visuais"]),
                   ", ".join("%s (%d)" % (t, n) for t, n in
                             sorted(p["tipos_visuais"].items(), key=lambda kv: (-kv[1], kv[0]))[:4])]
                  for p in man["relatorio"]["paginas"]], pesos=[2, 1, 1, 4])


def _indice(b, man):
    b.heading(1, "Índice", chave="sec_indice", quebra_antes=True)
    b.paragrafo("Clique em qualquer item para ir direto à seção correspondente.",
                italico=True, cor=W.COR_SUAVE, sz=20)

    b.heading(3, "Seções")
    for rotulo, chave in (("Objetivo", "sec_objetivo"),
                          ("Informações gerais", "sec_infos"),
                          ("Visão geral do modelo", "sec_visao"),
                          ("Modelo relacional", "sec_modelo"),
                          ("Tabelas", "sec_tabelas"),
                          ("Medidas", "sec_medidas"),
                          ("Queries M (Power Query)", "sec_queries"),
                          ("Segurança em nível de linha (RLS)", "sec_rls")):
        b.link_interno(rotulo, chave)

    b.heading(3, "Tabelas")
    for t in man["tabelas"]:
        b.link_interno(t["nome"], catalog.key_tabela(t["nome"]))

    b.heading(3, "Medidas")
    for m in man["medidas"]:
        b.link_interno("%s  (%s)" % (m["nome"], m["tabela"]),
                       catalog.key_medida(m["tabela"], m["nome"]))


def _visao_geral(b, prosa):
    b.heading(1, "Visão geral do modelo", chave="sec_visao", quebra_antes=True)
    for bloco in _txt(prosa.visao_geral()).split("\n\n"):
        b.paragrafo(bloco.strip())


def _modelo_relacional(b, man):
    b.heading(1, "Modelo relacional", chave="sec_modelo", quebra_antes=True)
    b.paragrafo("O modelo possui %d relacionamentos entre %d tabelas. A tabela abaixo lista "
                "origem, destino, cardinalidade e direção de filtro de cada um."
                % (man["estatisticas"]["relacionamentos"], man["estatisticas"]["tabelas"]))
    b.tabela(["Origem", "Destino", "Cardinalidade", "Filtro cruzado", "Estado"],
             [[W.Mono("%s[%s]" % (r["tabela_origem"], r["coluna_origem"])),
               W.Mono("%s[%s]" % (r["tabela_destino"], r["coluna_destino"])),
               rc.cardinalidade(r),
               rc.filtro_rotulo(r["filtro_cruzado"]),
               "Ativo" if r["ativo"] else "Inativo"]
              for r in man["relacionamentos"]], pesos=[3, 3, 2, 2, 1])

    est = man["estatisticas"]
    bidir = sum(1 for r in man["relacionamentos"] if r["filtro_cruzado"] == "bothDirections")
    inativos = [r for r in man["relacionamentos"] if not r["ativo"]]
    b.heading(3, "Pontos de atenção")
    b.marcador("Filtro cruzado bidirecional em %d de %d relacionamentos. Filtros bidirecionais "
               "propagam contexto nos dois sentidos e podem gerar ambiguidade ou impacto de "
               "desempenho." % (bidir, est["relacionamentos"]))
    if inativos:
        b.marcador("Relacionamentos inativos (%d): %s. Só entram em vigor dentro de CALCULATE "
                   "com USERELATIONSHIP."
                   % (len(inativos), "; ".join("%s[%s] → %s[%s]"
                                               % (r["tabela_origem"], r["coluna_origem"],
                                                  r["tabela_destino"], r["coluna_destino"])
                                               for r in inativos)))
    else:
        b.marcador("Nenhum relacionamento inativo.")
    if est["tabelas_auto_data"]:
        b.marcador("O Power BI gerou %d tabelas de data automáticas e %d relacionamentos "
                   "correspondentes, omitidos deste documento por não terem significado de "
                   "negócio. Para eliminá-los, desative Opções → Carregar dados → Data/hora "
                   "automática." % (est["tabelas_auto_data"], est["relacionamentos_auto_data"]))


def _tabelas(b, man, prosa):
    b.heading(1, "Tabelas", chave="sec_tabelas", quebra_antes=True)
    b.paragrafo("As %d tabelas do modelo, com origem, grão e dicionário de colunas."
                % man["estatisticas"]["tabelas"])
    b.tabela(["Tabela", "Papel", "Colunas", "Descrição"],
             [[W.Mono(t["nome"]),
               rc.PAPEL_ROTULO.get(prosa.tabela(t["nome"], "papel"),
                                   prosa.tabela(t["nome"], "papel") or "—"),
               str(t["qtd_colunas"]),
               _uma_linha(prosa.tabela(t["nome"], "descricao", PENDENTE))]
              for t in man["tabelas"]], pesos=[3, 2, 1, 6])

    for t in man["tabelas"]:
        origem = t["origem"] or {}
        b.heading(2, t["nome"], chave=catalog.key_tabela(t["nome"]))
        b.rotulo("Descrição", _txt(prosa.tabela(t["nome"], "descricao")))
        b.rotulo("Grão", _txt(prosa.tabela(t["nome"], "grao")))
        b.rotulo("Papel no modelo", rc.PAPEL_ROTULO.get(prosa.tabela(t["nome"], "papel"),
                                                        prosa.tabela(t["nome"], "papel") or "—"))
        b.rotulo("Origem", "%s — %s" % (origem.get("tipo") or "—", _objetos_origem(origem)))
        b.rotulo("Modo de armazenamento", t["modo_armazenamento"] or "—")
        b.rotulo("Atualização incremental",
                 "Sim" if origem.get("atualizacao_incremental") else "Não")
        if prosa.revisar(catalog.key_tabela(t["nome"])):
            b.rotulo("Ponto de atenção",
                     "Descrição marcada para revisão humana — validar antes de publicar.")
        if t["colunas"]:
            b.heading(3, "Colunas de %s" % t["nome"])
            b.tabela(["Coluna", "Tipo", "Origem", "Descrição"],
                     [[W.Mono(c["nome"]), rc.tipo_rotulo(c["tipo"]),
                       "Calculada" if c["calculada"] else (c["coluna_origem"] or "—"),
                       _uma_linha(prosa.coluna(t["nome"], c["nome"], PENDENTE))]
                      for c in t["colunas"]], pesos=[3, 2, 2, 5])
        calculadas = [c for c in t["colunas"] if c["calculada"]]
        if calculadas:
            b.heading(3, "Colunas calculadas de %s" % t["nome"])
            for c in calculadas:
                b.heading(4, c["nome"])
                b.rotulo("Descrição", _txt(prosa.coluna(t["nome"], c["nome"])))
                b.codigo(c["dax"])


def _medidas(b, man, prosa):
    b.heading(1, "Medidas", chave="sec_medidas", quebra_antes=True)
    b.paragrafo("As %d medidas DAX do modelo, com a regra de negócio que cada uma implementa."
                % man["estatisticas"]["medidas"])
    por_tabela = {}
    for m in man["medidas"]:
        por_tabela.setdefault(m["tabela"], []).append(m)
    for tabela in sorted(por_tabela):
        b.heading(2, "Medidas de %s" % tabela)
        for m in por_tabela[tabela]:
            chave = catalog.key_medida(tabela, m["nome"])
            b.heading(3, m["nome"], chave=chave)
            b.rotulo("Descrição", _txt(prosa.medida(tabela, m["nome"], "descricao")))
            b.rotulo("Regra de cálculo", _txt(prosa.medida(tabela, m["nome"], "regra")))
            b.rotulo("Formato", m["formato"] or "—")
            if m["pasta"]:
                b.rotulo("Pasta de exibição", m["pasta"])
            dep = m.get("depende_de") or {}
            partes = []
            if dep.get("medidas"):
                partes.append("medidas: " + ", ".join("[%s]" % d for d in dep["medidas"]))
            if dep.get("colunas"):
                partes.append("colunas: " + ", ".join(dep["colunas"]))
            b.rotulo("Depende de", "; ".join(partes) if partes else "nenhuma referência direta")
            if prosa.revisar(chave):
                b.rotulo("Ponto de atenção",
                         "Descrição marcada para revisão humana — validar antes de publicar.")
            b.rotulo("Expressão DAX", "")
            b.codigo(m["dax"])


def _queries(b, man, prosa):
    b.heading(1, "Queries M (Power Query)", chave="sec_queries", quebra_antes=True)
    b.paragrafo("Código Power Query de cada tabela e os tratamentos aplicados aos dados entre a "
                "origem e o modelo.")

    if man["parametros"]:
        b.heading(2, "Parâmetros")
        b.tabela(["Parâmetro", "Tipo", "Valor atual", "Função"],
                 [[W.Mono(p["nome"]), p["tipo"] or "—", W.Mono(_uma_linha(p["valor"])),
                   _uma_linha(prosa.parametro(p["nome"], p["descricao_tmdl"] or PENDENTE))]
                  for p in man["parametros"]], pesos=[3, 2, 3, 5])

    incrementais = [t for t in man["tabelas"]
                    if (t["origem"] or {}).get("atualizacao_incremental")]
    if incrementais:
        b.heading(2, "Atualização incremental")
        b.paragrafo("As tabelas abaixo usam os parâmetros RangeStart e RangeEnd para restringir a "
                    "janela de dados lida da origem, permitindo que o Power BI atualize apenas as "
                    "partições afetadas em vez de recarregar a tabela inteira.")
        for t in incrementais:
            b.marcador("%s — %s" % (t["nome"], _txt(prosa.m(t["nome"], "resumo"))))

    for t in man["tabelas"]:
        if not t["particoes"]:
            continue
        origem = t["origem"] or {}
        b.heading(2, "Query de %s" % t["nome"], chave=catalog.key_m(t["nome"]))
        b.rotulo("Resumo", _txt(prosa.m(t["nome"], "resumo")))
        b.rotulo("Origem", "%s — %s" % (origem.get("tipo") or "—", _objetos_origem(origem)))
        b.rotulo("Consulta nativa (SQL)", "Sim" if origem.get("consulta_nativa") else "Não")
        for part in t["particoes"]:
            if part["passos"]:
                b.heading(3, "Tratamentos aplicados")
                for i, passo in enumerate(part["passos"], 1):
                    b.numerado(i, passo["nome"], _txt(prosa.passo(t["nome"], passo["nome"])))
            b.heading(3, "Código M")
            b.codigo(part["codigo_m"])
            for i, sql in enumerate(part["sql"], 1):
                b.heading(3, "Consulta SQL nativa%s"
                          % ("" if len(part["sql"]) == 1 else " %d" % i))
                b.codigo(sql)


def _rls(b, man, prosa):
    if not man["perfis_rls"]:
        return
    b.heading(1, "Segurança em nível de linha (RLS)", chave="sec_rls", quebra_antes=True)
    b.paragrafo("O modelo define %d perfis de segurança. Cada perfil aplica um filtro DAX por "
                "tabela, avaliado no contexto do usuário autenticado."
                % len(man["perfis_rls"]))
    b.tabela(["Perfil", "Permissão", "Tabelas filtradas", "Descrição"],
             [[W.Mono(r["nome"]), r["permissao_modelo"] or "—", str(len(r["permissoes"])),
               _uma_linha(prosa.rls(r["nome"], PENDENTE))] for r in man["perfis_rls"]],
             pesos=[3, 2, 2, 6])
    for r in man["perfis_rls"]:
        b.heading(2, "Perfil %s" % r["nome"], chave=catalog.key_rls(r["nome"]))
        b.rotulo("Descrição", _txt(prosa.rls(r["nome"])))
        b.rotulo("Permissão no modelo", r["permissao_modelo"] or "—")
        for p in r["permissoes"]:
            b.heading(3, "Filtro em %s" % p["tabela"])
            b.codigo(p["dax"])


# ---------------------------------------------------------------------------- API


def render(man, cfg, descriptions, destino, meta):
    template = _template_path()
    if not os.path.isfile(template):
        raise SystemExit(
            "Template ausente: %s\nGere-o com:\n"
            "  python3 tools/pbidoc/make_template.py <referencia.docx>" % template)

    W.aplicar_estilo(cfg.get("estilo_docx"))
    prosa = rc.Prosa(descriptions)
    b = W.Body()
    _capa(b, man, cfg, meta)
    _objetivo(b, cfg)
    _informacoes(b, man, cfg)
    _indice(b, man)
    _visao_geral(b, prosa)
    _modelo_relacional(b, man)
    _tabelas(b, man, prosa)
    _medidas(b, man, prosa)
    _queries(b, man, prosa)
    _rls(b, man, prosa)

    nome = "%s - Glossário de Dados.docx" % cfg["titulo"]
    os.makedirs(destino, exist_ok=True)
    caminho = os.path.join(destino, nome)
    corpo = b.xml()
    # reescrever um .docx idêntico geraria um blob novo no git a cada execução
    if W.corpo_de(caminho) == corpo:
        return None
    W.gravar(template, caminho, corpo)
    return nome
