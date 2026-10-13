# Layout do servidor Yoru

Servidor para divulgar as novidades do **projeto Yoru**. Estilo dos nomes: emoji + `│` +
nome (ex.: `📖│regras`), com categorias em maiúsculas (`📌 | INÍCIO`).

- Servidor: **Yoru** (`1559555589120598057`)
- Dono: `558336516959502336`

## Estrutura final

| Categoria | Canais | Quem escreve |
|---|---|---|
| 📌 \| INÍCIO | 📖│regras · 👋│boas-vindas · 📢│anúncios | só a equipe |
| 🌙 \| PROJETO YORU | 📰│novidades · 🛠️│patch-notes* · 🚀│releases* · 🗺️│roadmap · 🖼️│galeria | só a equipe |
| 💬 \| COMUNIDADE | 💭│chat-geral* · 💡│sugestões · 🐞│reportar-bugs · ❓│dúvidas · 🎨│fanarts | todos |
| 🔊 \| CALLS | 💬 \| Bate-papo* (voz) · 🎙️ \| Devlog ao vivo (voz) · 💤 \| AFK (voz) | todos |
| 🔒 \| STAFF | 🔒│staff-chat · 📋│planejamento · 🔊 \| Reunião (voz) | só Equipe e Moderador veem |

\* canais que já existem e serão **renomeados e movidos** (mantêm as mensagens):

| Hoje | Vira | Categoria |
|---|---|---|
| `#geral` (`1559555589804261419`) | `💭│chat-geral` | 💬 \| COMUNIDADE |
| `#patch-notes` (`1559556066226741248`) | `🛠️│patch-notes` | 🌙 \| PROJETO YORU |
| `#release` (`1559556081364238447`) | `🚀│releases` | 🌙 \| PROJETO YORU |
| voz `Geral` (`1559555589804261420`) | `💬 \| Bate-papo` | 🔊 \| CALLS |

As categorias antigas `Canais de Texto` (`1559555589804261417`) e `Canais de Voz`
(`1559555589804261418`) ficam vazias e são **excluídas** (pedir confirmação).

### Cargos

| Cargo | Cor | Permissões |
|---|---|---|
| 🌙 Equipe Yoru | `#8B5CF6` | separado na lista; gerenciar mensagens, castigo, expulsar, gerenciar threads e apelidos, mencionar @everyone |
| 🛡️ Moderador | `#3BA55C` | separado na lista; gerenciar mensagens, castigo, gerenciar threads e apelidos |
| 🧪 Beta Tester | `#1ABC9C` | separado na lista, mencionável; sem permissões extras (quem testa as versões beta) |
| 🔔 Notificações Yoru | `#FEE75C` | mencionável; sem permissões (ping quando sair novidade) |

O dono recebe o cargo 🌙 Equipe Yoru. Os devs do projeto são a staff: também recebem 🌙 Equipe Yoru.

## Passos para o Claude Code

Use `.venv/bin/python -m bot.cli` (veja `CLAUDE.md`). Antes de começar, rode
`run get_server_info` e confira se os IDs acima ainda existem; se algo mudou, adapte e
avise o usuário.

### 1. Criar cargos, categorias e canais novos

```bash
.venv/bin/python -m bot.cli run setup_server_structure - <<'JSON'
{
  "roles": [
    {"name": "🌙 Equipe Yoru", "color": "#8B5CF6", "hoist": true,
     "permissions": ["manage_messages", "moderate_members", "kick_members",
                     "manage_threads", "manage_nicknames", "mention_everyone"]},
    {"name": "🛡️ Moderador", "color": "#3BA55C", "hoist": true,
     "permissions": ["manage_messages", "moderate_members", "manage_threads",
                     "manage_nicknames"]},
    {"name": "🔔 Notificações Yoru", "color": "#FEE75C", "mentionable": true}
  ],
  "categories": [
    {"name": "📌 | INÍCIO", "read_only": true, "write_roles": ["🌙 Equipe Yoru"],
     "channels": [
       {"name": "📖│regras", "type": "text", "topic": "Leia antes de participar."},
       {"name": "👋│boas-vindas", "type": "text", "topic": "Boas-vindas ao servidor do projeto Yoru!"},
       {"name": "📢│anúncios", "type": "text", "topic": "Avisos importantes da equipe Yoru."}
     ]},
    {"name": "🌙 | PROJETO YORU", "read_only": true, "write_roles": ["🌙 Equipe Yoru"],
     "channels": [
       {"name": "📰│novidades", "type": "text", "topic": "Tudo o que há de novo no projeto Yoru."},
       {"name": "🗺️│roadmap", "type": "text", "topic": "O que está planejado para o Yoru."},
       {"name": "🖼️│galeria", "type": "text", "topic": "Prints, artes e bastidores do desenvolvimento."}
     ]},
    {"name": "💬 | COMUNIDADE",
     "channels": [
       {"name": "💡│sugestões", "type": "text", "topic": "Ideias para o projeto Yoru."},
       {"name": "🐞│reportar-bugs", "type": "text", "topic": "Encontrou um problema? Descreva aqui como reproduzir."},
       {"name": "❓│dúvidas", "type": "text", "topic": "Perguntas sobre o projeto."},
       {"name": "🎨│fanarts", "type": "text", "topic": "Artes e criações da comunidade."}
     ]},
    {"name": "🔊 | CALLS",
     "channels": [
       {"name": "🎙️ | Devlog ao vivo", "type": "voice"},
       {"name": "💤 | AFK", "type": "voice"}
     ]},
    {"name": "🔒 | STAFF", "private_to_roles": ["🌙 Equipe Yoru", "🛡️ Moderador"],
     "channels": [
       {"name": "🔒│staff-chat", "type": "text"},
       {"name": "📋│planejamento", "type": "text"},
       {"name": "🔊 | Reunião", "type": "voice"}
     ]}
  ]
}
JSON
```

### 2. Mover e renomear os canais existentes

Rode `run get_server_info` para pegar os IDs das categorias novas e então um `batch`
com `edit_channel` para os 4 canais da tabela acima, usando `category_id` da categoria
nova e `sync_permissions: true` (assim patch-notes e releases ficam somente leitura).

### 3. Ajustes finais

- `edit_server` com `system_channel_id` = ID do `👋│boas-vindas`.
- `update_member_roles`: dar `🌙 Equipe Yoru` ao dono (`558336516959502336`).
- Ordenar com `edit_channel` + `position` se a ordem dentro das categorias ficar
  diferente da tabela (ordem desejada em PROJETO YORU: novidades, patch-notes,
  releases, roadmap, galeria; em COMUNIDADE: chat-geral primeiro).

### 4. Ações que precisam de confirmação

Mostre ao usuário e só rode com `--confirm` depois que ele aprovar:

- `delete_channel` nas categorias antigas `Canais de Texto` e `Canais de Voz` (só se
  estiverem vazias).

### 5. Opcional (perguntar antes)

Publicar com `send_message` (embed) as regras em `📖│regras` e uma mensagem de
boas-vindas em `👋│boas-vindas`. Rascunho das regras:

1. Respeite todos os membros; sem ofensas, preconceito ou assédio.
2. Sem spam, flood ou divulgação sem permissão.
3. Use cada canal para o seu assunto.
4. Bugs vão em 🐞│reportar-bugs, ideias em 💡│sugestões.
5. Sem conteúdo NSFW.
6. Siga os Termos de Serviço do Discord.
