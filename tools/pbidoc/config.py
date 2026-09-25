"""Configuração do pbidoc (`.pbidoc.json` na raiz do repositório).

Um repositório pode conter vários projetos PBIP (um por subpasta de
`projetos/`, ver `extract_model.descobrir`). `.pbidoc.json` guarda:

- valores **globais**, que valem para todos os projetos (`docs_dir`,
  `formatos`, `modelo`, `timeout`, `limite_itens_precommit`, `projetos_dir`);
- um mapa **`projetos`**, chaveado pelo nome de cada subpasta, com
  overrides específicos daquele projeto (título, subtítulo, elaborado por,
  modelo, etc.) — qualquer campo do PADRAO pode ser sobrescrito ali.

A resolução para um projeto específico é: PADRAO -> globais do arquivo ->
`projetos[<nome>]`. Veja `resolver_projeto()`.
"""

import json
import os

PADRAO = {
    "projetos_dir": "projetos",      # onde procurar as subpastas de projeto
    "docs_dir": "docs",
    "formatos": ["md", "docx"],      # md, docx (técnico) e/ou negocio
    "descrever_colunas": True,
    "modelo": "sonnet",
    "timeout": 900,
    "limite_itens_precommit": 120,
    "titulo": None,                  # None = deriva do nome do projeto
    "subtitulo": "Documentação Técnica do Modelo de Dados",
    "elaborado_por": "",
    "revisado_por": "",
    "link_relatorio": "",
    "frequencia_atualizacao": "",
    "objetivo": "",
    "estilo_docx": {},                # fontes/cores do .docx — ver docx_writer.aplicar_estilo
    # informações do documento de negócio que não existem nos arquivos do PBIP;
    # campo vazio vira o marcador [PREENCHER: …] no .docx de negócio
    "negocio": {
        "link_relatorio": "",
        "link_dataset": "",
        "objetivo": "",
        "owner_tecnico": "",
        "owner_negocio": "",
        "publico_area": "",
        "publico_clientes": "",
        "publico_perfis": "",
        "propriedade": "",
        "plataforma_origem": "",
        "data_criacao_dashboard": "",
        "data_atualizacao_dashboard": "",
        "frequencia_atualizacao": "",
        "status": "",
        "duvidas_frequentes": [],    # [{"pergunta": "...", "resposta": "..."}]
        "filtro_padrao_obs": "",
    },
    "projetos": {},                  # overrides por projeto: {"<nome>": {...}}
}

NOME_ARQUIVO = ".pbidoc.json"


def caminho(root):
    return os.path.join(root, NOME_ARQUIVO)


def carregar(root):
    cfg = dict(PADRAO)
    path = caminho(root)
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                cfg.update(json.load(fh) or {})
        except (ValueError, OSError) as exc:
            raise SystemExit("%s inválido: %s" % (NOME_ARQUIVO, exc))
    return cfg


def salvar(root, cfg):
    with open(caminho(root), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def _copiar(valor):
    if isinstance(valor, dict):
        return {k: _copiar(v) for k, v in valor.items()}
    return list(valor) if isinstance(valor, list) else valor


def _mesclar(base, novo):
    """Mescla `novo` em `base`: dicts (`negocio`, `estilo_docx`) chave a chave, o resto
    por substituição — assim um projeto sobrescreve só `negocio.owner_tecnico`, por
    exemplo, sem perder as demais chaves definidas globalmente."""
    for k, v in novo.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _mesclar(base[k], v)
        else:
            base[k] = _copiar(v)


def resolver_projeto(cfg_raiz, nome, projeto_dir=None):
    """Mescla PADRAO -> globais de `.pbidoc.json` -> `projetos[<nome>]` ->
    `<projeto_dir>/.pbidoc.json` (config local do projeto, opcional).

    O arquivo dentro da pasta do projeto serve para projetos que não são versionados
    (ou que têm configuração própria): vale por último e não precisa de `projetos`.

    Dicts (`negocio`, `estilo_docx`) são mesclados chave a chave (ver `_mesclar`).
    `nome` é sempre o nome da subpasta em `projetos/` (ou o nome derivado do
    `*.SemanticModel` no modo de projeto único) — é ele que determina
    `docs/<nome>/` e `.pbidoc-cache/<nome>/`, então `cfg["projeto"]` nunca é
    sobrescrito por um valor do arquivo de configuração.
    """
    cfg = _copiar(PADRAO)
    _mesclar(cfg, {k: v for k, v in cfg_raiz.items() if k != "projetos"})
    overrides = (cfg_raiz.get("projetos") or {}).get(nome) or {}
    _mesclar(cfg, {k: v for k, v in overrides.items() if k != "projetos"})
    if projeto_dir:
        local = os.path.join(projeto_dir, NOME_ARQUIVO)
        if os.path.isfile(local):
            try:
                with open(local, encoding="utf-8") as fh:
                    _mesclar(cfg, {k: v for k, v in (json.load(fh) or {}).items()
                                   if k != "projetos"})
            except (ValueError, OSError) as exc:
                raise SystemExit("%s inválido: %s" % (local, exc))
    cfg["projeto"] = nome
    if not cfg.get("titulo"):
        cfg["titulo"] = nome.replace("_", " ").replace("-", " ").upper()
    return cfg


def docs_projeto(root, cfg):
    return os.path.join(root, cfg["docs_dir"], cfg["projeto"])
