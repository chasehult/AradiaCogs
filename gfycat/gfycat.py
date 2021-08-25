import logging
from io import BytesIO
from typing import Optional

import aiohttp
from discord.ext.commands import BucketType
from redbot.core import commands
from redbot.core.bot import Red

from gfycat.gfy_api import GfycatAPI

logger = logging.getLogger('red.aradiacogs.gfycat')


class Gfycat(commands.Cog):
    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.session = aiohttp.ClientSession()

        self.api = GfycatAPI(bot, self.session)

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
        self.bot.loop.create_task(self.session.close())

    @commands.command(aliases=['gfy'])
    @commands.cooldown(1, 5, BucketType.user)
    async def gfycat(self, ctx, number: Optional[int], *, search_str):
        """Sends gifs from gfycat.com."""
        number = number or 1
        if number < 1 or 10 < number:
            return await ctx.send("You must request between 1 and 5 gifs")
        urls = await self.api.get_gyfs(number, search_str)
        if not urls:
            return await ctx.send("No gfys found.")
        for url in urls:
            await ctx.send(url)
