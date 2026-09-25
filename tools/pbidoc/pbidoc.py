#!/usr/bin/env python3
"""pbidoc — documentação determinística de projetos Power BI (PBIP).

Repositório multi-projeto: cada subpasta de `projetos/` (configurável via
`projetos_dir`) que contenha um `*.SemanticModel` é um projeto independente,
com sua própria documentação em `docs/<projeto>/` e seu próprio cache em
`.pbidoc-cache/<projeto>/`. Um repositório com um único `*.SemanticModel` na
raiz também funciona (modo de compatibilidade).

Subcomandos:
    init      cria/atualiza `.pbidoc.json` com os projetos descobertos
    projetos  lista os projetos do repositório e quantas descrições faltam
    extract   lê o TMDL/PBIR e grava o manifesto em `.pbidoc-cache/<projeto>/model.json`
    diff      compara com `_descriptions.json` e grava `.pbidoc-cache/<projeto>/changes.json`
    render    gera a documentação (`--md`, `--docx` técnico, `--negocio`) + o índice em `docs/README.md`
    merge     mescla lotes de descrições em `_descriptions.json`
    status    resumo do estado atual da documentação

`diff`, `merge` e `status` aceitam `--escopo tecnico|negocio`. O escopo `negocio` inclui
tudo do técnico e acrescenta as páginas do relatório (e as colunas usadas nele).
Sem a flag, vale `negocio` se o projeto tem `"negocio"` em `formatos`, senão `tecnico`.

Todo subcomando aceita `--projeto NOME` (repetível, informado **antes** do
subcomando: `pbidoc.py --projeto vendas --projeto rh extract`) para
restringir a um ou mais projetos; sem essa flag, opera sobre todos os
projetos descobertos.

Só o passo de escrever `_descriptions.json` envolve um modelo de linguagem; todo o
resto é puramente mecânico.
"""

import argparse
import os
import subprocess
import sys
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import catalog                      # noqa: E402
import config                       # noqa: E402
import diff_model                   # noqa: E402
import extract_model                # noqa: E402
import render_common as rc          # noqa: E402

CACHE_DIR = ".pbidoc-cache"
ARQ_MODELO_CACHE = "model.json"
ARQ_MUDANCAS = "changes.json"
ARQ_DESCRICOES = "_descriptions.json"
ARQ_MODELO_DOC = "_model.json"
ARQ_META = "_meta.json"
ARQ_INDICE_DOCS = "README.md"


class Repo:
    """A raiz do repositório: config global e descoberta de projetos."""

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.cfg_bruta = config.carregar(self.root)

    @property
    def projetos_dir_nome(self):
        return self.cfg_bruta.get("projetos_dir") or config.PADRAO["projetos_dir"]

    def descobrir(self):
        """Lista `(nome, caminho)` de todos os projetos do repositório."""
        return extract_model.descobrir(self.root, self.projetos_dir_nome)

    def selecionar(self, nomes):
        """Resolve uma lista de nomes de projeto (ou todos, se `nomes` vazio)."""
        todos = self.descobrir()
        if not todos:
            raise SystemExit(
                "Nenhum projeto encontrado em %s/*/ (nem *.SemanticModel na raiz)."
                % self.projetos_dir_nome)
        if not nomes:
            return todos
        mapa = dict(todos)
        selecionados = []
        for n in nomes:
            if n not in mapa:
                raise SystemExit("Projeto não encontrado: %s (disponíveis: %s)"
                                  % (n, ", ".join(sorted(mapa))))
            selecionados.append((n, mapa[n]))
        return selecionados


