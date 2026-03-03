from django.db import models

from bd_models.models import GuildConfig

class Broadcast(models.Model):
    config = models.OneToOneField(
        GuildConfig, 
        on_delete=models.CASCADE,
        related_name="broadcast"
    )
    ping_role_id = models.BigIntegerField(
        null=True, blank=True, help_text="Optional role ID to mention in broadcast messages."
    )

    def __str__(self) -> str:
        return f"Broadcast Settings for {self.config.guild_id}"

    class Meta:
        managed = True
        db_table = "broadcast"
