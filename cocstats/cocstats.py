import logging

import discord
from pyppeteer import launch
from io import BytesIO

from redbot.core import commands

logger = logging.getLogger('red.aradiacogs.cocstats')


class CoCStats(commands.Cog):
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        data = "No data is stored for user with ID {}.\n".format(user_id)
        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data.

        No personal data is stored in this cog.
        """
        return

    @commands.command()
    async def clash(self, ctx):
        """Get the current report from clashofclansforecaster.com"""
        async with ctx.typing():
            browser = await launch()
            page = await browser.newPage()
            await page.goto('http://clashofclansforecaster.com')
            a = await page.screenshot(clip={'x': 170,
                                            'y': 8,
                                            'height': 898,
                                            'width': 1152})
        await ctx.send(file=discord.File(BytesIO(a), filename="screenshot.png"))
        await browser.close()
