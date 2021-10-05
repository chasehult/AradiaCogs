import asyncio
import html
import logging
from contextlib import suppress
from datetime import datetime
from io import BytesIO
from typing import NoReturn

import aiohttp
import discord
from aiohttp import ClientResponseError
from discordmenu.embed.components import EmbedBodyImage, EmbedField, EmbedFooter, EmbedMain, EmbedThumbnail
from discordmenu.embed.text import Text
from discordmenu.embed.view import EmbedView
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box
from tsutils.helper_functions import repeating_timer

logger = logging.getLogger('red.aradiacogs.vlive')
fields = "attachments,author,availableActions,channel{channelName,channelCode}," \
         "totalCommentCount,createdAt,emotionCount,lastModifierMember,notice," \
         "officialVideo,originPost,plainBody,postId,postVersion,reservation," \
         "starReactions,targetMember,thumbnail,title,url,writtenIn"


class VLive(commands.Cog):
    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.config = Config.get_conf(self, identifier=77173)
        self.config.register_global(seen=[], channels={})

        self.session = aiohttp.ClientSession()

        self._loop = bot.loop.create_task(self.do_loop())

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

    async def do_loop(self) -> NoReturn:
        await self.bot.wait_until_ready()
        with suppress(asyncio.CancelledError):
            async for _ in repeating_timer(60):
                try:
                    await self.do_check()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Error in loop:")

    async def do_check(self):
        async with self.config.seen() as seen:
            for vchannel, vdata in (await self.config.channels()).items():
                for video in (await self.get_data(vchannel))['data']:
                    if 'officialVideo' not in video:
                        continue
                    if video['postId'] in seen:
                        continue
                    with suppress(discord.Forbidden):
                        embed = await self.send_video(video)
                    for conf in vdata:
                        if (channel := self.bot.get_channel(conf['channel'])) is None:
                            continue
                        text = ""
                        if conf.get('role'):
                            text = f"<@&{conf['role']}>"
                        await channel.send(text, embed=embed)
                    seen.append(video['postId'])

    @commands.group()
    async def vlive(self, ctx):
        """The base command for VLive related subcommands"""

    @vlive.command(name="add")
    async def v_add(self, ctx, channel_name, role: discord.Role = None):
        """Subscribe to a VLive channel in this Discord channel"""
        if 'appID' not in await self.bot.get_shared_api_tokens("vlive"):
            return await ctx.send(f"You need to set up your app ID with"
                                  f" `{ctx.prefix}set api vlive appID <APP ID>`")

        async with self.config.channels() as channels:
            if channel_name not in channels:
                async with self.config.seen() as seen:
                    try:
                        for video in (await self.get_data(channel_name))['data']:
                            seen.append(video['postId'])
                    except ClientResponseError as cre:
                        if cre.status == 404:
                            return await ctx.send("Invalid channel.")
                channels[channel_name] = []
            role_id = role.id if role else None
            for conf in channels[channel_name][:]:
                if conf['channel'] == ctx.channel.id:
                    channels[channel_name].remove(conf)
            channels[channel_name].append({'channel': ctx.channel.id, 'role': role_id})
        await ctx.tick()

    @vlive.command(name="remove")
    async def v_remove(self, ctx, channel_name):
        """Remove a subscribed VLive channel from this Discord channel"""
        async with self.config.channels() as channels:
            if channel_name in channels:
                for conf in channels[channel_name][:]:
                    if conf['channel'] == ctx.channel.id:
                        channels[channel_name].remove(conf)
            if not channels[channel_name]:
                del channels[channel_name]
        await ctx.tick()

    @vlive.command(name="list")
    async def v_list(self, ctx):
        """List all subscribed VLive channels"""
        channels = await self.config.channels()
        valid_channels = []
        for vc, data in channels.items():
            if any(ctx.channel.id == conf['channel'] for conf in data):
                valid_channels.append(f"{(await self.get_data(vc))['data'][0]['channel']['channelName']} ({vc})")
        await ctx.send(box('\n'.join(valid_channels)))

    async def get_data(self, channel):
        app_id = (await self.bot.get_shared_api_tokens("vlive"))['appID']

        endpoint = "https://www.vlive.tv/globalv-web/vam-web/post/v1.0/channel-{}/starPosts"
        params = {'appId': app_id, 'fields': fields, 'gcc': 'HU', 'locale': 'en_US'}
        headers = {'Referer': 'https://www.vlive.tv/'}

        async with aiohttp.ClientSession() as session:
            async with session.get(endpoint.format(channel), params=params, headers=headers) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def send_video(self, video):
        return EmbedView(
            EmbedMain(
                color=discord.Color(0x82ecf5),
                title=f"{video['author']['officialName']}"
                      f" {'Now Live' if video['officialVideo']['type'] == 'LIVE' else 'New Video'}:"
                      f" {html.unescape(video['officialVideo']['multinationalTitles'][0]['label'])}",
                url=video['url']
            ),
            embed_thumbnail=EmbedThumbnail(video['author']['profileImageUrl']),
            embed_fields=[
                EmbedField("Views", Text(f"{video['officialVideo']['playCount']:,}"), inline=True),
                EmbedField("Likes", Text(f"{video['officialVideo']['likeCount']:,}"), inline=True),
            ],
            embed_footer=EmbedFooter(
                datetime.fromtimestamp(video['officialVideo']['willStartAt'] // 1000).strftime(
                    f"Posted by {video['author']['officialName']} at %X %Z on %A %B %d, %Y"
                ),
                "https://i.imgur.com/gHo7BTO.png"
            ),
            embed_body_image=EmbedBodyImage(video['officialVideo']['thumb']),
        ).to_embed()