class Contexto:
    """Contexto de um projeto específico dentro do repositório."""

    def __init__(self, repo, nome, projeto_dir):
        self.repo = repo
        self.nome = nome
        self.projeto_dir = projeto_dir
        self.root = repo.root
        self.cache = os.path.join(self.root, CACHE_DIR, nome)

    @property
    def modelo_cache(self):
        return os.path.join(self.cache, ARQ_MODELO_CACHE)

    @property
    def mudancas(self):
        return os.path.join(self.cache, ARQ_MUDANCAS)

    def manifesto(self, extrair_se_faltar=True):
        man = rc.carregar_json(self.modelo_cache)
        if man is None:
            if not extrair_se_faltar:
                raise SystemExit("Manifesto ausente. Rode: pbidoc.py --projeto %s extract" % self.nome)
            man = extract_model.extract(self.projeto_dir)
            extract_model.dump(man, self.modelo_cache)
        return man

    def cfg(self):
        return config.resolver_projeto(self.repo.cfg_bruta, self.nome, self.projeto_dir)

    def docs_dir(self):
        return config.docs_projeto(self.root, self.cfg())

    def descricoes_path(self):
        return os.path.join(self.docs_dir(), ARQ_DESCRICOES)

    def descricoes(self):
        return rc.carregar_json(self.descricoes_path(), catalog.vazio(self.nome))


def _ignorado_pelo_git(root, path):
    """True se o git ignora `path` (`.gitignore` ou `.git/info/exclude`).

    Projetos ignorados são locais/temporários: não entram no índice `docs/README.md`
    (versionado) nem são registrados no `.pbidoc.json` por `init`.
    """
    try:
        r = subprocess.run(["git", "check-ignore", "-q", "--", path], cwd=root,
                           capture_output=True)
        return r.returncode == 0
    except OSError:
        return False


def _rel(root, path):
    try:
        return os.path.relpath(path, root).replace(os.sep, "/")
    except ValueError:
        return path


def _contextos(repo, args):
    return [Contexto(repo, nome, caminho) for nome, caminho in repo.selecionar(args.projeto)]


def _escopo(cfg, args):
    """Escopo do catálogo: pedido explícito, ou `negocio` se o projeto gera esse formato."""
    pedido = getattr(args, "escopo", None)
    if pedido:
        return pedido
    return "negocio" if "negocio" in (cfg.get("formatos") or []) else "tecnico"


# ------------------------------------------------------------------------ comandos


def cmd_init(repo, args):
    path = config.caminho(repo.root)
    achados = repo.descobrir()
    if not achados:
        print("Nenhum projeto encontrado em %s/*/ nem *.SemanticModel na raiz." % repo.projetos_dir_nome)
        print("Adicione um projeto PBIP em %s/<nome>/ e rode init novamente." % repo.projetos_dir_nome)
        return 0

    if os.path.isfile(path) and not args.force:
        cfg = config.carregar(repo.root)
    else:
        cfg = dict(config.PADRAO)
        cfg["projetos"] = {}

    cfg.setdefault("projetos", {})
    novos = 0
    for nome, caminho in achados:
        if _ignorado_pelo_git(repo.root, caminho):
            print("  (ignorado pelo git, não registrado em .pbidoc.json: %s — use "
                  "%s/.pbidoc.json para a configuração local)" % (nome, _rel(repo.root, caminho)))
            continue
        if nome not in cfg["projetos"]:
            cfg["projetos"][nome] = {"negocio": dict(config.PADRAO["negocio"])}
            novos += 1
    config.salvar(repo.root, cfg)

    print("Config em %s" % _rel(repo.root, path))
    print("  %d projeto(s) encontrado(s), %d novo(s) registrado(s):" % (len(achados), novos))
    for nome, caminho in achados:
        print("    - %s (%s)" % (nome, _rel(repo.root, caminho)))
    return 0


def cmd_projetos(repo, args):
    contextos = _contextos(repo, args)
    for ctx in contextos:
        man = ctx.manifesto()
        cfg = ctx.cfg()
        descricoes = ctx.descricoes()
        changes = diff_model.compute(man, descricoes, descrever_colunas=cfg["descrever_colunas"],
                                     escopo=_escopo(cfg, args))
        pendentes = changes["resumo"]["total_a_escrever"]
        print("%-30s tipo=%-19s %-40s docs=%-30s relatorio=%-3s pendentes=%d"
              % (ctx.nome, man["projeto"].get("tipo") or "completo",
                 _rel(repo.root, ctx.projeto_dir), _rel(repo.root, ctx.docs_dir()),
                 "sim" if man["projeto"].get("report") else "nao", pendentes))
    return 0


