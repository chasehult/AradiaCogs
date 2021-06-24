import asyncio
import logging
import random
from typing import Optional

import aiohttp
import discord
from io import BytesIO

from redbot.core import commands, Config, checks
from Weverse import WeverseClientAsync
from redbot.core.utils.chat_formatting import humanize_list, inline

logger = logging.getLogger('red.aradiacogs.weverse')


class Weverse(commands.Cog):
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.config = Config.get_conf(self, identifier=7373253)
        self.config.register_global(token=None, seen=[])
        self.config.register_channel(channels={})

        self.weverse_client: Optional[WeverseClientAsync] = None
        self.session = aiohttp.ClientSession()
        self.ready = asyncio.Event()

        bot.loop.create_task(self.init())
        self._loop = bot.loop.create_task(self.run_loop())

    async def init(self):
        if await self.config.token() is None:
            for owner_id in self.bot.owner_ids:
                await self.bot.get_user(owner_id).send(f"Please set up your Weverse authorization token with"
                                                       f" `{(await self.bot.get_valid_prefixes())[0]}weverse settoken"
                                                       f" <token>`.  Instructions on how to get an authorization token"
                                                       f" can be found at https://pastebin.com/raw/pBvn2KsX.")
                return
        self.weverse_client = WeverseClientAsync(authorization=await self.config.token(),
                                                 web_session=self.session,
                                                 verbose=True, loop=self.bot.loop)
        try:
            await self.weverse_client.start()
        except Exception:
            self.weverse_client = None
            raise
        finally:
            self.ready.set()

    async def wait_until_ready(self, ctx):
        await self.ready.wait()
        if self.weverse_client is None:
            await ctx.send("Weverse client initialization failed.  Check your logs for more info.")
            return False
        if not self.weverse_client.cache_loaded:
            await ctx.send(f"Weverse cache is being updated. Please try again in a minute or two.")
            return False
        return True

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
        await asyncio.sleep(10)
        while True:
            try:
                await self.update_weverse()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in loop")
            await asyncio.sleep(30)

    @commands.group()
    async def weverse(self, ctx):
        """Subcommand for Weverse related commands."""

    @weverse.command()
    @commands.is_owner()
    async def settoken(self, ctx, token):
        """Set the Weverse API token.

        This must be done every 6 months.  Instructions here: https://pastebin.com/raw/pBvn2KsX
        """
        await self.config.token.set(token)
        try:
            await self.init()
        except Exception:
            logger.exception("Weverse connection failed.")
            await ctx.send("The connection failed.  Check your logs for more info.")
            await self.config.token.set(None)
            return
        await ctx.tick()

    @weverse.command()
    @commands.is_owner()
    async def resetclient(self, ctx):
        """Reset the Weverse client.  Do this when you've subscribed to new channels."""
        await self.init()
        await ctx.tick()

    @weverse.command(name="add")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def weverse_add(self, ctx, channel: Optional[discord.TextChannel], community_name, role: discord.Role = None):
        """Receive Weverse updates from a specific Weverse community.

        If the community is multiple words, surround the entire thing in quotes.
        """
        if not await self.wait_until_ready(ctx):
            return

        if channel is None:
            channel = ctx.channel
        if role is None:
            role_id = 0
        else:
            role_id = role.id

        community_name = community_name.lower()

        async with self.config.channel(channel).channels() as chans:
            if community_name in chans:
                if role_id != chans[community_name]['role_id']:
                    chans[community_name]['role_id'] = role_id
                    await ctx.send(f"Role updated for community `{community_name}`.")
                    return

            for community in self.weverse_client.all_communities.values():
                if community.name.lower() == community_name:
                    chans[community_name] = {
                        'role_id': role_id,
                        'show_comments': True,
                    }

                    await ctx.send(f"You will now receive weverse updates for {community.name}.")
                    return
            available = humanize_list([inline(com.name) for com in self.weverse_client.all_communities.values()])
            await ctx.send(f"I could not find {community_name}. Available choices are:\n" + available)

    @weverse.command(name="remove")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def weverse_remove(self, ctx, channel: Optional[discord.TextChannel], community_name):
        """Stop recieving Weverse Updates from a specific Weverse community in the current text channel.

        If the community is multiple words, surround the entire thing in quotes.
        """
        if channel is None:
            channel = ctx.channel

        async with self.config.channel(channel).channels() as chans:
            if community_name not in chans:
                await ctx.send("This community is not set up to notify the channel.")
                return
            del chans[community_name]
        await ctx.send(f"You will no longer receive weverse updates for {community_name}.")

    @weverse.command(name="list")
    @commands.guild_only()
    async def weverse_list(self, ctx, channel: discord.TextChannel = None):
        """Receive Weverse updates from a specific Weverse community.

        If the community is multiple words, surround the entire thing in quotes.
        """
        if channel is None:
            channel = ctx.channel

        chans = [inline(chan) for chan in await self.config.channel(channel).channels()]

        if not chans:
            await ctx.send("There are no communities set up to notify in this channel.")
            return

        await ctx.send(f"The communities set to notify in this channel are {humanize_list(chans)}.")

    @weverse.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def showcomments(self, ctx, channel: Optional[discord.TextChannel], community_name, enable: bool):
        """Enable or disable updates for comments on a community.

        If the community is multiple words, surround the entire thing in quotes.
        """
        if channel is None:
            channel = ctx.channel

        async with self.config.channel(channel).channels() as chans:
            if community_name not in chans:
                await ctx.send("This community is not set up to notify the channel.")
                return
            chans[community_name]['show_comments'] = enable
        await ctx.send(f"You will {'now' if enable else 'no longer'} recieve"
                       f" channel notifications from {community_name}.")

    async def update_weverse(self):
        """Process for checking for Weverse updates and sending to discord channels."""
        if self.weverse_client is None or not self.weverse_client.cache_loaded:
            return

        await self.weverse_client.check_new_user_notifications()

        user_notifications = self.weverse_client.user_notifications
        for notif in user_notifications:
            async with self.config.seen() as seen:
                seen.append(notif.id)
            community_name = notif.community_name or notif.bold_element
            if not community_name or notif.id in await self.config.seen():
                continue

            channels = [(c_id, data['channels'][community_name.lower()])
                        for c_id, data in (await self.config.all_channels()).items()
                        if community_name.lower() in data['channels']]

            if not channels:
                continue

            noti_type = self.weverse_client.determine_notification_type(notif.message)
            embed_title = f"New {community_name} Notification!"
            is_comment = False
            message_text = None
            if noti_type == 'comment':
                is_comment = True
                embed = await self.set_comment_embed(notif, embed_title)
            elif noti_type == 'post':
                embed, message_text = await self.set_post_embed(notif, embed_title)
            elif noti_type == 'media':
                embed, message_text = await self.set_media_embed(notif, embed_title)
            elif noti_type == 'announcement':
                continue  # not keeping track of announcements ATM
            else:
                continue

            if not embed:
                continue

            for channel_id, data in channels:
                await self.send_weverse_to_channel(channel_id, data, message_text, embed, is_comment, community_name)


    async def set_comment_embed(self, notification, embed_title):
        """Set Comment Embed for Weverse."""
        comment_body = await self.weverse_client.fetch_comment_body(notification.community_id, notification.contents_id)
        if not comment_body:
            artist_comments = await self.weverse_client.fetch_artist_comments(notification.community_id,
                                                                              notification.contents_id)
            if artist_comments:
                comment_body = artist_comments[0].body
            else:
                return
        translation = await self.translate(comment_body)

        embed_description = (f"**{notification.message}**\n\n"
                             f"Content: **{comment_body}**" +
                             (f"\nTranslated Content: **{translation}**" if translation else ""))
        embed = discord.Embed(title=embed_title, description=embed_description,
                              color=discord.Color(random.randint(0x000000, 0xffffff)))
        return embed

    async def set_post_embed(self, notification, embed_title):
        """Set Post Embed for Weverse."""
        post = self.weverse_client.get_post_by_id(notification.contents_id)
        if post:
            translation = await self.translate(post.body)

            # artist = self.weverse_client.get_artist_by_id(notification.artist_id)
            embed_description = (f"**{notification.message}**\n\n"
                                 f"Artist: **{post.artist.name} ({post.artist.list_name[0]})**\n"
                                 f"Content: **{post.body}**" +
                                 (f"\nTranslated Content: **{translation}**" if translation else ""))
            embed = discord.Embed(title=embed_title, description=embed_description,
                                  color=discord.Color(random.randint(0x000000, 0xffffff)))
            message = "\n".join(photo.original_img_url for photo in post.photos)
            return embed, message
        return None, None

    async def set_media_embed(self, notification, embed_title):
        """Set Media Embed for Weverse."""
        media = self.weverse_client.get_media_by_id(notification.contents_id)
        if media:
            embed_description = f"**{notification.message}**\n\n" \
                                f"Title: **{media.title}**\n" \
                                f"Content: **{media.body}**\n"
            embed = discord.Embed(title=embed_title, description=embed_description,
                                  color=discord.Color(random.randint(0x000000, 0xffffff)))
            message = media.video_link
            return embed, message
        return None, None

    async def send_weverse_to_channel(self, channel_id, channel_data, message_text, embed, is_comment, community_name):
        role_id = channel_data['role_id']
        comments_enabled = channel_data['show_comments']
        if not is_comment or comments_enabled:
            channel = self.bot.get_channel(channel_id)
            try:
                await channel.send(embed=embed)
                if message_text:
                    # Since an embed already exists, any individual content will not load
                    # as an embed -> Make it it's own message.
                    if role_id:
                        message_text = f"<@&{role_id}>\n{message_text}"
                    await channel.send(message_text)

            except Exception:
                pass

    async def translate(self, text: str) -> Optional[str]:
        if self.bot.get_cog("Translate") and self.bot.get_cog("Translate").aservice:
            return await self.bot.get_cog("Translate").a_translate_lang('ko', 'en', text)
