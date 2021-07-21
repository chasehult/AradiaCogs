import urllib.parse
from io import BytesIO

import aiohttp
import discord
from redbot.core import commands


class Papago(commands.Cog):
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.session = aiohttp.ClientSession()

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

    @commands.command()
    async def ptranslate(self, ctx, source, target, *, text):
        try:
            translation = await self.translate(source, target, text)
        except NoAPIKey:
            await ctx.send(f"Invalid API keys.  You can set them with "
                           f"`{ctx.prefix}set api papago client_id <CLIENT_ID> client_secret <CLIENT_SECRET>`")
            return
        await ctx.send(embed=discord.Embed(description=f'**Original**\n`{text}`\n\n**Translation**\n`{translation}`'))

    async def translate(self, source: str, target: str, text: str) -> str:
        url = 'https://openapi.naver.com/v1/papago/n2mt'
        keys = await self.bot.get_shared_api_tokens('papago')
        headers = {
            "X-Naver-Client-Id": keys.get('client_id', 'None'),
            "X-Naver-Client-Secret": keys.get('client_secret', 'None'),
        }
        data = {'source': source, 'target': target, 'text': text}

        response = await self.session.post(url, headers=headers, data=data)

        content = await response.json()
        if response.status == 401:
            raise ValueError()
        if response.status != 200:
            raise IOError(f'{response.status}: request aborted\n\n{content}')
        return content['message']['result']['translatedText']
