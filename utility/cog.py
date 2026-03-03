from datetime import datetime, timezone
import logging
from typing import TYPE_CHECKING, Optional, cast

import discord
from discord import app_commands
from discord.ext import commands
from discord.utils import format_dt

from ballsdex.core.models import BallInstance, GuildConfig, Player, balls
from ballsdex.core.utility_models import Broadcast
from ballsdex.core.utils.paginator import FieldPageSource, Pages, TextPageSource
from ballsdex.settings import settings

from .components import BroadcastSendModal
from .types import PrisonData

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot                                                                                                                                                                                                   

log = logging.getLogger(__name__)

GUILD_JOIN_TEXT = """
Hey, **{server_name}!**

👋 Thanks for adding {bot_mention} to **{server_name}**!

Let’s get everything set up so cards can start spawning in your server.

**🔧 Quick Setup**

Run the following command in your server:
```/config channel```
Choose the channel where you’d like cards to spawn, and you’re good to go.
Once that’s done, members can start collecting, trading, and building their NinjagoDex card collections right away.

**🎉 Want more?**

For support, exclusive giveaways, card rains, sneak peeks, and community events:
👉 Join the NinjagoDex server: Click [**HERE**](https://discord.gg/KWye2jxwxW)

Have fun collecting, and may your Ninjago catches be legendary!! 🥷✨
"""

