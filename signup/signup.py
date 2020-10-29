import asyncio
import discord
import logging
import emoji as emoji_module
import datetime
import re
from redbot.core import checks, commands, Config, modlog
from redbot.core.utils.chat_formatting import box, inline, pagify

logger = logging.getLogger('red.RedbotCogs.signup')

TIME_STRINGS = {
    's': 'seconds',
    'm': 'minutes',
    'h': 'hours',
    'd': 'days',
    'w': 'weeks',
}

class SignUp(commands.Cog):
    """Signup Cog"""

    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.config = Config.get_conf(self, identifier=7077327)
        self.config.register_global(events={})

        self._loop = bot.loop.create_task(self.signup_loop())

    def cog_unload(self):
         self._loop.cancel()

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
    async def signup(self, ctx, event_name, time, role: discord.Role, max_players: int, emoji):
        """Invite users to an event

        [p]signup "Event Name" 10m @role 10 \N{GRINNING FACE}"""
        try:
            emoji = await commands.EmojiConverter().convert(ctx, emoji)
        except commands.BadArgument:
            if emoji not in emoji_module.UNICODE_EMOJI:
                await ctx.send("I do not have access to emoji `{}`".format(emoji))
                return

        r = re.findall(r'(\d+) ?([smhdw])[a-z]*', time.lower())
        if not r or re.sub(r'(\d+) ?([smhdw])[a-z]*', '', time.lower()):
            await ctx.send(f"Invalid time: {time.lower()}.  Try using something like `5m` for 5 minutes or"
                           f" `3d` for 3 days.")
            return
        time = datetime.timedelta(**{TIME_STRINGS[u]: int(a) for a, u in r})
        attime = datetime.datetime.now()+time

        await ctx.message.delete()
        m = await ctx.send(f"{role.mention}\n\n"
                           f"{ctx.author.mention} is hosting\n"
                           f"**{event_name}**\n"
                           f"in {str(time)}\n\n"
                           f"Please react to this message with {str(emoji)} to sign up.\n\n"
                           f"We will need {max_players} people.")
        await m.add_reaction(emoji)

        async with self.config.events() as events:
            events[str(datetime.datetime.now().timestamp())] = {
                "eventname": event_name,
                "maxusers": max_players,
                "author": ctx.author.id,
                "message": m.id,
                "channel": m.channel.id,
                "emoji": emoji.id if isinstance(emoji, discord.Emoji) else emoji,
                "time": attime.timestamp()
            }
        await ctx.tick()

    async def signup_loop(self):
        await self.bot.wait_until_ready()
        while self == self.bot.get_cog("SignUp"):
            try:
                async with self.config.events() as events:
                    for event, data in tuple(events.items()):
                        c = self.bot.get_channel(data['channel'])
                        if c is None:
                            continue
                        try:
                            m = await c.fetch_message(data['message'])
                        except Exception:
                            continue


                        reaction = discord.utils.find(
                                     lambda r: r.emoji.id == data['emoji'].id
                                               if isinstance(
                                                   data['emoji'],
                                                   (discord.Emoji, discord.PartialEmoji))
                                               else r.emoji == data['emoji'],
                                     m.reactions
                                   )

                        if not reaction and datetime.datetime.now().timestamp() > data['time']:
                            del events[event]
                            continue

                        if datetime.datetime.now().timestamp() > data['time'] or reaction.count > data['maxusers']:
                            ustr = "\n".join(f"{c}. {u.mention}"
                                             for c, u
                                             in enumerate([u
                                                           for u
                                                           in await reaction.users(limit=data['maxusers']+1).flatten()
                                                           if u != self.bot.user], 1))
                            await m.delete()
                            a = self.bot.get_user(data['author'])
                            tdiff = datetime.timedelta(seconds=max(0, data['time']-datetime.datetime.now().timestamp()))
                            await c.send(f"{a.mention if a else '@deleted-user'}\n\n"
                                         f"{reaction.count-1} user(s) have signed up for\n"
                                         f"**{data['eventname']}**\n\n"
                                         f"{ustr}\n\n"
                                         f"Please meet up with {a.mention}{' in '+str(tdiff).split('.')[0] if tdiff else ''}")
                            del events[event]

            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("Error in signup loop:")
            await asyncio.sleep(3)
