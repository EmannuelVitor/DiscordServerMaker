"""Botões de confirmação para ações destrutivas."""

from __future__ import annotations

import discord


class ConfirmView(discord.ui.View):
    """Dois botões (Confirmar / Cancelar) que só o solicitante pode apertar."""

    def __init__(self, requester_id: int, timeout: float):
        super().__init__(timeout=timeout)
        self.requester_id = requester_id
        self.value: bool | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "Só quem fez o pedido pode confirmar esta ação.", ephemeral=True
            )
            return False
        return True

    def _disable_all(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.value = True
        self._disable_all()
        await interaction.response.edit_message(
            content=f"{interaction.message.content}\n✅ Confirmado.", view=self
        )
        self.stop()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.value = False
        self._disable_all()
        await interaction.response.edit_message(
            content=f"{interaction.message.content}\n❌ Cancelado.", view=self
        )
        self.stop()
