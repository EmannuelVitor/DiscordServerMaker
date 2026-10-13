# Discord Server Maker (com Claude)

Bot de Discord que conversa com o **Claude** (API da Anthropic) para **criar, editar,
organizar e moderar** servidores. Você escreve o pedido em linguagem natural e o Claude
decide quais ações executar no servidor por meio de ferramentas (tool use).

```
@ServerMaker monte um servidor para uma comunidade de jogos, com cargos de Staff,
Membro e VIP, categorias de texto e voz e um canal de regras
```

## O que ele faz

| Área | Ferramentas |
|---|---|
| Leitura | ver estrutura do servidor, permissões de um canal, listar membros, ler mensagens recentes |
| Canais | criar (texto, voz, fórum, palco, anúncios, categoria), editar, mover, excluir, permissões por cargo/membro |
| Cargos | criar, editar (cor, permissões, posição), excluir, dar/remover cargos de membros |
| Moderação | castigo (timeout), expulsar, banir/desbanir, apagar mensagens em massa |
| Servidor | nome, descrição, nível de verificação, canal do sistema, convites, enviar mensagens/embeds |
| Montagem rápida | `setup_server_structure`: cria cargos, categorias e canais em lote a partir de um tema |

### Segurança

- **Quem pode usar:** quem tem *Gerenciar Servidor*/*Administrador*, ou um cargo listado em
  `ALLOWED_ROLE_IDS`.
- **O Claude age com as permissões de quem pediu.** Se você não pode banir, o Claude também
  não banirá por você. A hierarquia de cargos também é respeitada, e ninguém consegue usar o
  bot para conceder permissões que não tem.
- **Confirmação por botão** antes de qualquer ação destrutiva (excluir canal/cargo, expulsar,
  banir, apagar mensagens). Só quem fez o pedido pode confirmar.
- Toda ação fica no **registro de auditoria** do Discord com o nome de quem pediu.
- Mensagens lidas do servidor são tratadas como dados, não como instruções para o Claude.

> **Observação:** a API do Discord não permite mais que bots criem servidores novos. Para
> "criar um servidor", crie um servidor vazio pelo app, convide o bot e peça para ele montar
> tudo.

## Instalação

Requisitos: Python 3.10+, uma conta no [Discord Developer Portal](https://discord.com/developers/applications)
e uma chave da [API da Anthropic](https://console.anthropic.com).

### 1. Criar o bot no Discord

1. Em **Applications → New Application**, crie o app.
2. Na aba **Bot**: clique em **Reset Token** e copie o token.
3. Ainda em **Bot**, em *Privileged Gateway Intents*, ative **Server Members Intent** e
   **Message Content Intent**.
4. Convide o bot (troque `SEU_CLIENT_ID` pelo *Application ID* da aba **General Information**):

   ```
   https://discord.com/oauth2/authorize?client_id=SEU_CLIENT_ID&scope=bot+applications.commands&permissions=8
   ```

   `permissions=8` é Administrador, o mais simples. Se preferir permissões específicas, dê
   pelo menos: Gerenciar Canais, Gerenciar Cargos, Gerenciar Servidor, Gerenciar Mensagens,
   Expulsar, Banir, Moderar Membros, Criar Convite, Ver Canais, Enviar Mensagens e Ler
   Histórico.
5. Em **Configurações do servidor → Cargos**, arraste o cargo do bot para o topo: o bot só
   consegue gerenciar cargos e membros abaixo dele.

### 2. Rodar

```bash
git clone https://github.com/EmannuelVitor/DiscordServerMaker.git
cd DiscordServerMaker
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # preencha DISCORD_TOKEN e ANTHROPIC_API_KEY
python -m bot
```

## Como usar

- **Menção:** `@ServerMaker <pedido>`.
- **Comando de barra:** `/claude pedido:<pedido>`.
- `/claude-reset` apaga a memória da conversa no canal atual.
- `/claude-ajuda` mostra exemplos.

A conversa é lembrada por canal, então dá para ir refinando: *"agora deixe a categoria Staff
privada"*, *"troque a cor do VIP para dourado"*.

Exemplos:

- `crie uma categoria "Eventos" com um canal de anúncios e dois canais de voz`
- `deixe #regras somente leitura para @everyone`
- `crie o cargo Moderador com permissão de apagar mensagens e dar castigo, e dê para @fulano`
- `leia as últimas 30 mensagens de #geral e dê castigo de 1h para quem estiver fazendo spam`
- `apague as últimas 50 mensagens de @spammer em #geral`
- `escreva e publique as regras do servidor em #regras em um embed`

## Configuração (`.env`)

| Variável | Padrão | Descrição |
|---|---|---|
| `DISCORD_TOKEN` | — | Token do bot (obrigatório) |
| `ANTHROPIC_API_KEY` | — | Chave da API da Anthropic |
| `CLAUDE_MODEL` | `claude-opus-5-5` | Modelo usado |
| `CLAUDE_EFFORT` | `medium` | Esforço de raciocínio: `low`, `medium`, `high`, `xhigh`, `max` |
| `ALLOWED_ROLE_IDS` | vazio | Cargos extras que podem usar o bot (IDs separados por vírgula) |
| `REQUIRE_CONFIRMATION` | `true` | Pedir confirmação em ações destrutivas |
| `CONFIRM_TIMEOUT_SECONDS` | `60` | Tempo para confirmar |
| `MAX_TOOL_ROUNDS` | `25` | Máximo de rodadas de ferramentas por pedido |
| `MAX_HISTORY_MESSAGES` | `80` | Tamanho do histórico antes de reiniciar a conversa do canal |
| `DEV_GUILD_ID` | vazio | Sincroniza os comandos de barra na hora neste servidor |

O bot usa *prompt caching* e, se o modelo recusar um pedido, a API tenta de novo
automaticamente em outro modelo (*server-side fallback*). Cada pedido consome tokens da
sua conta da Anthropic; montar um servidor inteiro costuma levar algumas rodadas de
ferramentas.

## Estrutura

```
bot/
  __main__.py   # cliente do Discord, menções e comandos de barra
  agent.py      # loop de conversa com o Claude (tool use)
  tools.py      # ferramentas do Discord + checagem de permissões
  confirm.py    # botões de confirmação
  config.py     # leitura do .env
tests/          # testes offline: python -m unittest
```

### Adicionar uma ferramenta

Em `bot/tools.py`, decore uma função assíncrona com `@tool(...)`, informando nome, descrição,
propriedades do schema JSON e as permissões do Discord que o solicitante precisa ter. Ela
passa a ser oferecida ao Claude automaticamente.
