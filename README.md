# Template de documentação com IA para projetos Power BI (PBIP)

Três skills, um pipeline determinístico e um *hook* de pre-commit que mantêm a
documentação de um ou mais modelos semânticos Power BI sempre igual ao que está
publicado — em Markdown, em Word técnico e em Word de negócio — gastando o mínimo
possível de tokens. Funciona com o Claude Code, o OpenCode, o Google Antigravity e
qualquer harness que leia `AGENTS.md`.

## Sumário

1. [Como funciona](#1-como-funciona)
2. [Guardrails](#2-guardrails)
3. [Estrutura do repositório](#3-estrutura-do-repositório)
4. [O que é gerado](#4-o-que-é-gerado)
5. [Instalação](#5-instalação)
6. [Usar no chat](#6-usar-no-chat)
7. [Configuração](#7-configuração)
8. [Escolher o modelo](#8-escolher-o-modelo)
9. [Pre-commit](#9-pre-commit)
10. [Revisão humana](#10-revisão-humana)
11. [Plano B com chave de API](#11-plano-b-com-chave-de-api)
12. [Solução de problemas](#12-solução-de-problemas)
13. [Referência de comandos](#13-referência-de-comandos)

## 1. Como funciona

Um projeto PBIP é texto: o modelo semântico fica em arquivos `.tmdl` e o relatório
em `.json`. Isso significa que **quase toda a documentação pode ser extraída
mecanicamente** — nomes de tabelas, tipos de coluna, expressões DAX, código M,
relacionamentos, perfis de segurança. Nada disso precisa de um modelo de linguagem,
e mandar um modelo ler dezenas de arquivos TMDL a cada commit sairia caro e
produziria um texto diferente a cada execução.

Por isso o pipeline separa as duas responsabilidades. Scripts Python fazem a
extração e a formatação; o modelo de linguagem escreve **apenas a prosa de
negócio** — o que a medida significa, qual é o grão da tabela, o que aquele passo
do Power Query trata. Essa prosa é guardada em `_descriptions.json` junto com o
*hash* da definição que a originou. No commit seguinte, só o que mudou é reenviado
ao modelo.

| Etapa | O que faz | Custo |
| --- | --- | --- |
| `extract` | Lê os arquivos TMDL e PBIR e monta um manifesto JSON com toda a estrutura do modelo. | 0 tokens |
| `diff` | Compara os hashes com as descrições já escritas e lista só os objetos novos ou alterados. | 0 tokens |
| **descrever** | A skill escreve a prosa dos objetos da lista e grava em `_descriptions.json`. | **única etapa paga** |
| `render` | Monta os arquivos Markdown e o Word a partir do manifesto e das descrições. | 0 tokens |

Como os arquivos `.md` e `.docx` saem sempre dos mesmos renderizadores, a estrutura
da documentação é idêntica em qualquer projeto Power BI. O modelo nunca escreve um
arquivo de documentação diretamente.

## 2. Guardrails

Este repositório bloqueia, **sempre** — em qualquer skill, com qualquer skill ativa
ou nenhuma, em qualquer harness — a leitura de:

- **segredos**: `.env`/`.env.*` (exceto `.env.example`), dotfiles de shell, chaves
  privadas, dumps de variáveis de ambiente;
- **dados reais** de qualquer projeto Power BI: `.pbix`, `.pbit`, `.abf`, a pasta
  `.pbi/` inteira, e planilhas/bancos tabulares (`.csv`, `.xlsx`, `.parquet`,
  `.sqlite`, ...).

Metadados de estrutura — colunas, medidas, relacionamentos, RLS, queries M —
**não** são bloqueados; são o insumo da documentação. Isso é aplicado em quatro
camadas independentes (hook de execução, permissões declarativas, checagem
bloqueante no `git commit`, e a política em `AGENTS.md`) — detalhes completos em
[`.claude/skills/guardrails/SKILL.md`](.claude/skills/guardrails/SKILL.md). Fonte
normativa dos padrões: `tools/guardrails/policy.py`.

```bash
# testar manualmente
python3 tools/guardrails/check.py --path <caminho>
python3 tools/guardrails/check.py --bash "<comando>"
```

## 3. Estrutura do repositório

Um repositório pode conter **vários projetos PBIP**, cada um em sua própria
subpasta de `projetos/`, com documentação isolada em `docs/<nome>/`:

```
projetos/
├── vendas/
│   ├── vendas.pbip
│   ├── vendas.SemanticModel/
│   └── vendas.Report/
└── rh/
    └── ... (mesma estrutura)

docs/
├── README.md              índice de todos os projetos (gerado)
├── vendas/                documentação do projeto "vendas"
└── rh/                    documentação do projeto "rh"

docs/templates/          documentos-modelo Word (técnico, negócio e relatório)

tools/
├── pbidoc/                pipeline determinístico (extração + render)
├── guardrails/            política de bloqueio de leitura
└── sync_skills.py         espelha .claude/skills em .agents/skills

.claude/
├── settings.json          modelo, permissões, hook de guardrails (Claude Code)
└── skills/                FONTE das skills
    ├── pbi-doc-md/        documentação técnica em Markdown
    ├── pbi-doc-docx/      documentação técnica em Word (glossário)
    ├── pbi-doc-negocio/   documentação de negócio em Word
    └── guardrails/        política de segurança, explicada para o assistente

.agents/
├── skills/                cópia gerada das skills, para o Antigravity (não edite)
└── hooks.json             mesmo guardrail, para o Antigravity

.opencode/plugins/pbi-guard.js   mesmo guardrail, para o OpenCode
opencode.json                     configuração do OpenCode
hooks/pre-commit                  mantém docs/ e .agents/skills sincronizados
AGENTS.md                         instruções universais (qualquer harness)
.gitattributes                    fim de linha LF em qualquer sistema; .docx como binário
```

### Harnesses e skills

| Harness | Instruções | Skills | Guardrails em tempo de execução |
| --- | --- | --- | --- |
| Claude Code | `CLAUDE.md` (importa `AGENTS.md`) | `.claude/skills/` | `.claude/settings.json` |
| OpenCode | `AGENTS.md` + `opencode.json` | via `opencode.json` | `.opencode/plugins/pbi-guard.js` |
| Google Antigravity | `AGENTS.md` (lido nativamente) | `.agents/skills/` | `.agents/hooks.json` |

As skills têm **uma única fonte, `.claude/skills/`**. O Antigravity lê skills de
`.agents/skills/` (e não de `.claude/skills/`), então essa pasta é uma **cópia
gerada** por `python3 tools/sync_skills.py` — o `hooks/pre-commit` a atualiza a cada
commit, e `python3 tools/sync_skills.py --check` (para CI) falha se estiver
desatualizada. Copia-se em vez de usar symlink porque symlinks no git exigem
configuração especial no Windows e quebram em `/mnt/c` no WSL.

Veja [`projetos/README.md`](projetos/README.md) para o passo a passo de adicionar
um projeto.

### Tipos de projeto

O pipeline reconhece o **tipo** de cada projeto pelos arquivos (`pbidoc.py projetos`
mostra `tipo=`), e as skills usam esse valor para saber como documentar — nunca pelo
nome da pasta:

| Tipo | O que tem | Como é documentado |
| --- | --- | --- |
| `completo` | modelo semântico local + relatório | modelo (tabelas, colunas, medidas, M, relacionamentos, RLS) + relatório |
| `modelo` | só o modelo semântico | como `completo`, sem páginas |
| `relatorio_conectado` | só o relatório (`<nome>.pbip` + `<nome>.Report`), ligado a um dataset publicado que **não** está no repositório: sem dados, sem modelo | conexão com o dataset, páginas, visuais (campos, ordenação, filtros, segmentações), medidas definidas no relatório (com DAX), campos do dataset usados, bookmarks, drillthrough/tooltips, navegação, tema, configurações e alertas de qualidade |

Num relatório conectado, o que pertence ao dataset (tipos de dado, DAX das medidas do
dataset, relacionamentos, RLS, Power Query) **não** é inventado: aparece só o que o
relatório revela (nome, tabela e onde cada campo é usado). As **condições dos
filtros** entram com seus valores (são regras do relatório); o estado salvo de
matrizes e bookmarks, que guarda valores reais de linhas, é descartado.

Um projeto pode ser mantido **só na sua máquina**: adicione a pasta ao
`.git/info/exclude` e coloque a configuração dele em `projetos/<nome>/.pbidoc.json`.
Projetos ignorados pelo git não entram no índice `docs/README.md` nem são registrados
por `init`.

## 4. O que é gerado

Tudo vai para `docs/<projeto>/`. Os três formatos leem o mesmo
`_descriptions.json`, então gerar mais de um não custa o dobro. Quais formatos cada
projeto gera é a chave `formatos` do `.pbidoc.json` (`md`, `docx`, `negocio`).

```
docs/<projeto>/
├── README.md                      página principal: visão geral + índice
├── 01-medidas.md                  medidas DAX, regra de cálculo, dependências
├── 02-tabelas.md                  tabelas, colunas, colunas calculadas, RLS
├── 03-queries-m.md                parâmetros, incremental, código M passo a passo
├── 04-modelo-relacional.md        diagrama Mermaid + propriedades dos relacionamentos
├── <TÍTULO> - Glossário de Dados.docx        glossário técnico num arquivo só
├── <TÍTULO> - Documentação de Negócio.docx   dicionário de dados para a área de negócio
├── _descriptions.json             a prosa — o único arquivo que a skill escreve
├── _model.json                    manifesto extraído (gerado)
└── _meta.json                     datas de criação e atualização (gerado)
```

### Markdown

Os quatro arquivos auxiliares começam e terminam com um botão de retorno para a
página principal:

```markdown
[⬅ **Voltar para a documentação principal**](./README.md)
```

O `README.md` traz a visão geral, o modelo em números, o índice dos quatro
documentos e atalhos diretos para cada tabela e cada medida. O esquema relacional é
um `erDiagram` Mermaid, que o GitHub e o VS Code renderizam nativamente — as
tabelas de data automáticas do Power BI ficam de fora do diagrama e aparecem só
como nota agregada.

### Relatório conectado (Markdown e Word)

Para `tipo=relatorio_conectado` os formatos `md` e `docx` geram a **documentação do
relatório**: `README.md` + `01-paginas.md`, `02-medidas.md`, `03-campos-do-dataset.md`,
`04-filtros-e-navegacao.md`, `05-conexao-e-alertas.md`, e um
`<TÍTULO> - Documentação do Relatório.docx` com o mesmo conteúdo. O template Word é
`template-relatorio.docx`, gerado de `docs/templates/Modelo - Documentacao de Relatorio.docx`
(produzido pelo mesmo renderizador com um projeto fictício, por
`python3 tools/pbidoc/make_modelo.py --tipo relatorio`). Os **alertas de qualidade**
apontam inconsistências dos arquivos do relatório: página de tooltip inexistente,
medida de relatório sem uso, bookmark sem botão, coluna de dado pessoal exibida, filtro
divergente entre páginas, texto alternativo repetido.

### Word técnico (glossário de dados)

Descreve o modelo: tabelas, colunas, medidas DAX, queries M, relacionamentos e RLS.
Skill: `pbi-doc-docx`. Não é montado do zero: é uma cópia de
`tools/pbidoc/assets/template-tecnico.docx`, **gerado localmente** (não versionado) a
partir do documento-modelo `docs/templates/Modelo - Documentacao Tecnica.docx` (ou de
um da sua equipe). Estilos, fontes embutidas, tema, cabeçalho, rodapé e margens vêm
byte a byte do modelo. Como o Word não renderiza Mermaid, o diagrama vira a tabela de
relacionamentos; a navegação é feita pelo índice, um sumário nativo com números de
página (atualizado pelo Word ao abrir; no Google Docs, "Atualizar sumário").

### Word de negócio

Descreve o **relatório** para quem usa: informações gerais, objetivo e regras de
negócio, estrutura do dashboard **página a página**, dicionário de dados (só as colunas
que aparecem no relatório), medidas, filtros e segurança (RLS). Skill:
`pbi-doc-negocio`; template `template-negocio.docx`, gerado de
`docs/templates/Modelo - Documentacao de Negocio.docx`.

Boa parte do que um documento de negócio pede **não existe nos arquivos do PBIP**:
owners, objetivo do dashboard, público-alvo, links, datas, status, dúvidas
frequentes. Isso vem do bloco `negocio` do `.pbidoc.json` (seção 7), preenchido por
pessoas; enquanto um campo estiver vazio, o documento traz um marcador
**`[PREENCHER: …]`** em negrito com realce amarelo (procure por `PREENCHER` com
Ctrl+F). O assistente nunca inventa esses valores, e editar o `.docx` à mão não adianta
— ele é regenerado a cada commit. `pbidoc.py status --escopo negocio` lista os campos
que faltam.

Os documentos-modelo de `docs/templates/` são versionados com `[PREENCHER: …]` no
lugar de nomes de pessoas, e-mails, clientes e sistemas; troque-os pelos da sua
equipe se quiser outro visual.

Nos três documentos Word, o sumário (ou índice) é um sumário nativo com os títulos de
nível 1 e 2 e o número de página. O Word atualiza as páginas ao abrir o arquivo; no
Google Docs, use "Atualizar sumário" se elas parecerem desatualizadas. Os títulos não
levam indicadores visíveis (que o Google Docs mostraria como fitas azuis) e nunca se
repetem: no dicionário de dados, colunas exibidas com o mesmo rótulo ficam numa tabela
sob um único título.

### Paleta e fontes

Fontes e cores do corpo do texto do Word técnico usam, por padrão, uma paleta neutra
(Calibri + tons de cinza/azul); o Word de negócio usa a fonte e o verde do próprio
modelo. Para outra identidade visual, defina `estilo_docx` no `.pbidoc.json` — veja
[`.claude/skills/pbi-doc-docx/reference/estrutura.md`](.claude/skills/pbi-doc-docx/reference/estrutura.md)
e
[`.claude/skills/pbi-doc-negocio/reference/estrutura.md`](.claude/skills/pbi-doc-negocio/reference/estrutura.md).

## 5. Instalação

1. **Clonar e apontar o git para a pasta `hooks/`** — assim o hook fica versionado
   e chega junto com o repositório para o resto da equipe, em vez de viver
   escondido em `.git/hooks/`:

   ```bash
   git clone <url-do-repositorio>
   cd <repositorio>
   git config core.hooksPath hooks
   chmod +x hooks/pre-commit
   ```

   **Cada pessoa que clonar o repositório precisa rodar esse `git config` uma
   vez.** É a única configuração que não viaja com o clone.

2. **Confiar no diretório no seu harness.** No Claude Code, abra-o
   interativamente na pasta do projeto uma vez e aceite a caixa de confirmação —
   sem isso, as permissões de `.claude/settings.json` são ignoradas nas execuções
   automáticas (`cd <repositorio> && claude`). No OpenCode, o equivalente é abrir
   `opencode` na pasta uma vez. No Antigravity, abra a pasta como workspace: ele lê
   `AGENTS.md`, `.agents/skills/` e `.agents/hooks.json` (o hook assume `python3` no
   PATH — confira com `/hooks` na CLI).

3. **Adicionar um projeto PBIP** — veja [`projetos/README.md`](projetos/README.md).
   Depois, registre-o:

   ```bash
   python3 tools/pbidoc/pbidoc.py init
   ```

4. **Gerar os templates do Word** — só é necessário para os formatos `docx` e
   `negocio`. Use os modelos de `docs/templates/` ou os da sua equipe (mesmo formato):

   ```bash
   python3 tools/pbidoc/make_template.py "docs/templates/Modelo - Documentacao Tecnica.docx" --modelo tecnico
   python3 tools/pbidoc/make_template.py "docs/templates/Modelo - Documentacao de Negocio.docx" --modelo negocio
   python3 tools/pbidoc/make_template.py "docs/templates/Modelo - Documentacao de Relatorio.docx" --modelo relatorio
   ```

5. **Sincronizar as skills para o Antigravity** (o pre-commit também faz isso):

   ```bash
   python3 tools/sync_skills.py
   ```

### Requisitos

Python 3 e git. Não é preciso instalar nenhuma biblioteca: `python-docx`,
`pandoc` e `libreoffice` **não** são usados — o `.docx` é montado com a biblioteca
padrão do Python. Para a etapa de descrição, basta o assistente (Claude Code ou
OpenCode) instalado e autenticado; chave de API só é necessária no plano B
([seção 11](#11-plano-b-com-chave-de-api)).

## 6. Usar no chat

As skills funcionam pedindo em linguagem natural — "documente o projeto `vendas`",
"atualize a documentação das medidas", "gere o glossário em Word do projeto `rh`",
"gere a documentação de negócio do `vendas`" — ou acionando-as pelo nome, dependendo
do harness (`/pbi-doc-md` no Claude Code, por exemplo).

| Skill | O que faz |
| --- | --- |
| `pbi-doc-md` | Gera ou atualiza os cinco arquivos Markdown em `docs/<projeto>/`. |
| `pbi-doc-docx` | Gera ou atualiza o glossário técnico único em `.docx`. |
| `pbi-doc-negocio` | Gera ou atualiza a documentação de negócio em `.docx` (com as páginas do relatório e os marcadores `[PREENCHER]`). |
| várias | Rodar mais de uma não duplica o custo: a prosa já escrita é reaproveitada integralmente (o escopo de negócio só acrescenta as páginas). |

Se houver mais de um projeto no repositório e o pedido for ambíguo, a skill
pergunta qual (exceto em modo pre-commit, onde o projeto já vem determinado). Na
primeira execução de um projeto sem documentação, a skill descreve tudo; nas
seguintes, ela lê apenas a lista de mudanças e escreve só o que falta.

### O que as skills nunca fazem

- Editar arquivos `.md` ou `.docx` diretamente — isso é sempre dos renderizadores.
- Alterar qualquer arquivo do projeto Power BI (`.tmdl`, `.pbir`, `.pbip`, `.pbism`).
- Reescrever descrições cujo hash não mudou.
- Ler arquivos TMDL diretamente — todo o contexto vem do arquivo de mudanças.
- Ler segredos ou dados reais — veja [Guardrails](#2-guardrails).
- Preencher o bloco `negocio` do `.pbidoc.json` ou inventar objetivo/público nas
  descrições de página — isso é informação humana, marcada com `[PREENCHER: …]`.
- Editar `.agents/skills/` (é cópia gerada de `.claude/skills/`).

O estilo dos textos é definido em
[`.claude/skills/pbi-doc-md/reference/estilo.md`](.claude/skills/pbi-doc-md/reference/estilo.md),
que é normativo: campo por campo, define o tempo verbal, o tamanho e os valores
permitidos. É o arquivo a editar se você quiser mudar o tom da documentação em
todos os projetos.

## 7. Configuração

Tudo fica em `.pbidoc.json`, na raiz do repositório. Chaves no nível raiz valem
para **todos** os projetos; a chave `projetos.<nome>` sobrescreve qualquer uma
delas só para aquele projeto.

| Chave | Padrão | Para que serve |
| --- | --- | --- |
| `projetos_dir` | `projetos` | Onde procurar as subpastas de projeto. |
| `docs_dir` | `docs` | Pasta raiz da documentação. |
| `formatos` | `["md", "docx"]` | Quais formatos gerar: `md`, `docx` (técnico) e/ou `negocio`. Remova um para acelerar o pre-commit. |
| `descrever_colunas` | `true` | Se `false`, só as colunas calculadas ganham descrição — reduz muito o custo da primeira execução. |
| `modelo` | `sonnet` | Modelo usado na execução automática. |
| `timeout` | `900` | Segundos até o hook desistir da chamada. |
| `limite_itens_precommit` | `120` | Teto de objetos descritos por commit. O restante entra no commit seguinte. |
| `titulo` | nome do projeto em maiúsculas | Título da capa do Word e do `README.md`. Também batiza o arquivo `.docx`. |
| `subtitulo` | Documentação Técnica do Modelo de Dados | Subtítulo da capa. |
| `elaborado_por` / `revisado_por` | vazio | Linhas da capa do Word. Deixe vazio para omiti-las. |
| `link_relatorio` | vazio | Endereço do relatório publicado, exibido nas informações gerais. |
| `frequencia_atualizacao` | vazio | Texto livre, por exemplo "Diariamente às 6h". |
| `objetivo` | vazio | Substitui o texto padrão da seção Objetivo. |
| `estilo_docx` | paleta neutra | Fontes/cores dos `.docx` — veja a seção 4. Chaves do Word de negócio: `fonte_neg`, `fonte_neg_leve`, `fonte_toc`, `cor_neg_titulo`, `cor_neg_destaque`. |
| `negocio` | vazio | Informações do documento de negócio que não existem no PBIP (tabela abaixo). |

### O bloco `negocio`

Dicts como `negocio` e `estilo_docx` são mesclados chave a chave: um projeto pode
sobrescrever só `negocio.owner_tecnico` sem perder o resto. Campo vazio vira
`[PREENCHER: …]` no Word de negócio.

| Chave | O que informar |
| --- | --- |
| `link_relatorio`, `link_dataset` | Links do relatório publicado e do modelo semântico. |
| `objetivo` | Qual problema de negócio o dashboard resolve. |
| `owner_tecnico`, `owner_negocio` | Nome, área e e-mail dos responsáveis. |
| `publico_area`, `publico_clientes`, `publico_perfis` | Áreas, clientes e perfis de usuários. |
| `propriedade` | Conta proprietária e regra de compartilhamento. |
| `plataforma_origem` | Sistema(s) de origem dos dados. |
| `data_criacao_dashboard`, `data_atualizacao_dashboard` | Datas (dd/mm/aaaa) do dashboard. |
| `frequencia_atualizacao` | Frequência agendada no serviço (ex.: 1h, diária). |
| `status` | Em desenvolvimento, Ativo ou Descontinuado. |
| `duvidas_frequentes` | Lista de `{"pergunta": "...", "resposta": "..."}`. |
| `filtro_padrao_obs` | Filtros aplicados na origem, fora do Power BI. |

Exemplo com dois projetos, um deles com overrides:

```json
{
  "modelo": "sonnet",
  "formatos": ["md", "docx"],
  "projetos": {
    "vendas": {
      "titulo": "VENDAS", "modelo": "opus", "formatos": ["md", "negocio"],
      "negocio": { "owner_tecnico": "Nome Sobrenome (Time de dados)", "status": "Ativo" }
    },
    "rh": { "formatos": ["md"] }
  }
}
```

## 8. Escolher o modelo

O hook chama a CLI do seu assistente instalada na máquina em modo headless,
reaproveitando a sessão já autenticada — não é preciso chave de API para o
caminho principal.

### Ordem de precedência

Da maior para a menor prioridade:

1. A variável de ambiente `PBIDOC_MODEL`, se estiver definida.
2. `projetos.<nome>.modelo` no `.pbidoc.json`.
3. A chave `modelo` global do `.pbidoc.json`.
4. O padrão embutido, `sonnet`.

```bash
# mudar para sempre, só um projeto
python3 -c "..."  # ou edite .pbidoc.json: "projetos": {"vendas": {"modelo": "haiku"}}

# mudar só neste commit
PBIDOC_MODEL=opus git commit -m "revisão do modelo semântico"
```

### Qual escolher

No chat, o modelo é o da sua sessão. No pre-commit, vale a tabela abaixo:

| Alias | Modelo | Quando usar aqui |
| --- | --- | --- |
| `haiku` | Claude Haiku 4.5 | Modelos simples, com nomes de coluna autoexplicativos e pouco DAX. Mais rápido e mais barato; descrições mais secas. |
| `sonnet` | Claude Sonnet 5 | **Padrão.** Bom equilíbrio para a maioria dos modelos semânticos. |
| `opus` | Claude Opus 5 | DAX e Power Query complexos, regras de negócio sutis, ou a primeira execução de um projeto grande, quando a qualidade do texto compensa. |
| `fable` | Claude Fable 5.1 | Modelos muito grandes ou críticos, quando a redação precisa ser a melhor possível. |

Também é possível fixar um identificador completo em vez do alias (por exemplo
`claude-sonnet-5`), sem sufixo de data, para garantir que o modelo não mude quando
um novo alias for lançado.

> **Estratégia sugerida:** rode a **primeira execução** de cada projeto no chat com
> `opus`, revise as descrições e deixe o pre-commit com `sonnet` ou `haiku` para as
> manutenções — que quase sempre envolvem um punhado de objetos.

## 9. Pre-commit

O hook está em `hooks/pre-commit`. Ele começa sempre pelos **guardrails**
(bloqueante — veja a [seção 2](#2-guardrails)), depois espelha `.claude/skills` em
`.agents/skills` (e adiciona ao commit) e segue três caminhos por projeto afetado, do
mais barato para o mais caro:

1. **Nenhum arquivo do PBIP no stage.** Sai imediatamente, sem tocar em nada. É o
   caso da maioria dos commits. Custo zero.
2. **Arquivos mudaram, mas nenhuma descrição é nova.** Você renomeou uma página,
   mexeu num visual, alterou o formato de uma medida. O hook re-renderiza a
   documentação com Python puro e adiciona ao commit. Custo zero em tokens.
3. **Há objetos novos ou alterados.** Só aqui o assistente é chamado, recebendo
   apenas a lista de mudanças **daquele projeto**. Em seguida o hook mescla,
   re-renderiza e roda `git add` na pasta de documentação — os arquivos entram
   **no mesmo commit**.

Se o commit tocar em mais de um projeto, o hook processa cada um independentemente.
A skill acionada depende de `formatos` do projeto: `negocio` → `pbi-doc-negocio`
(escopo `negocio`, que já cobre o técnico); senão `md` → `pbi-doc-md`; senão
`pbi-doc-docx`. Os campos `[PREENCHER]` do Word de negócio **não** são preenchidos
pelo hook — dependem de pessoas (bloco `negocio`).

Os arquivos observados são `*.tmdl`, `*.pbip`, `*.pbir`, `*.pbism`, `*.platform` e
o conteúdo de `definition/` do relatório e do modelo semântico, dentro de
`projetos/<nome>/`.

### Variáveis de ambiente

| Variável | Efeito |
| --- | --- |
| `PBIDOC_SKIP=1` | Pula o hook por completo (inclusive os guardrails). |
| `PBIDOC_MODEL` | Sobrescreve o modelo do `.pbidoc.json`. |
| `PBIDOC_TIMEOUT` | Segundos até desistir da chamada. Padrão: o valor do `.pbidoc.json`. |
| `PBIDOC_DEBUG=1` | Mostra a saída completa do assistente — use ao investigar um problema. |
| `PBIDOC_BACKEND=api` | Usa a Claude API em vez de uma CLI local (ver seção 11). |

```bash
# commit sem passar pelo hook
PBIDOC_SKIP=1 git commit -m "wip"
```

> **O hook nunca bloqueia o commit por falha na documentação — exceto os
> guardrails.** Se o assistente não estiver acessível, a chamada estourar o tempo
> ou a extração falhar, o hook imprime um aviso e **libera o commit**; a
> documentação fica desatualizada até o próximo commit, que a corrige sozinho
> (a comparação por hash detecta o que ficou para trás). Já um arquivo de dado
> real ou segredo em stage **sempre** bloqueia — não há como tornar isso opcional
> por design. Para tornar o restante do hook bloqueante também, troque os
> `exit 0` da função `desiste` por `exit 1` em `hooks/pre-commit`.

## 10. Revisão humana

Quando um objeto é genuinamente ambíguo — nome opaco, DAX sem semântica clara,
coluna sem contexto — a skill é instruída a **não inventar**. Ela marca o item:

```json
{
  "medida::Medidas::xpto": {
    "hash": "a1b2c3d4e5f60718",
    "descricao": "",
    "regra": "",
    "revisar": true
  }
}
```

Itens marcados aparecem na documentação com um aviso e **não são reprocessados**
nas execuções seguintes, o que evita gastar tokens repetidamente com o mesmo caso
sem saída. Para localizá-los:

```bash
python3 tools/pbidoc/pbidoc.py --projeto <nome> status
```

A correção é editar o texto direto no `_descriptions.json` do projeto, remover a
linha `"revisar"` e rodar `render`. Esse arquivo foi feito para ser editado à mão
— é a única parte da documentação onde isso faz sentido. Todo o resto é
regenerado.

> **Corrigir um texto ruim:** apague a entrada inteira do objeto em
> `_descriptions.json` e rode a skill de novo — ela verá o item como novo e
> reescreverá. Ou edite o texto na mão e rode só `render` — o hash continua
> válido, e o modelo não será chamado.

## 11. Plano B com chave de API

O caminho principal usa a CLI local e não precisa de chave. O plano B existe para
onde não há sessão interativa — tipicamente um servidor de integração contínua.

```bash
pip install anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
export PBIDOC_BACKEND=api
git commit -m "atualiza o modelo semântico"
```

O hook passa a chamar `tools/pbidoc/describe_api.py --projeto <nome>`, que envia
os objetos em lotes de 40 pela Messages API. O *system prompt* é o **mesmo
arquivo de estilo** que a skill lê, com cache de prompt ativado, e a resposta é
validada contra um esquema JSON.

Também dá para usar direto, sem passar pelo hook:

```bash
python3 tools/pbidoc/pbidoc.py --projeto <nome> extract
python3 tools/pbidoc/pbidoc.py --projeto <nome> diff
python3 tools/pbidoc/describe_api.py --projeto <nome> --model sonnet
python3 tools/pbidoc/pbidoc.py merge ".pbidoc-cache/<nome>/patch-api-*.json" --limpar
python3 tools/pbidoc/pbidoc.py --projeto <nome> render --md --docx
```

> **Diferença de cobrança:** nesse modo o consumo é cobrado por token na sua conta
> de API, e não no limite da sua assinatura. Só ative quando for realmente
> necessário.

## 12. Solução de problemas

| Mensagem ou sintoma | O que fazer |
| --- | --- |
| `CLI não encontrada (claude/opencode)` | Hooks do git rodam com `PATH` reduzido. O hook já tenta `$HOME/.local/bin/claude`; se o seu estiver em outro lugar, acrescente o caminho em `hooks/pre-commit`. |
| `Ignoring N permissions.allow entries … not been trusted` | Abra o assistente interativamente na pasta uma vez e aceite a caixa de confirmação. Não impede o funcionamento, mas remove o aviso. |
| `Template ausente` | Rode `make_template.py ... --modelo tecnico`, `--modelo negocio` ou `--modelo relatorio` apontando para o modelo em `docs/templates/` (seção 5). |
| O sumário do Word/Google Docs mostra páginas erradas | Os números gravados são uma estimativa. O Word os recalcula ao abrir (confirme a atualização de campos); no Google Docs, clique no sumário e use "Atualizar sumário". |
| Muitos arquivos aparecem como modificados sem mudança real | Diferença de fim de linha (CRLF do Windows × LF). O `.gitattributes` fixa LF; num clone antigo, rode uma vez `git add --renormalize .` ou restaure os arquivos com `git checkout -- <arquivo>`. |
| O Word de negócio está cheio de `[PREENCHER]` | Esperado: são informações que não estão no PBIP. Preencha `projetos.<nome>.negocio` no `.pbidoc.json` (`pbidoc.py status --escopo negocio` lista os campos). |
| `.agents/skills está desatualizado` (`sync_skills.py --check`) | Alguém editou uma skill sem sincronizar (ou editou `.agents/skills` à mão). Rode `python3 tools/sync_skills.py` e commite. |
| O Antigravity não bloqueia a leitura de um arquivo proibido | Confira se `.agents/hooks.json` foi carregado (`/hooks` na CLI) e se `python3` está no PATH. Teste o guard com `python3 tools/guardrails/check.py --path <arquivo>`. Sem o hook, só valem o pre-commit e a política do `AGENTS.md`. |
| `Nenhum projeto encontrado` | Confira se o PBIP está em `projetos/<nome>/` (ou na raiz, no modo de projeto único) e se há uma pasta `*.SemanticModel` e/ou `*.Report`. |
| Um projeto local não aparece no `docs/README.md` | Correto: projetos ignorados pelo git (`.git/info/exclude`) ficam fora do índice versionado. |
| O relatório conectado sai sem tabelas, M ou RLS | Esperado: esses itens estão no dataset, não no repositório. Documente também o projeto do dataset (`completo`/`modelo`) se precisar deles. |
| Leitura negada por "guardrails" | Correto — veja a [seção 2](#2-guardrails). Nunca contorne; se for um falso positivo, ajuste `tools/guardrails/policy.py` e abra um PR. |
| O assistente excedeu o tempo | Aumente `timeout` no `.pbidoc.json`, ou baixe `limite_itens_precommit` para dividir o trabalho entre commits. |
| O hook não dispara | Confira `git config core.hooksPath` (deve ser `hooks`) e se `hooks/pre-commit` tem permissão de execução. |
| A documentação saiu com _(descrição pendente)_ | Faltaram descrições. Acione a skill para completar; `status` mostra quantas faltam. |
| Aviso `chave inexistente no modelo` ao mesclar | O lote citou um objeto que não existe — normalmente um nome digitado errado. A entrada é descartada, sem efeito colateral. |
| Quero recomeçar do zero num projeto | Apague `docs/<projeto>/_descriptions.json` e rode a skill. Toda a prosa será reescrita. |

## 13. Referência de comandos

Todos aceitam `--root <caminho>` (raiz do repositório) e `--projeto NOME`
(repetível, **antes** do subcomando; sem ele, vale para todos os projetos).

| Comando | O que faz |
| --- | --- |
| `pbidoc.py init` | Registra em `.pbidoc.json` os projetos encontrados em `projetos/`. `--force` recomeça do zero. |
| `pbidoc.py projetos` | Lista os projetos (com o `tipo=` de cada um) e quantas descrições faltam. |
| `pbidoc.py extract` | Lê TMDL e PBIR e grava o manifesto em `.pbidoc-cache/<nome>/model.json`. |
| `pbidoc.py diff` | Lista o que precisa de descrição em `.pbidoc-cache/<nome>/changes.json`. `--limite N` limita o lote; `--escopo tecnico\|negocio` escolhe o catálogo. |
| `pbidoc.py merge <lotes>` | Mescla lotes de descrição, valida as chaves e carimba os hashes. `--limpar` apaga os lotes depois; `--escopo` como acima. |
| `pbidoc.py render` | Gera a documentação e o índice `docs/README.md`. `--md`, `--docx` (técnico), `--negocio`; sem flags, usa `formatos`. |
| `pbidoc.py status` | Quantas descrições estão preenchidas, quais estão marcadas para revisão e, com `--escopo negocio`, quais campos `negocio` faltam. |
| `make_template.py <modelo.docx> --modelo tecnico\|negocio\|relatorio` | Gera o template visual do Word a partir de um documento-modelo. |
| `make_modelo.py [--tipo relatorio]` | Regenera `docs/templates/Modelo - Documentacao Tecnica.docx` (ou o de relatório) a partir do renderizador, com um projeto fictício. |
| `sync_skills.py [--check]` | Espelha `.claude/skills` em `.agents/skills` (Antigravity); `--check` só verifica. |
| `describe_api.py --projeto NOME --model X` | Plano B: escreve as descrições pela Claude API. |
| `guardrails/check.py --path/--bash/--staged` | Testa a política de bloqueio de leitura. |

### Ciclo completo na mão, um projeto

```bash
python3 tools/pbidoc/pbidoc.py --projeto vendas extract
python3 tools/pbidoc/pbidoc.py --projeto vendas diff --escopo negocio
# a skill escreve .pbidoc-cache/vendas/patch-NN.json
python3 tools/pbidoc/pbidoc.py merge .pbidoc-cache/vendas/patch-*.json --limpar --escopo negocio
python3 tools/pbidoc/pbidoc.py --projeto vendas render --md --docx --negocio
```

---

Documentação gerada e mantida pelo pipeline `pbidoc`. A pasta `.pbidoc-cache/` é
temporária e está no `.gitignore`; `_descriptions.json`, `_model.json` e
`_meta.json` são versionados de propósito — é o que permite a comparação
incremental entre commits.
