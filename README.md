# dalvi-kit

Minhas skills para agentes de código, reunidas num plugin só.

As skills seguem o padrão aberto [Agent Skills](https://agentskills.io), então
o mesmo repositório serve o Claude Code e outros harnesses.

## Instalação

Escolha uma forma por harness. Instalar de duas formas no mesmo harness
duplica as skills.

### Claude Code

```
/plugin marketplace add leonardodalvi/dalvi-kit
/plugin install dalvi-kit@leonardodalvi
```

### Codex

```bash
codex plugin marketplace add leonardodalvi/dalvi-kit
codex plugin add dalvi-kit@leonardodalvi
```

### GitHub Copilot (CLI e VS Code)

```bash
copilot plugin marketplace add leonardodalvi/dalvi-kit
copilot plugin install dalvi-kit@leonardodalvi
```

No VS Code, também dá para rodar **Chat: Install Plugin From Source** com
`https://github.com/leonardodalvi/dalvi-kit`.

### Gemini CLI

```bash
gemini skills install https://github.com/leonardodalvi/dalvi-kit.git --path plugins/dalvi-kit/skills
```

### Cursor, OpenCode, Windsurf, Amp e outros

```bash
npx skills@latest add leonardodalvi/dalvi-kit -a <agente>
```

Sem `-a`, o instalador pergunta para quais agentes instalar. Essa forma copia
os arquivos e não se atualiza sozinha: rode `npx skills@latest update`.

## Skills

| Skill | Como aciona | O que faz |
| --- | --- | --- |
| `grill-me` | Só você (no Claude Code, `/dalvi-kit:grill-me`) | Entrevista em rodadas que transforma uma ideia solta em decisões tomadas por você |
| `grilling` | O agente aciona sozinho, ou o `grill-me` chama | O método da entrevista: árvore de decisões, fronteira, rodadas com resposta recomendada, confirmação antes de agir |
| `web-design-guidelines` | O agente aciona sozinho quando você pede revisão de UI, acessibilidade ou UX | Revisa código de interface contra as Web Interface Guidelines da Vercel e aponta cada problema em `arquivo:linha` |
| `playwright-cli` | O agente aciona sozinho quando precisa usar um navegador ou rodar testes Playwright | Abre e controla um navegador pelo `playwright-cli` (navegar, clicar, preencher, capturar tela, gravar vídeo, simular requisições) e roda, depura e gera testes Playwright |
| `prod-data-guard` | O agente aciona sozinho quando vai ler ou alterar dado de produção (banco, API REST, carga em massa) | Explora só a estrutura, sem imprimir valor de campo. Para alterar, faz ensaio sem gravar, pede confirmação digitada, aplica, confere linha a linha contra a fonte e apaga os temporários com dado pessoal |
| `session-closeout` | O agente aciona só quando você pede, com essas palavras, para encerrar a sessão ("encerra a sessão", "wrap up") | Registra os procedimentos e as soluções achadas depois de um erro, anexa uma entrada ao log do dia, reescreve o estado e commita só os arquivos que a sessão tocou, sem levar junto o trabalho de outras sessões |
| `meeting-minutes` | O agente aciona sozinho quando há transcrição ou gravação de reunião para virar ata (`.vtt`, export do Teams, texto de gravador) | Transforma a transcrição em diálogo legível e escreve a ata com as decisões (e quem decidiu) e as ações (responsável, prazo, critério de aceite). Grava a ata no lugar que a regra de privacidade do projeto define e encaminha cada decisão e cada ação ao destino do projeto, pedindo confirmação antes de criar item ou mandar mensagem num sistema externo |

O `playwright-cli` precisa do programa instalado: `npm install -g @playwright/cli@latest`,
ou um Playwright local no projeto (`npx playwright cli`). No Claude Code, a skill
declara `allowed-tools`, que libera os comandos `playwright-cli` e
`npx playwright` sem pedir confirmação enquanto ela está ativa.

As regras do `web-design-guidelines` ficam numa cópia fixa dentro da skill
(`references/command.md`), em vez de serem baixadas a cada revisão. Para
atualizar, baixe de novo o `command.md` do
[vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines)
e troque o commit citado no `SKILL.md` e em `THIRD_PARTY_NOTICES.md`.

O `prod-data-guard` traz o método, não as regras de cada lugar. Quais sistemas
são somente leitura, quem confirma uma alteração e com que palavra, e onde
podem ficar os arquivos temporários ficam no `CLAUDE.md` ou no `AGENTS.md` do
projeto, e a skill manda procurar ali. Sem regra no projeto, ela pede a
confirmação a quem fez o pedido.

O `session-closeout` também traz só o método. Onde ficam os procedimentos, o
log do dia e o arquivo de estado, o formato da mensagem de commit, os trailers
proibidos e se pode dar push ficam no `CLAUDE.md` ou no `AGENTS.md` do projeto.
Sem regra no projeto, ela não cria pastas de registro no repositório: deixa uma
nota de passagem na pasta temporária do sistema e faz um commit local, sem push.
Arquivo que outra sessão também alterou entra só com as linhas desta sessão; o
que já existia sem estar no git, como o log do dia começado por outra sessão,
fica fora do commit, e ela avisa.

O `meeting-minutes` também traz só o método. Onde ficam as atas, quais reuniões
são privadas (conversa a dois, reunião que discute pessoa identificada) e o que
não pode sair da pasta delas, e para onde vão as decisões e as ações ficam no
`CLAUDE.md` ou no `AGENTS.md` do projeto. A reunião é classificada inteira: se
uma parte dela é privada, a ata toda vai para a pasta privada, e o conteúdo não
sai de lá sem o seu aval, item por item. Sem regra no projeto, se a reunião
tem dado pessoal, ela pergunta onde gravar antes de escrever qualquer arquivo.
O conversor `scripts/transcript_to_dialogue.py` precisa de Python 3, sem
dependências; sem Python, o agente faz a mesma limpeza lendo o arquivo.

## Estrutura

```
.claude-plugin/marketplace.json    o marketplace "leonardodalvi"
plugins/dalvi-kit/
  .claude-plugin/plugin.json       o plugin e a versão
  skills/<nome>/SKILL.md           uma pasta por skill
  skills/<nome>/agents/openai.yaml nome e regra de acionamento no Codex
```

## Adicionar uma skill

1. Crie `plugins/dalvi-kit/skills/<nome>/SKILL.md` com `name` e `description`
   no frontmatter. O `name` é igual ao nome da pasta.
2. Crie `agents/openai.yaml` ao lado, com `interface.display_name` e
   `interface.short_description`.
3. Se só você deve acionar a skill, marque nos dois arquivos:
   `disable-model-invocation: true` no `SKILL.md` (Claude Code) e
   `policy.allow_implicit_invocation: false` no `openai.yaml` (Codex).
4. Se ela chamar outra skill do kit, use o nome puro, que vale em qualquer
   harness: `Call the Skill tool with "<nome>"`. Pode acrescentar que, no
   Claude Code, ela aparece como `dalvi-kit:<nome>`.
5. Suba a `version` em `plugins/dalvi-kit/.claude-plugin/plugin.json`.
6. Valide: `claude plugin validate .` e `claude plugin validate ./plugins/dalvi-kit`.
7. Faça commit e push. No Claude Code de cada máquina:
   `claude plugin marketplace update leonardodalvi` e depois
   `claude plugin update dalvi-kit@leonardodalvi`.

## Créditos

- `grill-me` e `grilling` vêm de
  [mattpocock/skills](https://github.com/mattpocock/skills), sob licença MIT.
- `web-design-guidelines` vem de
  [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills), e as
  regras, de
  [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines),
  ambos sob licença MIT.
- `playwright-cli` vem de
  [microsoft/playwright-cli](https://github.com/microsoft/playwright-cli), sob
  licença Apache 2.0, com o texto da licença dentro da pasta da skill.
- `prod-data-guard` foi escrita para este kit. As consultas de PostgreSQL em
  `references/exploration-recipes.md` adaptam a skill `schema-exploration` de
  [timescale/pg-aiguide](https://github.com/timescale/pg-aiguide), sob licença
  Apache 2.0, com a licença e o `NOTICE` dentro da pasta da skill.
- `session-closeout` foi escrita para este kit, a partir da skill `handoff` de
  [mattpocock/skills](https://github.com/mattpocock/skills), sob licença MIT,
  com inspiração na `retro` do mesmo repositório. Da `wrap-up` de
  [rohitg00/pro-workflow](https://github.com/rohitg00/pro-workflow), que não
  declara licença, vieram só ideias, sem texto copiado.
- `meeting-minutes` adapta a skill `meeting-minutes` de
  [github/awesome-copilot](https://github.com/github/awesome-copilot), sob
  licença MIT. A leitura de transcrição, a regra de privacidade antes de
  escrever e o encaminhamento com confirmação foram acrescentados para este kit.

Os avisos de copyright e as licenças estão em
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
