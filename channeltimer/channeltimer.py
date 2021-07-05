import asyncio
import logging
from datetime import timedelta, datetime

import discord
from io import BytesIO

from redbot.core import commands, Config
from redbot.core.commands import TimedeltaConverter

logger = logging.getLogger('red.aradiacogs.channeltimer')

Timedelta = TimedeltaConverter(minimum=timedelta(minutes=10), default_unit="days")


class ChannelTimer(commands.Cog):
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.config = Config.get_conf(self, identifier=744773771732)
        self.config.register_channel(name=None, time=None)

        self._loop = bot.loop.create_task(self.run_loop())

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        data = "No data is stored for user with ID {}.\n".format(user_id)
        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data.

        No personal data is stored in this cog.
        """
        return

    def cog_unload(self):
        self._loop.cancel()

    async def run_loop(self):
        while True:
            try:
                await self.update_channels()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in loop")
            await asyncio.sleep(10 * 60)

    @commands.group()
    async def channeltimer(self, ctx):
        """Subcommand for channeltimer related commands."""

    @channeltimer.command(name='add', aliases=['set'])
    async def ct_add(self, ctx, channel: discord.VoiceChannel, *, time: Timedelta):
        """Add a timer to a voice channel"""
        if await self.config.channel(channel).time() is not None:
            await ctx.send("This channel is already set up with a timer.  Remove it first.")
            return
        hours, mins = divmod(time.seconds // 60, 60)
        await self.config.channel(channel).name.set(channel.name)
        await self.config.channel(channel).time.set((datetime.now() + time).timestamp())
        self.bot.loop.create_task(channel.edit(name=f"{channel.name} {time.days}d {hours}h {mins}m"))
        await ctx.tick()
        
    @channeltimer.command(name='remove', aliases=['rm', 'del', 'delete'])
    async def ct_rm(self, ctx, channel: discord.VoiceChannel):
        """Remove a timer from a voice channel"""
        if await self.config.channel(channel).time() is None:
            await ctx.send("This channel isn't set up with a timer.")
            return
        name = await self.config.channel(channel).name()
        await self.config.channel(channel).name.set(None)
        await self.config.channel(channel).time.set(None)
        self.bot.loop.create_task(channel.edit(name=name))
        await ctx.tick()

    async def update_channels(self):
        for cid, data in (await self.config.all_channels()).items():
            if (channel := self.bot.get_channel(cid)) is None:
                continue
            if data['time'] is None:
                continue

            now = datetime.now()
            then = datetime.fromtimestamp(data['time'])
            td = max(then-now, timedelta())

            hours, mins = divmod(td.seconds // 60, 60)

            cname = f"{data['name']} {td.days}d {hours}h {mins}m"

            await channel.edit(name=cname)
