from io import BytesIO
import logging
from typing import TYPE_CHECKING

import discord
from discord.utils import MISSING

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger(__name__)

class BroadcastSendModal(discord.ui.Modal, title="Global Announcement"):
    message = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.long,
        placeholder="Write the announcement. Markdown is supported.",
        min_length=1,
        max_length=1942
    )

    # ids -> tuple[channel_id, role_id]
    def __init__(
        self, 
        bot: "BallsDexBot", 
        ids: list[tuple[int, int | None]],
        file: discord.Attachment | None = MISSING,
    ):
        super().__init__()
        self.bot = bot
        self.file = file
        self.ids = ids

    async def on_error(
        self, interaction: discord.Interaction["BallsDexBot"], error: Exception, /  # noqa: W504
    ) -> None:
        log.exception("An error occured while sending global announcement", exc_info=error)
        if interaction.response.is_done():
            await interaction.followup.send(
                "An error occured while sending global announcement.",
            )
        else:
            await interaction.response.send_message(
                "An error occured while sending global announcement.",
            )
    
    async def on_submit(self, interaction: discord.Interaction["BallsDexBot"]):
        await interaction.response.send_message("Sending announcement...", ephemeral=True)
        announcement = self.message.value + "\n-# This message is an announcement"
        
        success_count = 0
        fail_count = 0
        failed_channels = []
        for channel_id, role_id in self.ids:
            channel = None
            try:
                channel = self.bot.get_channel(channel_id)
                if not channel or not isinstance(channel, discord.TextChannel):
                    fail_count += 1
                    failed_channels.append(f"Unknown Channel (ID: {channel_id})")
                    continue

                if role_id:
                    role = channel.guild.get_role(role_id)
                    final_message = f"{role.mention}\n{announcement}" if role else announcement
                else:
                    final_message = announcement

                if self.file:
                    try:
                        data = await self.file.read()
                        file = discord.File(
                            BytesIO(data), 
                            filename=self.file.filename, 
                            spoiler=self.file.is_spoiler(),
                            description=self.file.description
                        )
                        await channel.send(final_message, file=file)
                    except (discord.HTTPException, discord.Forbidden):
                        await channel.send(final_message)
                else:
                    await channel.send(final_message)
                success_count += 1
            except Exception:
                log.exception(f"Error broadcasting to channel {channel_id}")
                fail_count += 1
                if channel and isinstance(channel, discord.TextChannel):
                    failed_channels.append(f"{channel.guild.name} - #{channel.name}")
                else:
                    failed_channels.append(f"Unknown Channel (ID: {channel_id})")
        
        failed_text = ", ".join(failed_channels)
        if len(failed_text) > 1000:
            failed_text = failed_text[:1000] + "..."
        
        await interaction.edit_original_response(
            content=(
                "Broadcast completed.\n"
                f"Successfully sent: {success_count} channels\n"
                f"Failed: {fail_count} channels\n"
                f"{failed_text}"
            )
        )
        return