def cmd_extract(repo, args):
    for ctx in _contextos(repo, args):
        man = extract_model.extract(ctx.projeto_dir)
        destino = args.out or ctx.modelo_cache
        extract_model.dump(man, destino)
        est = man["estatisticas"]
        print("[%s] tipo: %s · manifesto em %s"
              % (ctx.nome, man["projeto"].get("tipo") or "completo", _rel(repo.root, destino)))
        if man["projeto"].get("tipo") == "relatorio_conectado":
            print("  %d páginas · %d visuais · %d medidas de relatório · %d bookmarks · "
                  "%d tabelas no dataset · %d alertas"
                  % (est["paginas"], est["visuais"], est["extensoes"], est["bookmarks"],
                     est["tabelas_dataset"], est["alertas"]))
            continue
        print("  %d tabelas · %d colunas · %d medidas · %d relacionamentos · %d parâmetros · "
              "%d perfis RLS · %d páginas"
              % (est["tabelas"], est["colunas"], est["medidas"], est["relacionamentos"],
                 est["parametros"], est["perfis_rls"], est["paginas"]))
    return 0


def cmd_diff(repo, args):
    for ctx in _contextos(repo, args):
        man = ctx.manifesto()
        cfg = ctx.cfg()
        desc_path = ctx.descricoes_path()
        descricoes = rc.carregar_json(desc_path)
        if descricoes is None:
            descricoes = catalog.vazio(ctx.nome)
            rc.salvar_json(desc_path, descricoes)

        changes = diff_model.compute(
            man, descricoes,
            descrever_colunas=cfg["descrever_colunas"],
            limite=args.limite if args.limite and args.limite > 0 else None,
            escopo=_escopo(cfg, args))
        destino = args.out or ctx.mudancas
        diff_model.dump(changes, destino)

        r = changes["resumo"]
        print("[%s] tipo: %s · escopo: %s · modo: %s"
              % (ctx.nome, changes["tipo_projeto"], changes["escopo"], changes["modo"]))
        print("  novos=%d alterados=%d pendentes=%d removidos=%d -> %d a escrever%s"
              % (r["novos"], r["alterados"], r["pendentes"], r["removidos"],
                 r["total_a_escrever"], " (truncado)" if r["truncado"] else ""))
        print("  mudanças em %s" % _rel(repo.root, destino))
    return 0


