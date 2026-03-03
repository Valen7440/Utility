from typing import TYPE_CHECKING

from tortoise import models, fields

from ballsdex.core.models import DiscordSnowflakeValidator

if TYPE_CHECKING:
    from ballsdex.core.models import GuildConfig

class Broadcast(models.Model):
    config: fields.OneToOneRelation["GuildConfig"] = fields.OneToOneField(
        "models.GuildConfig",
        on_delete=fields.CASCADE,
        related_name="broadcast"
    )
    ping_role_id = fields.BigIntField(
        null=True,
        description="Optional role ID to mention in broadcast messages.",
        validators=[DiscordSnowflakeValidator()]
    )
