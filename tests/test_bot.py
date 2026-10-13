"""Testes offline (sem Discord nem API real): `python -m unittest`."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

os.environ.setdefault("ANTHROPIC_API_KEY", "test")

from bot.__main__ import chunk  # noqa: E402
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


class ChunkTests(unittest.TestCase):
    def test_chunk(self):
        parts = chunk("a\n" * 3000)
        self.assertTrue(all(len(p) <= 1900 for p in parts))
        self.assertEqual("".join(parts).count("a"), 3000)


if __name__ == "__main__":
    unittest.main()
