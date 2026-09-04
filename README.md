# Template de documentação com IA para projetos Power BI (PBIP)

Duas skills, um pipeline determinístico e um *hook* de pre-commit que mantêm a
documentação de um ou mais modelos semânticos Power BI sempre igual ao que está
publicado — em Markdown e em Word — gastando o mínimo possível de tokens. Funciona
com o Claude Code e com qualquer harness que leia `AGENTS.md` (testado com
OpenCode).

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

tools/
├── pbidoc/                pipeline determinístico (extração + render)
└── guardrails/            política de bloqueio de leitura

.claude/
├── settings.json          modelo, permissões, hook de guardrails (Claude Code)
└── skills/
    ├── pbi-doc-md/        gera a documentação em Markdown
    ├── pbi-doc-docx/      gera a documentação em Word
    └── guardrails/        política de segurança, explicada para o assistente

.opencode/plugins/pbi-guard.js   mesmo guardrail, para o OpenCode
opencode.json                     configuração do OpenCode
hooks/pre-commit                  mantém docs/ sincronizado a cada commit
AGENTS.md                         instruções universais (qualquer harness)
```

Veja [`projetos/README.md`](projetos/README.md) para o passo a passo de adicionar
um projeto.

## 4. O que é gerado

Tudo vai para `docs/<projeto>/`. Os dois formatos leem o mesmo
`_descriptions.json`, então gerar os dois não custa o dobro.

```
docs/<projeto>/
├── README.md                      página principal: visão geral + índice
├── 01-medidas.md                  medidas DAX, regra de cálculo, dependências
├── 02-tabelas.md                  tabelas, colunas, colunas calculadas, RLS
├── 03-queries-m.md                parâmetros, incremental, código M passo a passo
├── 04-modelo-relacional.md        diagrama Mermaid + propriedades dos relacionamentos
├── <TÍTULO> - Glossário de Dados.docx   tudo num arquivo só
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

### Word

O `.docx` não é montado do zero: ele é uma cópia de
`tools/pbidoc/assets/template.docx`, **gerado localmente** (não versionado) a
partir de um documento de referência da sua equipe. Estilos, fontes embutidas,
tema, cabeçalho com logotipo, rodapé e margens vêm byte a byte do original.

Fontes e cores do corpo do texto usam, por padrão, uma paleta neutra (Calibri +
tons de cinza/azul); para usar a identidade visual da sua equipe, defina
`estilo_docx` no `.pbidoc.json` — veja
[`.claude/skills/pbi-doc-docx/reference/estrutura.md`](.claude/skills/pbi-doc-docx/reference/estrutura.md).

Tabelas são a única adição ao repertório do documento de referência, que só tem
parágrafos: sem elas, um dicionário com centenas de colunas ficaria ilegível. Como
o Word não renderiza Mermaid, o diagrama vira a tabela de relacionamentos, com as
mesmas informações e mais colunas. A navegação é feita pelo índice com links
internos.

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
   `opencode` na pasta uma vez.

3. **Adicionar um projeto PBIP** — veja [`projetos/README.md`](projetos/README.md).
   Depois, registre-o:

   ```bash
   python3 tools/pbidoc/pbidoc.py init
   ```

4. **Gerar o template do Word** — só é necessário se você for usar o formato
   `.docx` e tiver um documento de referência para herdar a identidade visual
   (senão, o padrão neutro é usado sem nenhum passo extra):

   ```bash
   python3 tools/pbidoc/make_template.py "<caminho/para/referencia.docx>"
   ```

### Requisitos

Python 3 e git. Não é preciso instalar nenhuma biblioteca: `python-docx`,
`pandoc` e `libreoffice` **não** são usados — o `.docx` é montado com a biblioteca
padrão do Python. Para a etapa de descrição, basta o assistente (Claude Code ou
OpenCode) instalado e autenticado; chave de API só é necessária no plano B
([seção 11](#11-plano-b-com-chave-de-api)).

## 6. Usar no chat

As duas skills funcionam pedindo em linguagem natural — "documente o projeto
`vendas`", "atualize a documentação das medidas", "gere o glossário em Word do
projeto `rh`" — ou acionando-as pelo nome, dependendo do harness (`/pbi-doc-md` no
Claude Code, por exemplo).

| Skill | O que faz |
| --- | --- |
| `pbi-doc-md` | Gera ou atualiza os cinco arquivos Markdown em `docs/<projeto>/`. |
| `pbi-doc-docx` | Gera ou atualiza o glossário único em `.docx`. |
| as duas | Rodar as duas não duplica o custo: a prosa já escrita é reaproveitada integralmente. |

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
| `formatos` | `["md", "docx"]` | Quais formatos gerar. Remova um para acelerar o pre-commit. |
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
| `estilo_docx` | paleta neutra | Fontes/cores do `.docx` — veja a seção 4. |

Exemplo com dois projetos, um deles com overrides:

```json
{
  "modelo": "sonnet",
  "formatos": ["md", "docx"],
  "projetos": {
    "vendas": { "titulo": "VENDAS", "modelo": "opus" },
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
(bloqueante — veja a [seção 2](#2-guardrails)), depois segue três caminhos por
projeto afetado, do mais barato para o mais caro:

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
| `Template ausente` | Rode `make_template.py` apontando para o `.docx` de referência (seção 5). |
| `Nenhum projeto encontrado` | Confira se o PBIP está em `projetos/<nome>/` (ou na raiz, no modo de projeto único) e se há uma pasta `*.SemanticModel`. |
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
| `pbidoc.py projetos` | Lista os projetos do repositório e quantas descrições faltam em cada um. |
| `pbidoc.py extract` | Lê TMDL e PBIR e grava o manifesto em `.pbidoc-cache/<nome>/model.json`. |
| `pbidoc.py diff` | Lista o que precisa de descrição em `.pbidoc-cache/<nome>/changes.json`. `--limite N` limita o lote. |
| `pbidoc.py merge <lotes>` | Mescla lotes de descrição, valida as chaves e carimba os hashes. `--limpar` apaga os lotes depois. |
| `pbidoc.py render` | Gera a documentação e o índice `docs/README.md`. `--md`, `--docx` ou ambos; sem flags, usa `formatos`. |
| `pbidoc.py status` | Quantas descrições estão preenchidas e quais estão marcadas para revisão. |
| `make_template.py <ref.docx>` | Gera o template visual do Word a partir de um documento de referência. |
| `describe_api.py --projeto NOME --model X` | Plano B: escreve as descrições pela Claude API. |
| `guardrails/check.py --path/--bash/--staged` | Testa a política de bloqueio de leitura. |

### Ciclo completo na mão, um projeto

```bash
python3 tools/pbidoc/pbidoc.py --projeto vendas extract
python3 tools/pbidoc/pbidoc.py --projeto vendas diff
# a skill escreve .pbidoc-cache/vendas/patch-NN.json
python3 tools/pbidoc/pbidoc.py merge .pbidoc-cache/vendas/patch-*.json --limpar
python3 tools/pbidoc/pbidoc.py --projeto vendas render --md --docx
```

---

Documentação gerada e mantida pelo pipeline `pbidoc`. A pasta `.pbidoc-cache/` é
temporária e está no `.gitignore`; `_descriptions.json`, `_model.json` e
`_meta.json` são versionados de propósito — é o que permite a comparação
incremental entre commits.
