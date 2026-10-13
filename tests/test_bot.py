"""Testes offline (sem Discord nem API real): `python -m unittest`."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

os.environ.setdefault("ANTHROPIC_API_KEY", "test")

from bot.__main__ import chunk  # noqa: E402
from bot.cli import _run_calls  # noqa: E402
from bot.agent import ClaudeAgent  # noqa: E402
from bot.config import Config  # noqa: E402
from bot.tools import ToolContext, execute_tool  # noqa: E402


def make_ctx(perms: discord.Permissions) -> ToolContext:
    guild = MagicMock()
    guild.id = 1
    guild.name = "Teste"
    guild.owner_id = 999
    requester = MagicMock()
    requester.id = 10
    requester.name = "pessoa"
    requester.display_name = "Pessoa"
    requester.guild_permissions = perms
    requester.top_role.name = "Admin"
    channel = MagicMock()
    channel.id = 50
    channel.name = "geral"
    return ToolContext(
        guild=guild, requester=requester, channel=channel, send=AsyncMock(),
        require_confirmation=True, confirm_timeout=5,
    )


def response(stop_reason, *blocks):
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocks))


def text(t):
    return SimpleNamespace(type="text", text=t)


def tool_use(id_, name, input_):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=input_)


class ToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_denied_without_permission(self):
        ctx = make_ctx(discord.Permissions.none())
        content, is_error = await execute_tool(ctx, "create_channel", {"name": "x", "type": "text"})
        self.assertTrue(is_error)
        self.assertIn("manage_channels", content)

    async def test_unknown_field_rejected(self):
        ctx = make_ctx(discord.Permissions(administrator=True))
        content, is_error = await execute_tool(ctx, "get_server_info", {"foo": 1})
        self.assertTrue(is_error)

    async def test_delete_cancelled(self):
        ctx = make_ctx(discord.Permissions(manage_channels=True))
        channel = MagicMock()
        channel.name = "lixo"
        channel.delete = AsyncMock()
        ctx.guild.get_channel.return_value = channel
        ctx.confirm = AsyncMock(return_value=False)
        content, is_error = await execute_tool(ctx, "delete_channel", {"channel_id": "123"})
        self.assertFalse(is_error)
        self.assertIn("cancelada", content)
        channel.delete.assert_not_awaited()

    async def test_delete_confirmed(self):
        ctx = make_ctx(discord.Permissions(manage_channels=True))
        channel = MagicMock()
        channel.name = "lixo"
        channel.delete = AsyncMock()
        ctx.guild.get_channel.return_value = channel
        ctx.confirm = AsyncMock(return_value=True)
        _, is_error = await execute_tool(ctx, "delete_channel", {"channel_id": "<#123>"})
        self.assertFalse(is_error)
        ctx.guild.get_channel.assert_called_with(123)
        channel.delete.assert_awaited_once()

    async def test_cannot_grant_missing_permission(self):
        ctx = make_ctx(discord.Permissions(manage_roles=True))
        ctx.guild.owner = None
        content, is_error = await execute_tool(
            ctx, "create_role", {"name": "x", "permissions": ["ban_members"]}
        )
        self.assertTrue(is_error)
        self.assertIn("ban_members", content)


class SetupStructureTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_only_and_private(self):
        ctx = make_ctx(discord.Permissions(administrator=True))
        guild = ctx.guild
        equipe = MagicMock()
        equipe.name = "Equipe"
        guild.roles = [equipe]
        category = MagicMock()
        guild.create_category = AsyncMock(return_value=category)
        guild.create_text_channel = AsyncMock(return_value=MagicMock())
        guild.create_voice_channel = AsyncMock(return_value=MagicMock())
        _, is_error = await execute_tool(ctx, "setup_server_structure", {"categories": [
            {"name": "INFO", "read_only": True, "write_roles": ["Equipe"],
             "channels": [{"name": "avisos", "type": "text"}]},
            {"name": "STAFF", "private_to_roles": ["Equipe", "Fantasma"],
             "channels": [{"name": "voz", "type": "voice"}]},
        ]})
        self.assertFalse(is_error)
        info_ow = guild.create_category.await_args_list[0].kwargs["overwrites"]
        self.assertFalse(info_ow[guild.default_role].send_messages)
        self.assertTrue(info_ow[equipe].send_messages)
        staff_ow = guild.create_category.await_args_list[1].kwargs["overwrites"]
        self.assertFalse(staff_ow[guild.default_role].view_channel)
        self.assertTrue(staff_ow[equipe].view_channel)
        # canais sem opções herdam da categoria
        self.assertNotIn("overwrites", guild.create_text_channel.await_args.kwargs)


class EditServerTests(unittest.IsolatedAsyncioTestCase):
    def _ctx(self):
        ctx = make_ctx(discord.Permissions(administrator=True))
        guild = ctx.guild
        guild.rules_channel = None
        guild.public_updates_channel = None
        guild.verification_level = discord.VerificationLevel.none
        guild.explicit_content_filter = discord.ContentFilter.disabled
        guild.features = []
        guild.edit = AsyncMock(return_value=guild)
        channels = {}
        for cid in (1, 2):
            channel = MagicMock(spec=discord.TextChannel)
            channel.id = cid
            channels[cid] = channel
        guild.get_channel = channels.get
        return ctx, channels

    async def test_enable_community_fills_requirements(self):
        ctx, channels = self._ctx()
        _, is_error = await execute_tool(ctx, "edit_server", {
            "community": True, "rules_channel_id": "1", "public_updates_channel_id": "2",
        })
        self.assertFalse(is_error)
        kwargs = ctx.guild.edit.await_args.kwargs
        self.assertTrue(kwargs["community"])
        self.assertIs(kwargs["rules_channel"], channels[1])
        self.assertIs(kwargs["public_updates_channel"], channels[2])
        self.assertEqual(kwargs["verification_level"], discord.VerificationLevel.low)
        self.assertEqual(kwargs["explicit_content_filter"], discord.ContentFilter.all_members)

    async def test_enable_community_needs_channels(self):
        ctx, _ = self._ctx()
        content, is_error = await execute_tool(ctx, "edit_server", {"community": True})
        self.assertTrue(is_error)
        self.assertIn("rules_channel_id", content)
        ctx.guild.edit.assert_not_awaited()


class LocalImageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.image = os.path.join(tmp.name, "yoru.png")
        with open(self.image, "wb") as f:
            f.write(b"\x89PNG fake")

    async def test_refused_in_bot_mode(self):
        ctx = make_ctx(discord.Permissions(administrator=True))
        ctx.guild.create_custom_emoji = AsyncMock()
        content, is_error = await execute_tool(
            ctx, "create_emoji", {"name": "yoru", "image_path": self.image})
        self.assertTrue(is_error)
        self.assertIn("modo Claude Code", content)
        ctx.guild.create_custom_emoji.assert_not_awaited()

    async def test_send_message_with_image(self):
        ctx = make_ctx(discord.Permissions(administrator=True))
        ctx.allow_local_files = True
        channel = MagicMock(spec=discord.TextChannel)
        channel.name = "guia"
        channel.send = AsyncMock(return_value=MagicMock(id=1))
        ctx.guild.get_channel = {5: channel}.get
        _, is_error = await execute_tool(ctx, "send_message", {
            "channel_id": "5", "embed_title": "Yoru", "image_path": self.image,
        })
        self.assertFalse(is_error)
        kwargs = channel.send.await_args.kwargs
        self.assertEqual(kwargs["file"].filename, "yoru.png")
        self.assertEqual(kwargs["embed"].image.url, "attachment://yoru.png")


    async def test_sticker_limit(self):
        ctx = make_ctx(discord.Permissions(administrator=True))
        ctx.allow_local_files = True
        ctx.guild.stickers = [MagicMock()] * 5
        ctx.guild.sticker_limit = 5
        ctx.guild.create_sticker = AsyncMock()
        content, is_error = await execute_tool(ctx, "create_sticker", {
            "name": "Yoru", "emoji": "🌙", "image_path": self.image,
        })
        self.assertTrue(is_error)
        self.assertIn("Limite", content)
        ctx.guild.create_sticker.assert_not_awaited()


class AgentTests(unittest.IsolatedAsyncioTestCase):
    def make_agent(self, *responses):
        agent = ClaudeAgent(Config(discord_token="x"))
        agent._call_claude = AsyncMock(side_effect=list(responses))
        return agent

    async def test_tool_loop(self):
        ctx = make_ctx(discord.Permissions(administrator=True))
        ctx.guild.get_role.return_value = None
        agent = self.make_agent(
            response("tool_use", text("Vou olhar."), tool_use("t1", "edit_role", {"role_id": "5"})),
            response("end_turn", text("Feito!")),
        )
        progress = AsyncMock()
        reply = await agent.run(ctx, "faça algo", progress)
        self.assertEqual(reply, "Feito!")
        progress.assert_awaited_once_with("Vou olhar.")
        session = agent.sessions[50]
        self.assertEqual([m["role"] for m in session], ["user", "assistant", "user", "assistant"])
        result = session[2]["content"][0]
        self.assertEqual(result["tool_use_id"], "t1")
        self.assertTrue(result["is_error"])  # cargo inexistente

    async def test_max_tokens_not_saved(self):
        ctx = make_ctx(discord.Permissions(administrator=True))
        agent = self.make_agent(response("max_tokens", text("parcial"), tool_use("t1", "x", {})))
        reply = await agent.run(ctx, "oi", AsyncMock())
        self.assertIn("cortada", reply)
        self.assertEqual([m["role"] for m in agent.sessions[50]], ["user"])

    async def test_refusal(self):
        ctx = make_ctx(discord.Permissions(administrator=True))
        agent = self.make_agent(response("refusal"))
        reply = await agent.run(ctx, "oi", AsyncMock())
        self.assertIn("não posso", reply)


class CliTests(unittest.IsolatedAsyncioTestCase):
    def make_guild(self):
        guild = MagicMock()
        guild.owner_id = 999
        guild.me.id = 77
        guild.me.guild_permissions = discord.Permissions(manage_channels=True)
        channel = MagicMock()
        channel.name = "lixo"
        channel.delete = AsyncMock()
        guild.get_channel.return_value = channel
        return guild, channel

    async def test_destructive_needs_confirm(self):
        guild, channel = self.make_guild()
        [res] = await _run_calls(guild, [{"tool": "delete_channel", "input": {"channel_id": "1"}}], False)
        self.assertIn("needs_confirmation", res)
        channel.delete.assert_not_awaited()

    async def test_destructive_with_confirm(self):
        guild, channel = self.make_guild()
        [res] = await _run_calls(guild, [{"tool": "delete_channel", "input": {"channel_id": "1"}}], True)
        self.assertTrue(res["ok"])
        channel.delete.assert_awaited_once()
        self.assertEqual(channel.delete.await_args.kwargs["reason"], "Via Claude Code")

    async def test_uses_bot_permissions(self):
        guild, _ = self.make_guild()
        [res] = await _run_calls(guild, [{"tool": "ban_user", "input": {"user_id": "5"}}], True)
        self.assertFalse(res["ok"])
        self.assertIn("ban_members", res["result"])


class ChunkTests(unittest.TestCase):
    def test_chunk(self):
        parts = chunk("a\n" * 3000)
        self.assertTrue(all(len(p) <= 1900 for p in parts))
        self.assertEqual("".join(parts).count("a"), 3000)


if __name__ == "__main__":
    unittest.main()