class UtilityCog(commands.Cog):
    """
    An utility cog that add some helper commands.
    """

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot
        self.prison_data: dict[int, dict[int, PrisonData]] = {}
    
    broadcast = app_commands.Group(
        name="broadcast",
        description="Send a global announcement to spawn channels.",
        guild_only=True,
        default_permissions=discord.Permissions(administrator=True)
    )
    prision = app_commands.Group(
        name="prision",
        description="Bot prision commands",
        guild_only=True,
        default_permissions=discord.Permissions(administrator=True)
    )

    @broadcast.command()
    @app_commands.checks.has_permissions(administrator=True)
    async def set_ping(
        self, interaction: discord.Interaction["BallsDexBot"], role: discord.Role | None = None
    ):
        """
        Set/unset role to mention in broadcast messages.

        Parameters
        ----------
        role: discord.Role | None
            The role to set for broadcast pings.
            If None, the current ping role will be removed.
        """
        await interaction.response.defer(thinking=True, ephemeral=True)
        assert interaction.guild
        if interaction.guild.unavailable:
            await interaction.followup.send(
                "The server is unavailable to the bot and will not work properly. "
                "Kicking and readding the bot may fix this.",
                ephemeral=True,
            )
            return
        config = await GuildConfig.get_or_none(
            guild_id=interaction.guild.id,
            enabled=True,
            spawn_channel__isnull=False,
        )
        if not config:
            await interaction.followup.send(
                "This server does not have the spawn channel configured. "
                "Set it up if you want to receive global announcements.",
                ephemeral=True
            )
            return

        id = role.id if role else None
        broadcast, created = await Broadcast.get_or_create(config=config, defaults={"ping_role_id": id})
        if not created:
            broadcast.ping_role_id = id
            await broadcast.save(update_fields=("ping_role_id",))

        await interaction.followup.send(
            f"You've {'enabled' if role else 'disabled'} the role mention "
            "in broadcast mentions",
            ephemeral=True
        )
        return

    @broadcast.command()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.checks.has_any_role(*settings.root_role_ids)
    async def send(self, interaction: discord.Interaction["BallsDexBot"], file: discord.Attachment | None = None):
        """
        Sends a global announcement.

        Parameters
        ----------
        file: discord.Attachment | None
            An optional image to attach.
        """
        configs = await GuildConfig.filter(
            enabled=True,
            spawn_channel__isnull=False
        ).prefetch_related("broadcast")
        assert interaction.guild
        if interaction.guild.id not in settings.admin_guild_ids:
            await interaction.response.send_message("This server isn't an admin server.")
            return

        ids = []
        for x in configs:
            ping_role_id = None
            if hasattr(x, "broadcast") and x.broadcast: # type: ignore
                ping_role_id = x.broadcast.ping_role_id # type: ignore

            ids.append((x.spawn_channel, ping_role_id))
        await interaction.response.send_modal(BroadcastSendModal(self.bot, ids, file))

    @app_commands.command()
    @app_commands.guilds(*settings.admin_guild_ids)
    @app_commands.checks.has_any_role(*settings.root_role_ids, *settings.admin_role_ids)
    async def servers(self, interaction: discord.Interaction["BallsDexBot"]):
        """
        List all servers BallsDex is in
        """
        guilds = sorted(
            self.bot.guilds,
            key=lambda x: x.member_count or 0,
            reverse=True
        )
        text = ""

        for i, guild in enumerate(guilds, start=1):
            text += f"{i}. {guild.name} ({guild.id}) - {guild.member_count} members\n"

        source = TextPageSource(text, prefix="```md\n", suffix="```")
        pages = Pages(source=source, interaction=interaction, compact=True)
        pages.remove_item(pages.stop_pages)
        await pages.start(ephemeral=True)

    @app_commands.command()
    async def rarity(self, interaction: discord.Interaction["BallsDexBot"], owned: bool | None = None):
        """
        Genereate a list of rarities of cards.

        Parameters
        ----------
        owned: bool | None
            Filters the list to only include the countryballs you own.
        """
        player, _ = await Player.get_or_create(discord_id=interaction.user.id)
        ball_ids = await BallInstance.filter(player=player).values_list("ball_id", flat=True)
        if owned is not None:
            if owned:
                countryballs = [
                    b
                    for b in balls.values()
                    if b.pk in ball_ids
                ]
            else:
                countryballs = [
                    b
                    for b in balls.values()
                    if b.pk not in ball_ids
                ]
        else:
            countryballs = [b for b in balls.values()]
        
        if not countryballs:
            if owned is not None:
                if owned:
                    text = f"You don't any {settings.plural_collectible_name}."
                else:
                    text = "You've already completed the bot. Congratulations!"
            else:
                text = (
                    f"There are no {settings.plural_collectible_name}"
                    f"registered on this bot yet."
                )
            await interaction.response.send_message(text, ephemeral=True)
            return
        
        entries: list[tuple[str, str]] = []
        for countryball in countryballs:
            emoji = self.bot.get_emoji(countryball.emoji_id)
            if owned is not None:
                title = f"{countryball.country} {'✅' if owned else '❌'}"
            else:
                title = f"{countryball.country} {'✅' if countryball.pk in ball_ids else '❌'}"

            if emoji:
                title = f"{emoji} {title}"
            
            rarity_text = f"{countryball.rarity:.1f}%"
            entries.append((title, f"Rarity: {rarity_text}"))
        source = FieldPageSource(entries, per_page=5)
        source.embed.title = f"{settings.bot_name} {settings.plural_collectible_name.title()} rarity list"
        
        pages = Pages(source, interaction=interaction, compact=True)
        await pages.start()

    @prision.command()
    async def set(
        self, 
        interaction: discord.Interaction["BallsDexBot"], 
        user: discord.Member,
        *,
        reason: Optional[str] = None
    ):
        """
        Sends a user to prison mode. Their messages will be automatically deleted.

        Parameters
        ----------
        user: discord.Member
            The user to send to prision.
        reason: Optional[str]
            The reason for sending the user to prison.
        """
        assert interaction.guild
        if interaction.guild.unavailable:
            await interaction.response.send_message(
                "The server is unavailable to the bot and will not work properly. "
                "Kicking and readding the bot may fix this.",
                ephemeral=True,
            )
            return
        assert isinstance(interaction.user, discord.Member)
        if user.bot:
            await interaction.response.send_message("You cannot send bots to prison.", ephemeral=True)
            return
        if user.id == interaction.user.id:
            await interaction.response.send_message("You cannot prison yourself.", ephemeral=True)
            return
        if user.id == interaction.guild.owner_id:
            await interaction.response.send_message("You cannot prison the server owner.", ephemeral=True)
            return
        if user.top_role.position >= interaction.user.top_role.position:
            await interaction.response.send_message(
                "You cannot prison someone with an equal or higher role.", ephemeral=True
            )
            return
        guild_prison_data = self.prison_data.setdefault(interaction.guild.id, {})
        if user.id in guild_prison_data:
            await interaction.response.send_message(f"{user.mention} is already added to prison.")
            return
        guild_prison_data[user.id] = { # type: ignore
            "id": len(guild_prison_data) + 1,
            "guild": interaction.guild,
            "moderator": interaction.user,
            "user": user,
            "reason": reason,
            "since": datetime.now(timezone.utc)
        }
        text = (
            f"{user.mention} has been sent to the cursed realm!\n"
            f"Reason: {reason}"
            if reason
            else f"{user.mention} has been sent to the cursed realm!"
        )
    
        await interaction.response.send_message(text)
    
    @prision.command()
    async def unset(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        user: discord.Member
    ):
        """
        Removes a user from prison mode.

        Parameters
        ----------
        user: discord.Member
            The user to remove from prision.
        """
        assert interaction.guild
        if interaction.guild.unavailable:
            await interaction.response.send_message(
                "The server is unavailable to the bot and will not work properly. "
                "Kicking and readding the bot may fix this.",
                ephemeral=True,
            )
            return
        guild_prison_data = self.prison_data.get(interaction.guild.id, {})
        if user.id not in guild_prison_data:
            await interaction.response.send_message(f"{user.mention} isn't in prision mode.")
            return
        guild_prison_data.pop(user.id)
        await interaction.response.send_message(f"{user.mention} removed from prision mode.")
        return
    
    @prision.command()
    async def list(self, interaction: discord.Interaction["BallsDexBot"]):
        """
        List of users in prision mode.
        """
        assert interaction.guild
        if interaction.guild.unavailable:
            await interaction.response.send_message(
                "The server is unavailable to the bot and will not work properly. "
                "Kicking and readding the bot may fix this.",
                ephemeral=True,
            )
            return
        guild_prison_data = self.prison_data.get(interaction.guild.id, {})
        if not guild_prison_data:
            await interaction.response.send_message("There isn't any user in prision mode.", ephemeral=True)
            return
    
        entries: list[tuple[str, str]] = []
        for data in guild_prison_data.values():
            text = (
                f"User: {data["user"].display_name}\n"
                f"Moderator: {data["moderator"].display_name}\n"
                f"Since: {format_dt(data["since"])} ({format_dt(data["since"], "R")})\n"
            )
            if data["reason"]:
                text += f"Reason: {data["reason"]}\n"
            entries.append((f"Case #{data["id"]}", text))
        source = FieldPageSource(entries, per_page=5)
        source.embed.title = f"{interaction.guild.name}'s Prision"

        pages = Pages(source, interaction=interaction)
        await pages.start()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        assert message.guild
        guild_prison_data = self.prison_data.get(message.guild.id, {})
        if message.author.id in guild_prison_data:
            log.debug(f"{message.author.name}'s message was successfully deleted.")
            await message.delete()
            return

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        if settings.log_channel:
            log_channel = self.bot.get_channel(settings.log_channel)
            if not log_channel:
                log.warning(f"Channel {settings.log_channel} not found")
                return
            if not isinstance(log_channel, discord.TextChannel):
                log.warning(f"Channel {log_channel.name} is not a text channel")  # type: ignore
                return
            
            assert self.bot.user
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    try:
                        text = GUILD_JOIN_TEXT.format(
                            server_name=guild.name,
                            bot_mention=self.bot.user.mention
                        )
                        await channel.send(text)
                        break
                    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                        continue

            owner_id = cast(int, guild.owner_id)
            try:
                owner = await guild.fetch_member(owner_id)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                owner = None
            
            members = guild.members

            embed = discord.Embed(title="✅ Joined a new server", color=discord.Color.green())
            embed.description = f"Now {settings.bot_name} is in **{len(self.bot.guilds)}** servers."
            embed.add_field(name="ID", value=guild.id)
            embed.add_field(name="Name", value=guild.name)
            if owner:
                embed.add_field(name="Owner", value=f"{owner.display_name} ({owner.id})")
            else:
                embed.add_field(name="Owner ID", value=owner_id)
            embed.add_field(
                name="Created At", 
                value=f"{format_dt(guild.created_at)} ({format_dt(guild.created_at, "R")})",
            )
            if self.bot.intents.members:
                humans = list(filter(lambda x: not x.bot, members))
                bots = list(filter(lambda x: x.bot, members))
                embed.add_field(
                    name="Members",
                    value=(
                        f"Total: **{guild.member_count or "Unknown"}**\n"
                        f"Humans: **{len(humans)}**\n"
                        f"Bots: **{len(bots)}**\n"
                    ),
                )
            else:
                embed.add_field(
                    name="Total Members",
                    value=guild.member_count,
                )
            embed.add_field(
                name="Channels",
                value=(
                    f"Total: **{len(guild.channels)}**\n"
                    f"Text: **{len(guild.text_channels)}** • Voice: **{len(guild.voice_channels)}** "
                    f"• Stage: **{len(guild.stage_channels)}**\n"
                    f"Categories: **{len(guild.categories)}** • Threads: **{len(guild.threads)}**"
                ),
            )
            embed.add_field(
                name="Boosts",
                value=f"Tier {guild.premium_tier} • {guild.premium_subscription_count} boosts",
                inline=True
            )
            embed.add_field(    
                name="Security",
                value=(
                    f"Verification: {guild.verification_level.name.title()}\n"
                    f"NSFW filter: {guild.nsfw_level.name.title()}\n"
                ),
                inline=True
            )
            embed.add_field(
                name="Shard ID",
                value=f"{guild.shard_id}",
                inline=True
            )
            embed.add_field(
                name="Features",
                value=", ".join(guild.features) if guild.features else None
            )

            await log_channel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        if settings.log_channel:
            log_channel = self.bot.get_channel(settings.log_channel)
            if not log_channel:
                log.warning(f"Channel {settings.log_channel} not found")
                return
            if not isinstance(log_channel, discord.TextChannel):
                log.warning(f"Channel {log_channel.name} is not a text channel")  # type: ignore
                return

            owner_id = cast(int, guild.owner_id)
            try:
                owner = await self.bot.fetch_user(owner_id)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                owner = None
            
            members = guild.members

            embed = discord.Embed(title="❌ Removed from a server", color=discord.Color.red())
            embed.description = f"Now {settings.bot_name} is in **{len(self.bot.guilds)}** servers."
            embed.add_field(name="ID", value=guild.id)
            embed.add_field(name="Name", value=guild.name)
            if owner:
                embed.add_field(name="Owner", value=f"{owner.display_name} ({owner.id})")
            else:
                embed.add_field(name="Owner ID", value=owner_id)
            embed.add_field(
                name="Created At", 
                value=f"{format_dt(guild.created_at)} ({format_dt(guild.created_at, "R")})",
            )
            if self.bot.intents.members:
                humans = list(filter(lambda x: not x.bot, members))
                bots = list(filter(lambda x: x.bot, members))
                embed.add_field(
                    name="Members",
                    value=(
                        f"Total: **{guild.member_count or "Unknown"}**\n"
                        f"Humans: **{len(humans)}**\n"
                        f"Bots: **{len(bots)}**\n"
                    ),
                )
            else:
                embed.add_field(
                    name="Total Members",
                    value=guild.member_count,
                )
            embed.add_field(
                name="Channels",
                value=(
                    f"Total: **{len(guild.channels)}**\n"
                    f"Text: **{len(guild.text_channels)}** • Voice: **{len(guild.voice_channels)}** "
                    f"• Stage: **{len(guild.stage_channels)}**\n"
                    f"Categories: **{len(guild.categories)}** • Threads: **{len(guild.threads)}**"
                ),
            )
            embed.add_field(
                name="Boosts",
                value=f"Tier {guild.premium_tier} • {guild.premium_subscription_count} boosts",
                inline=True
            )
            embed.add_field(    
                name="Security",
                value=(
                    f"Verification: {guild.verification_level.name.title()}\n"
                    f"NSFW filter: {guild.nsfw_level.name.title()}\n"
                ),
                inline=True
            )
            embed.add_field(
                name="Shard ID",
                value=f"{guild.shard_id}",
                inline=True
            )
            embed.add_field(
                name="Features",
                value=", ".join(guild.features) if guild.features else None
            )

            await log_channel.send(embed=embed)