def _escrever_indice_docs(repo):
    """Gera `docs/README.md`: um índice determinístico de TODOS os projetos do
    repositório — não só os passados a `--projeto` nesta chamada. Renderizar um
    único projeto nunca pode apagar os demais do índice, por isso a lista vem
    sempre de `repo.descobrir()`, e o `cfg` de cada um é resolvido sem precisar
    extrair o manifesto (mais barato, e funciona mesmo se aquele projeto ainda
    não tiver sido renderizado nesta execução)."""
    cfg_raiz = repo.cfg_bruta
    docs_dir = os.path.join(repo.root, cfg_raiz.get("docs_dir") or config.PADRAO["docs_dir"])

    linhas = [
        "# Documentação dos projetos Power BI",
        "",
        "> _Índice gerado automaticamente por `pbidoc.py render`. **Não edite este "
        "arquivo à mão** — as alterações são perdidas na próxima geração._",
        "",
        "| Projeto | Descrição | Documentação |",
        "| --- | --- | --- |",
    ]
    for nome, caminho in sorted(repo.descobrir(), key=lambda p: p[0].lower()):
        if _ignorado_pelo_git(repo.root, caminho):
            continue          # projeto local/temporário: não entra no índice versionado
        cfg = config.resolver_projeto(cfg_raiz, nome, caminho)
        titulo = cfg.get("titulo") or nome
        objetivo = (cfg.get("objetivo") or "—").strip() or "—"
        objetivo = objetivo.replace("|", "\\|").replace("\n", " ")
        link = "./%s/README.md" % quote(nome)
        linhas.append("| **%s** | %s | [Abrir](%s) |" % (titulo, objetivo, link))
    linhas.append("")
    if len(linhas) <= 7:
        return None           # nenhum projeto visível: mantém o índice/placeholder existente

    conteudo = "\n".join(linhas)
    destino = os.path.join(docs_dir, ARQ_INDICE_DOCS)
    os.makedirs(docs_dir, exist_ok=True)
    anterior = None
    if os.path.isfile(destino):
        with open(destino, encoding="utf-8") as fh:
            anterior = fh.read()
    if anterior == conteudo:
        return None
    with open(destino, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(conteudo)
    return destino


def cmd_render(repo, args):
    formatos_flag = []
    if args.md:
        formatos_flag.append("md")
    if args.docx:
        formatos_flag.append("docx")
    if args.negocio:
        formatos_flag.append("negocio")

    for ctx in _contextos(repo, args):
        man = ctx.manifesto()
        cfg = ctx.cfg()
        destino = ctx.docs_dir()
        descricoes = ctx.descricoes()

        # descrições de objetos que não existem mais saem junto com o render
        obsoletas = diff_model.compute(
            man, descricoes, descrever_colunas=cfg["descrever_colunas"])["removidos"]
        if obsoletas:
            diff_model.purge(descricoes, obsoletas)
            rc.salvar_json(ctx.descricoes_path(), descricoes)

        formatos = formatos_flag or list(cfg["formatos"])

        conectado = man["projeto"].get("tipo") == "relatorio_conectado"
        conteudos = {}
        if "md" in formatos:
            if conectado:
                import render_md_relatorio as render_md
            else:
                import render_md
            conteudos.update(render_md.render(man, cfg, descricoes))

        meta_path = os.path.join(destino, ARQ_META)
        assinatura = rc.assinar(man, descricoes)
        conteudos, meta = rc.datar(conteudos, meta_path, assinatura)
        escritos = rc.escrever(destino, conteudos)

        if "docx" in formatos:
            if conectado:
                import render_docx_relatorio as render_docx
            else:
                import render_docx
            nome_docx = render_docx.render(man, cfg, descricoes, destino, meta)
            if nome_docx:
                escritos.append(nome_docx)

        if "negocio" in formatos:
            import render_docx_negocio
            nome_neg = render_docx_negocio.render(man, cfg, descricoes, destino, meta)
            if nome_neg:
                escritos.append(nome_neg)

        rc.salvar_json(meta_path, meta)
        extract_model.dump(man, os.path.join(destino, ARQ_MODELO_DOC))

        print("[%s] documentação em %s" % (ctx.nome, _rel(repo.root, destino)))
        if escritos:
            for nome_arq in escritos:
                print("  atualizado: %s" % nome_arq)
        else:
            print("  nada mudou")

    indice = _escrever_indice_docs(repo)
    if indice:
        print("índice atualizado: %s" % _rel(repo.root, indice))
    return 0


def _inferir_projeto(repo, caminho_patch):
    """`.pbidoc-cache/<projeto>/patch-NN.json` -> nome do projeto."""
    rel = _rel(repo.root, os.path.abspath(caminho_patch))
    partes = rel.split("/")
    if len(partes) >= 3 and partes[0] == CACHE_DIR:
        return partes[1]
    return None


def cmd_merge(repo, args):
    por_projeto = {}
    avulsos = []
    for caminho in args.patches:
        nome = _inferir_projeto(repo, caminho)
        if nome is None:
            avulsos.append(caminho)
            continue
        por_projeto.setdefault(nome, []).append(caminho)

    if avulsos:
        if len(args.projeto) == 1:
            por_projeto.setdefault(args.projeto[0], []).extend(avulsos)
        else:
            raise SystemExit(
                "Não foi possível inferir o projeto destes lotes (fora de "
                "%s/<projeto>/): %s — use --projeto para indicar um único "
                "projeto." % (CACHE_DIR, ", ".join(avulsos)))

    for nome, patches in por_projeto.items():
        caminho_projeto = dict(repo.descobrir()).get(nome)
        if caminho_projeto is None:
            raise SystemExit("Projeto não encontrado para os lotes: %s" % nome)
        ctx = Contexto(repo, nome, caminho_projeto)
        _merge_um(repo, ctx, patches, args.limpar, args)
    return 0


def _merge_um(repo, ctx, patches, limpar, args):
    man = ctx.manifesto()
    cfg = ctx.cfg()
    desc_path = ctx.descricoes_path()
    descricoes = rc.carregar_json(desc_path, catalog.vazio(ctx.nome))
    descricoes.setdefault("objetos", {})

    # valida contra o escopo mais amplo: um lote pode trazer itens de qualquer escopo
    esperado = {i["chave"]: i for i in catalog.build(
        man, descrever_colunas=cfg["descrever_colunas"], escopo="negocio")}
    aplicados = ignorados = 0
    avisos = []

    for caminho in patches:
        patch = rc.carregar_json(caminho)
        if patch is None:
            avisos.append("não foi possível ler %s" % _rel(repo.root, caminho))
            continue
        objetos = patch.get("objetos", patch)
        if not isinstance(objetos, dict):
            avisos.append("%s não contém um objeto JSON de descrições" % _rel(repo.root, caminho))
            continue
        for chave, entrada in objetos.items():
            item = esperado.get(chave)
            if item is None:
                ignorados += 1
                avisos.append("chave inexistente no modelo: %s" % chave)
                continue
            if not isinstance(entrada, dict):
                ignorados += 1
                avisos.append("valor inválido em %s" % chave)
                continue
            limpo = {"hash": item["hash"]}
            for campo in catalog.CAMPOS[item["tipo"]]:
                if campo in entrada and entrada[campo] not in (None, ""):
                    limpo[campo] = entrada[campo]
            if entrada.get("revisar"):
                limpo["revisar"] = True
            if item["tipo"] == "tabela" and limpo.get("papel") not in catalog.PAPEIS:
                if limpo.get("papel"):
                    avisos.append("papel inválido em %s: %r (esperado: %s)"
                                  % (chave, limpo["papel"], ", ".join(catalog.PAPEIS)))
                limpo.pop("papel", None)
            extras = set(entrada) - set(catalog.CAMPOS[item["tipo"]]) - {"hash", "revisar"}
            if extras:
                avisos.append("campos ignorados em %s: %s" % (chave, ", ".join(sorted(extras))))
            descricoes["objetos"][chave] = limpo
            aplicados += 1
        if limpar:
            try:
                os.remove(caminho)
            except OSError:
                pass

    changes = diff_model.compute(man, descricoes, descrever_colunas=cfg["descrever_colunas"])
    diff_model.purge(descricoes, changes["removidos"])
    rc.salvar_json(desc_path, descricoes)

    print("[%s] mescladas %d descrições em %s" % (ctx.nome, aplicados, _rel(repo.root, desc_path)))
    if ignorados:
        print("  %d entradas ignoradas" % ignorados)
    for aviso in avisos[:15]:
        print("  aviso: %s" % aviso)
    if len(avisos) > 15:
        print("  ... e mais %d avisos" % (len(avisos) - 15))
    restante = diff_model.compute(man, descricoes, descrever_colunas=cfg["descrever_colunas"],
                                  escopo=_escopo(cfg, args))
    print("  ainda faltam %d descrições" % restante["resumo"]["total_a_escrever"])


def cmd_status(repo, args):
    for ctx in _contextos(repo, args):
        man = ctx.manifesto()
        cfg = ctx.cfg()
        descricoes = ctx.descricoes()
        escopo = _escopo(cfg, args)
        changes = diff_model.compute(man, descricoes, descrever_colunas=cfg["descrever_colunas"],
                                     escopo=escopo)
        itens = catalog.build(man, descrever_colunas=cfg["descrever_colunas"], escopo=escopo)
        total = len(itens)
        faltando = changes["resumo"]["total_a_escrever"]
        print("[%s] (tipo %s · escopo %s)"
              % (ctx.nome, man["projeto"].get("tipo") or "completo", escopo))
        print("  Documentação: %s" % _rel(repo.root, ctx.docs_dir()))
        print("  Descrições: %d/%d preenchidas (%d pendentes)" % (total - faltando, total, faltando))
        alertas = man["relatorio"].get("alertas") or []
        if alertas:
            print("  Alertas de qualidade do relatório (%d):" % len(alertas))
            for al in alertas[:12]:
                print("    - %s: %s" % (al["tipo"], al["detalhe"][:140]))
            if len(alertas) > 12:
                print("    ... e mais %d (veja relatorio.alertas em _model.json)" % (len(alertas) - 12))
        if escopo == "negocio":
            import render_docx_negocio
            faltas = render_docx_negocio.campos_a_preencher(cfg, man)
            print("  Informações a preencher no documento de negócio (%s): %d"
                  % (render_docx_negocio.MARCADOR, len(faltas)))
            for campo, rotulo in faltas:
                print("    - negocio.%s — %s" % (campo, rotulo))
        revisar = [k for k, v in (descricoes.get("objetos") or {}).items()
                   if isinstance(v, dict) and v.get("revisar")]
        if revisar:
            print("  Marcados para revisão humana (%d):" % len(revisar))
            for k in sorted(revisar)[:20]:
                print("    - %s" % k)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="pbidoc", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default=".", help="raiz do repositório (padrão: .)")
    p.add_argument("--projeto", action="append", default=[],
                   help="nome do projeto (subpasta de projetos/); repetível; "
                        "padrão: todos os projetos descobertos")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="cria/atualiza .pbidoc.json com os projetos descobertos")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("projetos", help="lista os projetos do repositório")
    s.set_defaults(func=cmd_projetos)

    s = sub.add_parser("extract", help="TMDL/PBIR -> manifesto JSON")
    s.add_argument("--out")
    s.set_defaults(func=cmd_extract)

    s = sub.add_parser("diff", help="lista o que precisa de descrição nova")
    s.add_argument("--out")
    s.add_argument("--limite", type=int, default=0)
    s.add_argument("--escopo", choices=catalog.ESCOPOS,
                   help="tecnico (md/glossário) ou negocio (acrescenta páginas do relatório)")
    s.set_defaults(func=cmd_diff)

    s = sub.add_parser("render", help="gera a documentação")
    s.add_argument("--md", action="store_true")
    s.add_argument("--docx", action="store_true", help="glossário técnico em .docx")
    s.add_argument("--negocio", action="store_true", help="documentação de negócio em .docx")
    s.set_defaults(func=cmd_render)

    s = sub.add_parser("merge", help="mescla lotes de descrições em _descriptions.json")
    s.add_argument("patches", nargs="+")
    s.add_argument("--limpar", action="store_true", help="apaga os lotes após mesclar")
    s.add_argument("--escopo", choices=catalog.ESCOPOS)
    s.set_defaults(func=cmd_merge)

    s = sub.add_parser("status", help="resumo do estado da documentação")
    s.add_argument("--escopo", choices=catalog.ESCOPOS)
    s.set_defaults(func=cmd_status)

    args = p.parse_args(argv)
    return args.func(Repo(args.root), args)


if __name__ == "__main__":
    sys.exit(main())
