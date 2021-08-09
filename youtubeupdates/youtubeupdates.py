import asyncio
import logging
import re
from datetime import datetime, timezone
from io import BytesIO

import aiohttp
import discord
from dateutil.parser import isoparse
from discord import Embed
from discordmenu.embed.components import EmbedBodyImage, EmbedField, EmbedFooter, EmbedMain, EmbedThumbnail
from discordmenu.embed.text import Text
from discordmenu.embed.view import EmbedView
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box, pagify

logger = logging.getLogger('red.aradiacogs.youtubeupdates')

CHANNEL_URL_REGEX = re.compile(r"^(?:https?://)?(?:www\.)?youtube\.com/(?:channel|user)/([\w-]+)")


class YouTubeUpdates(commands.Cog):
    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.config = Config.get_conf(self, identifier=70777837904735)
        self.config.register_global(last_check=0, ytchannels={}, wait_minutes=5)
        self.config.register_guild(channel_count=0)

        self.session = aiohttp.ClientSession()

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
        self.bot.loop.create_task(self.session.close())

    async def run_loop(self):
        await self.bot.wait_until_red_ready()
        while True:
            try:
                await self.do_loop()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in loop")
            await asyncio.sleep(60 * await self.config.wait_minuts())

    async def do_loop(self):
        endpoint = "https://youtube.googleapis.com/youtube/v3/{}"
        keys = await self.bot.get_shared_api_tokens("youtube")

        last_check = datetime.fromtimestamp(await self.config.last_check() - 60 * 60, timezone.utc)
        headers = {'Accept': 'application/json'}

        async with self.config.ytchannels() as full_channels:
            for ycid, cdata in full_channels.items():
                params = {'part': 'snippet', 'channel_id': ycid, 'maxResults': 15, 'key': keys['apikey'],
                          'order': 'date'}
                async with self.session.get(endpoint.format('search'), params=params, headers=headers) as resp:
                    data = await resp.json()
                    if 'error' in data:
                        print(data['error']['message'])
                        return
                    all_videos = data['items'][::-1]
                videos = [v for v in all_videos
                          if isoparse(v['snippet']['publishedAt']) > last_check
                          and v['id']['videoId'] not in cdata.get('seen_ids', [])]
                if not videos:
                    continue
                full_channels[ycid]['seen_ids'] = [v['id']['videoId'] for v in all_videos]

                params = {'part': 'snippet,statistics', 'id': ycid, 'key': keys['apikey']}
                async with self.session.get(endpoint.format('channels'), params=params, headers=headers) as resp:
                    channel_data = (await resp.json())['items'][0]

                for c_id in cdata['channels']:
                    if not (channel := self.bot.get_channel(c_id)):
                        continue
                    for video in videos:
                        try:
                            await channel.send(embed=self.make_embed(video, channel_data))
                        except discord.Forbidden:
                            pass
        await self.config.last_check.set(datetime.now().timestamp())

    @commands.group(aliases=['youtubeupdates', 'ytupdate', 'ytupdates'])
    async def youtubeupdate(self, ctx):
        """Subcommand for YouTubeUpdate related commands."""

    @youtubeupdate.group(name='channel', aliases=['channels'])
    async def ytu_channel(self, ctx):
        """Add or remove channels"""

    @ytu_channel.command(name="add")
    @commands.has_guild_permissions(manage_messages=True)
    async def ytuc_add(self, ctx, url):
        """Add a channel"""
        if await self.config.guild(ctx.guild).channel_count() >= 5 \
                and ctx.author.id not in self.bot.owner_ids:
            await ctx.send("You can't have more than five channels"
                           " set up with this guild.")
            return
        if not await self.ensure_api():
            await ctx.send(f"You need to set up your API keys with"
                           f" `{ctx.prefix}set api youtube apikey <API KEY>`")
        if not (match := CHANNEL_URL_REGEX.match(url)):
            await ctx.send("URL is not a valid youtube channel.")
            return
        ytc_id = match.group(1)
        async with self.config.ytchannels() as ytchannels:
            if ytc_id not in ytchannels:
                ytchannels[ytc_id] = {'channels': []}
            ytchannels[ytc_id]['channels'].append(ctx.channel.id)
        await self.config.guild(ctx.guild).channel_count.set(await self.config.guild(ctx.guild).channel_count() + 1)
        await ctx.tick()

    @ytu_channel.command(name="remove", aliases=['rm', 'delete', 'del'])
    @commands.has_guild_permissions(manage_messages=True)
    async def ytuc_rm(self, ctx, url):
        """Remove a channel"""
        if not (match := CHANNEL_URL_REGEX.match(url)):
            await ctx.send("URL is not a valid youtube channel.")
            return
        ytc_id = match.group(1)
        async with self.config.ytchannels() as ytchannels:
            if ytc_id not in ytchannels or \
                    ctx.channel.id not in ytchannels[ytc_id]['channels']:
                await ctx.send("This channel is not configured to recieve updates"
                               " from that youtube channel.")
            ytchannels[ytc_id]['channels'].remove(ctx.channel.id)
            if not ytchannels[ytc_id]['channels']:
                del ytchannels[ytc_id]
        await self.config.guild(ctx.guild).channel_count.set(await self.config.guild(ctx.guild).channel_count() - 1)
        await ctx.tick()

    @ytu_channel.command(name="listall")
    async def ytuc_listall(self, ctx):
        """List all set up channels"""
        ytchannels = ['https://www.youtube.com/channel/' + ytcid
                      for ytcid in await self.config.ytchannels()]
        for page in pagify('\n'.join(ytchannels)):
            await ctx.send(box(page))

    @ytu_channel.command(name="list")
    async def ytuc_list(self, ctx):
        """List the channels set in this channel"""
        ytchannels = ['https://www.youtube.com/channel/' + ytcid
                      for ytcid, cdata in (await self.config.ytchannels()).items()
                      if ctx.channel.id in cdata['channels']]
        for page in pagify('\n'.join(ytchannels)):
            await ctx.send(box(page))

    async def ensure_api(self) -> bool:
        keys = await self.bot.get_shared_api_tokens("youtube")
        return "apikey" in keys

    def make_embed(self, video, channel_data) -> Embed:
        return EmbedView(
            EmbedMain(
                color=discord.Color.red(),
                title=f"New Video: {video['snippet']['title']}",
                url="https://www.youtube.com/watch?v=" + video['id']['videoId'],
                description=video['snippet']['description'].split("\n\n")[0],
            ),
            embed_thumbnail=EmbedThumbnail(channel_data['snippet']['thumbnails']['default']['url']),
            embed_fields=[
                EmbedField("Subscribers", Text(channel_data['statistics']['subscriberCount']), inline=True),
                EmbedField("Views", Text(channel_data['statistics']['viewCount']), inline=True),
            ],
            embed_footer=EmbedFooter(
                isoparse(video['snippet']['publishedAt']).strftime(
                    f"Posted by {channel_data['snippet']['title']} at %X %Z on %A %B %d, %Y"
                ),
                "https://logos-world.net/wp-content/uploads/2020/04/YouTube-Emblem-700x394.png"
            ),
            embed_body_image=EmbedBodyImage(video['snippet']['thumbnails']['high']['url']),
        ).to_embed()
