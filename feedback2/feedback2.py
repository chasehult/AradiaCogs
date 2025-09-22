import logging
from io import BytesIO

import discord
from redbot.core import commands, app_commands, Config

logger = logging.getLogger('red.aradia-cogs.feedback2')


class Feedback2(commands.Cog):
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.config = Config.get_conf(self, identifier=hash("aradia"))
        self.config.register_guild(log_channel=None)

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        data = "No data is stored for user with ID {}.\n".format(user_id)
        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data.

        No personal data is stored in this cog.
        """
        return

    @commands.group()
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def feedback2(self, ctx):
        """Admin suite for feedback2."""

    @feedback2.command()
    async def enable(self, ctx, log_channel: discord.TextChannel):
        """Enable feedback2 in this guild"""
        await self.config.guild(ctx.guild).log_channel.set(log_channel.id)
        await ctx.tick()

    @feedback2.command()
    async def disable(self, ctx):
        """Disable feedback2 in this guild"""
        await self.config.guild(ctx.guild).log_channel.set(None)
        await ctx.tick()

    @app_commands.command()
    @app_commands.guild_only()
    async def report(self, interaction: discord.Interaction, message: str):
        """Report a message to moderation."""
        if (cid := await self.config.guild(interaction.guild).log_channel()) is None:
            return await interaction.response.send_message("Report is not enabled in this server.", ephemeral=True)
        if (channel := await self.bot.fetch_channel(cid)) is None:
            return await interaction.response.send_message("Report channel invalid. Please reach out to moderation.", ephemeral=True)
        await channel.send(f"From {interaction.user.mention} ({interaction.user.id}):\n{message}")
        await interaction.response.send_message("Your report has been sent to moderation.", ephemeral=True)

