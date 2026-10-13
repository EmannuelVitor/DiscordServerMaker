"""Modo Claude Code: executa as ferramentas do bot pela linha de comando.

Aqui quem decide o que fazer é o Claude Code (usando a assinatura do Claude),
então não é preciso ANTHROPIC_API_KEY — só o DISCORD_TOKEN do bot.

    python -m bot.cli guilds
    python -m bot.cli tools
    python -m bot.cli run get_server_info
    python -m bot.cli run create_channel '{"name": "geral", "type": "text"}'
    python -m bot.cli batch '[{"tool": "create_role", "input": {"name": "VIP"}}, ...]'
    python -m bot.cli run delete_channel '{"channel_id": "123"}' --confirm

Ações destrutivas (excluir, expulsar, banir, apagar mensagens) só são
executadas com --confirm; sem ele, o comando apenas mostra o que seria feito.
As ações respeitam as permissões e a hierarquia de cargos do próprio bot.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

import discord
from dotenv import load_dotenv

from .tools import TOOLS, ToolContext, execute_tool, tool_definitions


def _print(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def _parse_json(raw: str | None, default: Any) -> Any:
    if raw is None or raw.strip() == "":
        return default
    if raw.strip() == "-":
        raw = sys.stdin.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"JSON inválido: {exc}") from None


def _maybe_json(text: str) -> Any:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


def _pick_guild(client: discord.Client, guild_id: str | None) -> discord.Guild:
    if guild_id:
        guild = client.get_guild(int(guild_id))
        if guild is None:
            raise SystemExit(f"O bot não está no servidor {guild_id}. Use o comando 'guilds'.")
        return guild
    if len(client.guilds) == 1:
        return client.guilds[0]
    if not client.guilds:
        raise SystemExit("O bot não está em nenhum servidor. Convide-o primeiro.")
    names = ", ".join(f"{g.name} ({g.id})" for g in client.guilds)
    raise SystemExit(f"O bot está em vários servidores; informe --guild. Servidores: {names}")


async def _run_calls(guild: discord.Guild, calls: list[dict], confirm: bool) -> list[dict]:
    pending: list[str] = []

    async def confirm_fn(description: str) -> bool:
        if confirm:
            return True
        pending.append(description)
        return False

    ctx = ToolContext(
        guild=guild,
        requester=guild.me,  # age com as permissões e a hierarquia do bot
        channel=None,  # type: ignore[arg-type]
        send=None,  # type: ignore[arg-type]  # não usado: confirm_fn substitui os botões
        require_confirmation=True,
        confirm_timeout=0,
        confirm_fn=confirm_fn,
        audit_label="Via Claude Code",
    )

    results = []
    for call in calls:
        name = call.get("tool")
        tool_input = call.get("input") or {}
        pending.clear()
        content, is_error = await execute_tool(ctx, name, tool_input)
        entry: dict[str, Any] = {"tool": name, "ok": not is_error, "result": _maybe_json(content)}
        if pending:
            entry["needs_confirmation"] = pending[0]
            entry["result"] = "NÃO executado: rode de novo com --confirm depois que o usuário aprovar."
        results.append(entry)
    return results


class _IntentsDenied(Exception):
    pass


def _is_intents_error(exc: BaseException | None) -> bool:
    return isinstance(exc, discord.PrivilegedIntentsRequired) or (
        isinstance(exc, discord.ConnectionClosed) and exc.code == 4014
    )


async def _with_client(token: str, work) -> Any:
    try:
        return await _connect_and_run(token, work, privileged=True)
    except _IntentsDenied:
        print(
            "AVISO: 'Server Members Intent' e/ou 'Message Content Intent' estão desativados "
            "em Developer Portal > Bot. Continuando sem eles: list_members fica limitado e "
            "read_recent_messages não mostra o texto das mensagens.",
            file=sys.stderr,
        )
        return await _connect_and_run(token, work, privileged=False)


async def _connect_and_run(token: str, work, privileged: bool) -> Any:
    intents = discord.Intents.default()
    intents.members = privileged
    intents.message_content = privileged
    client = discord.Client(intents=intents)
    ready = asyncio.Event()

    @client.event
    async def on_ready() -> None:
        ready.set()

    async with client:
        try:
            await client.login(token)
        except discord.LoginFailure:
            raise SystemExit("DISCORD_TOKEN inválido. Gere um novo em Developer Portal > Bot.") from None
        connect = asyncio.create_task(client.connect(reconnect=False))
        waiter = asyncio.create_task(ready.wait())
        done, _ = await asyncio.wait({connect, waiter}, return_when=asyncio.FIRST_COMPLETED)
        if connect in done:
            waiter.cancel()
            exc = connect.exception()
            if privileged and _is_intents_error(exc):
                raise _IntentsDenied
            raise SystemExit(f"Falha ao conectar no Discord: {exc}")
        try:
            return await work(client)
        finally:
            await client.close()
            try:
                await connect
            except Exception:
                pass


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="python -m bot.cli", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--guild", default=os.getenv("DISCORD_GUILD_ID") or None,
                        help="ID do servidor (padrão: DISCORD_GUILD_ID ou o único servidor do bot)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("guilds", help="lista os servidores onde o bot está")
    tools_cmd = sub.add_parser("tools", help="lista as ferramentas e seus parâmetros")
    tools_cmd.add_argument("name", nargs="?", help="mostrar só esta ferramenta")

    run = sub.add_parser("run", help="executa uma ferramenta")
    run.add_argument("tool")
    run.add_argument("input", nargs="?", help="JSON com os parâmetros ('-' lê do stdin)")
    run.add_argument("--confirm", action="store_true", help="autoriza ações destrutivas")

    batch = sub.add_parser("batch", help="executa várias ferramentas em sequência")
    batch.add_argument("calls", nargs="?", default="-",
                       help='JSON: [{"tool": "...", "input": {...}}, ...] (padrão: stdin)')
    batch.add_argument("--confirm", action="store_true", help="autoriza ações destrutivas")

    args = parser.parse_args(argv)

    if args.command == "tools":
        defs = tool_definitions()
        if args.name:
            defs = [d for d in defs if d["name"] == args.name]
            if not defs:
                raise SystemExit(f"Ferramenta desconhecida: {args.name}")
        _print(defs)
        return

    if args.command == "run":
        if args.tool not in TOOLS:
            raise SystemExit(f"Ferramenta desconhecida: {args.tool}. Use 'tools' para ver a lista.")
        calls = [{"tool": args.tool, "input": _parse_json(args.input, {})}]
    elif args.command == "batch":
        calls = _parse_json(args.calls, [])
        if not isinstance(calls, list) or not all(isinstance(c, dict) for c in calls):
            raise SystemExit('batch espera uma lista: [{"tool": "...", "input": {...}}]')

    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "DISCORD_TOKEN não definido. No Claude Code na nuvem, adicione-o nas variáveis "
            "de ambiente do ambiente; no seu PC, coloque-o no arquivo .env."
        )

    async def work(client: discord.Client) -> Any:
        if args.command == "guilds":
            return [
                {"id": str(g.id), "name": g.name, "members": g.member_count}
                for g in client.guilds
            ]
        guild = _pick_guild(client, args.guild)
        return {
            "guild": {"id": str(guild.id), "name": guild.name},
            "results": await _run_calls(guild, calls, args.confirm),
        }

    _print(asyncio.run(_with_client(token, work)))


if __name__ == "__main__":
    main()
