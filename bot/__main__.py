"""Ponto de entrada: `python -m bot`."""

from __future__ import annotations

import logging
import re

import discord
from discord import app_commands

from .agent import ClaudeAgent
from .config import Config
from .tools import ToolContext

log = logging.getLogger("bot")

HELP_TEXT = """\
**Claude Server Maker** — converse com o Claude para administrar este servidor.

Como usar: mencione o bot (`@Bot seu pedido`) ou use `/claude pedido:...`.
Exemplos:
• `monte um servidor de comunidade de jogos com cargos, regras e canais de voz`
• `crie uma categoria Staff visível só para o cargo Moderador`
• `renomeie #geral para #bate-papo e coloque modo lento de 10s`
• `dê castigo de 30 minutos para @fulano por spam`
• `leia as últimas 20 mensagens de #geral e veja se alguém quebrou as regras`

`/claude-reset` apaga a memória da conversa neste canal.
Ações destrutivas (excluir, expulsar, banir, apagar mensagens) pedem confirmação.\
"""


def chunk(text: str, size: int = 1900) -> list[str]:
    """Divide o texto respeitando o limite de 2000 caracteres do Discord."""
    parts: list[str] = []
    while len(text) > size:
        cut = text.rfind("\n", 0, size)
        if cut <= 0:
            cut = size
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text.strip():
        parts.append(text)
    return parts or ["(sem resposta)"]


class ServerMakerBot(discord.Client):
    def __init__(self, config: Config):
        intents = discord.Intents.default()
        intents.message_content = True  # ler pedidos feitos por menção
        intents.members = True  # listar membros e checar cargos
        super().__init__(
            intents=intents,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        self.config = config
        self.agent = ClaudeAgent(config)
        self.tree = app_commands.CommandTree(self)
        self._register_commands()

    # ------------------------------------------------------------------
    # Controle de acesso
    # ------------------------------------------------------------------

    def can_use(self, member: discord.Member) -> bool:
        perms = member.guild_permissions
        if perms.administrator or perms.manage_guild:
            return True
        return any(role.id in self.config.allowed_role_ids for role in member.roles)

    def make_context(self, member: discord.Member, channel, send) -> ToolContext:
        return ToolContext(
            guild=member.guild,
            requester=member,
            channel=channel,
            send=send,
            require_confirmation=self.config.require_confirmation,
            confirm_timeout=self.config.confirm_timeout,
        )

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------

    async def setup_hook(self) -> None:
        if self.config.dev_guild_id:
            guild = discord.Object(id=self.config.dev_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def on_ready(self) -> None:
        log.info("Conectado como %s em %d servidores", self.user, len(self.guilds))

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None or self.user is None:
            return
        if self.user not in message.mentions:
            return
        member = message.author
        if not isinstance(member, discord.Member):
            return

        text = re.sub(rf"<@!?{self.user.id}>", "", message.content).strip()
        if not text or text.lower() in {"ajuda", "help"}:
            await message.reply(HELP_TEXT)
            return
        if not self.can_use(member):
            await message.reply(
                "Você precisa da permissão **Gerenciar Servidor** (ou de um cargo "
                "autorizado) para usar o Claude aqui."
            )
            return

        async def send(content: str, **kwargs) -> discord.Message:
            return await message.channel.send(content, **kwargs)

        ctx = self.make_context(member, message.channel, send)
        async with message.channel.typing():
            reply = await self.agent.run(ctx, text, on_progress=self._progress(send))
        parts = chunk(reply)
        await message.reply(parts[0])
        for part in parts[1:]:
            await message.channel.send(part)

    @staticmethod
    def _progress(send):
        async def on_progress(text: str) -> None:
            for part in chunk(text):
                await send(f"💭 {part}")

        return on_progress

    # ------------------------------------------------------------------
    # Comandos de barra
    # ------------------------------------------------------------------

    def _register_commands(self) -> None:
        @self.tree.command(name="claude", description="Peça ao Claude para criar, editar ou moderar o servidor")
        @app_commands.describe(pedido="O que você quer que o Claude faça")
        @app_commands.guild_only()
        async def claude(interaction: discord.Interaction, pedido: str) -> None:
            member = interaction.user
            if not isinstance(member, discord.Member) or not self.can_use(member):
                await interaction.response.send_message(
                    "Você precisa da permissão **Gerenciar Servidor** (ou de um cargo "
                    "autorizado) para usar o Claude aqui.",
                    ephemeral=True,
                )
                return
            await interaction.response.defer(thinking=True)

            async def send(content: str, **kwargs) -> discord.Message:
                return await interaction.followup.send(content, wait=True, **kwargs)

            await send(f"> **{member.display_name}:** {pedido[:1800]}")
            ctx = self.make_context(member, interaction.channel, send)
            reply = await self.agent.run(ctx, pedido, on_progress=self._progress(send))
            for part in chunk(reply):
                await send(part)

        @self.tree.command(name="claude-reset", description="Apaga a memória da conversa com o Claude neste canal")
        @app_commands.guild_only()
        async def claude_reset(interaction: discord.Interaction) -> None:
            member = interaction.user
            if not isinstance(member, discord.Member) or not self.can_use(member):
                await interaction.response.send_message("Sem permissão.", ephemeral=True)
                return
            self.agent.reset(interaction.channel_id or 0)
            await interaction.response.send_message("🧹 Conversa reiniciada neste canal.")

        @self.tree.command(name="claude-ajuda", description="Mostra como usar o Claude Server Maker")
        async def claude_help(interaction: discord.Interaction) -> None:
            await interaction.response.send_message(HELP_TEXT, ephemeral=True)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = Config.from_env()
    bot = ServerMakerBot(config)
    bot.run(config.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
