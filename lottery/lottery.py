import logging
import random
from io import BytesIO

import discord
import emoji as emoji_module
from redbot.core import checks, commands, Config
from redbot.core.utils.chat_formatting import box, inline, pagify

logger = logging.getLogger('red.misc-cogs.grantrole')


class Lottery(commands.Cog):
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.config = Config.get_conf(self, identifier=7077327)
        self.config.register_guild(on_react={}, pools={})

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        data = "No data is stored for user with ID {}.\n".format(user_id)
        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data.

        No personal data is stored in this cog.
        """
        return

    @commands.group(invoke_without_command=True)
    @checks.mod_or_permissions(manage_roles=True)
    async def lottery(self, ctx, lotteryname):
        """Manage or run a lottery"""
        on_react = await self.config.guild(ctx.guild).on_react()
        if lotteryname not in on_react:
            await ctx.send("That lottery does not exist.")
            return
        lottery = on_react[lotteryname]
        members = [m
                   for m
                   in ctx.guild.members
                   if on_react[lotteryname]['role'] in [r.id for r in m.roles]
                   ]
        if not members:
            await ctx.send("Nobody has entered this lottery.")
            return
        random.shuffle(members)
        chan = self.bot.get_channel(on_react[lotteryname]['channel'])
        if chan is not None:
            try:
                m = await chan.fetch_message(on_react[lotteryname]['message'])
                if m is not None:
                    await m.delete()
            except discord.NotFound:
                pass
        await members[0].remove_roles(ctx.guild.get_role(on_react[lotteryname]['role']))
        if lottery.get("prizelist"):
            pools = await self.config.guild(ctx.guild).pools()
            await ctx.send("{} has won {}".format(members[0].mention, random.choice(pools[lottery.get("prizelist")])))
        else:
            await ctx.send("The winner is {}".format(members[0].mention))

    @lottery.command(name="add")
    async def lottery_add(self, ctx, lotteryname, message: discord.Message, emoji):
        """Create a lottery"""
        try:
            emoji = await commands.EmojiConverter().convert(ctx, emoji)
        except commands.BadArgument:
            if emoji not in emoji_module.UNICODE_EMOJI:
                await ctx.send("I do not have access to emoji `{}`".format(emoji))
                return
        await message.add_reaction(emoji)
        role = discord.utils.get(ctx.guild.roles, name=lotteryname)
        if role is None:
            try:
                role = await ctx.guild.create_role(name=lotteryname)
            except discord.Forbidden:
                await ctx.send("I don't have permission to create a role here.")
                return
        async with self.config.guild(ctx.guild).on_react() as on_react:
            on_react[lotteryname] = {
                "message": message.id,
                "emoji": emoji.id if isinstance(emoji, discord.Emoji) else emoji,
                "role": role.id,
                "channel": message.channel.id,
                "enabled": True,
                "prizelist": None
            }
        await ctx.tick()

    @lottery.command(name="delete")
    async def lottery_delete(self, ctx, lotteryname):
        """Delete a lottery"""
        async with self.config.guild(ctx.guild).on_react() as on_react:
            if lotteryname not in on_react:
                await ctx.send("That lottery does not exist.")
                return
            del on_react[lotteryname]
        await ctx.tick()

    @lottery.command(name="prizelist")
    async def lottery_prizelist(self, ctx, name):
        """Create a prizelist"""
        async with self.config.guild(ctx.guild).pools() as pools:
            if name in pools:
                await ctx.send("That prizelist already exists.")
                return
            pools[name] = []
        await ctx.tick()

    @lottery.command(name="addprize")
    async def lottery_addprize(self, ctx, prizelist, *, prizes):
        """Add one or more prizes to a prizelist

        Prizes should be separated by a semicolon (`;`)
        """
        prizes = [p.strip() for p in prizes.split(";")]
        async with self.config.guild(ctx.guild).pools() as pools:
            if prizelist not in pools:
                await ctx.send("There is no prizelist with that name.")
                return
            pools[prizelist].extend(prizes)
        await ctx.tick()

    @lottery.command(name="removeprize", aliases=['rmprize'])
    async def lottery_removeprize(self, ctx, prizelist, *, prizes):
        """Remove one or more prizes from a prizelist

        Prizes should be separated by a semicolon (`;`)
        """
        prizes = [p.strip() for p in prizes.split(";")]
        async with self.config.guild(ctx.guild).pools() as pools:
            if prizelist not in pools:
                await ctx.send("There is no prizelist with that name.")
                return
            for p in prizes:
                if p not in pools[prizelist]:
                    await ctx.send(inline(p) + " is not in prizelist " + inline(prizelist))
                else:
                    pools[prizelist].remove(p)
        await ctx.tick()

    @lottery.command(name="bind")
    async def lottery_bind(self, ctx, lottery, prizelist):
        """Bind a prizelist to a lottery"""
        pools = await self.config.guild(ctx.guild).pools()
        if prizelist not in pools:
            await ctx.send("There is no prizelist with that name.")
            return
        async with self.config.guild(ctx.guild).on_react() as lotteries:
            if lottery not in lotteries:
                await ctx.send("There is no lottery with that name.")
                return
            lotteries[lottery]["prizelist"] = prizelist
        await ctx.tick()

    @lottery.command(name="unbind")
    async def lottery_unbind(self, ctx, lottery):
        """Unbind a prizelist from a lottery"""
        async with self.config.guild(ctx.guild).on_react() as lotteries:
            if lottery not in lotteries:
                await ctx.send("There is no lottery with that name.")
                return
            lotteries[lottery]["prizelist"] = None
        await ctx.tick()

    @lottery.command(name="prizes")
    async def lottery_prizes(self, ctx, prizelist):
        """Show the items in a prizelist"""
        pools = await self.config.guild(ctx.guild).pools()
        if prizelist not in pools:
            await ctx.send("There is no prizelist with that name.")
            return
        for page in pagify("\n".join(pools[prizelist])):
            await ctx.send(box(page))

    @commands.Cog.listener('on_raw_reaction_add')
    async def on_reaction_add(self, payload):
        if not payload.guild_id \
                or payload.member.bot \
                or await self.bot.cog_disabled_in_guild(self, payload.member.guild):
            return
        lotteries = await self.config.guild(payload.member.guild).on_react()

        for name, lot in lotteries.items():
            if lot['message'] == payload.message_id:
                try:
                    emoji = payload.emoji.name if isinstance(payload.emoji, discord.PartialEmoji) else payload.emoji.id

                    if emoji != lot['emoji'] or not lot['enabled']:
                        continue

                    role = payload.member.guild.get_role(lot['role'])
                    if role is not None:
                        await payload.member.add_roles(role, reason="Lottery React Role Grant")
                except discord.Forbidden:
                    logger.exception("Unable to add roles in guild: {}".format(payload.guild_id))
                    return

    @commands.Cog.listener('on_raw_reaction_remove')
    async def on_reaction_remove(self, payload):
        try:
            guild = self.bot.get_guild(payload.guild_id)
            member = await guild.fetch_member(payload.user_id)
        except (AttributeError, discord.NotFound):
            return

        if not payload.guild_id \
                or member.bot \
                or await self.bot.cog_disabled_in_guild(self, guild):
            return

        lotteries = await self.config.guild(guild).on_react()
        for name, lot in lotteries.items():
            if lot['message'] == payload.message_id:
                try:
                    emoji = payload.emoji.name if isinstance(payload.emoji, discord.PartialEmoji) else payload.emoji.id
                    if emoji != lot['emoji'] or not lot['enabled']:
                        continue
                    role = guild.get_role(lot['role'])
                    if role is not None:
                        await member.remove_roles(role, reason="Lottery React Role Removal")
                except discord.Forbidden:
                    logger.exception("Unable to remove roles in guild: {}".format(guild.id))
                    return

    async def can_assign(self, ctx, role):
        if ctx.author.id == ctx.guild.owner_id:
            return True
        if ctx.author.top_role < role:
            await ctx.send("You're not high enough on the heirarchy enough assign this role.")
            return False
        if ctx.me.top_role < role:
            await ctx.send("I'm not high enough on the heirarchy enough assign this role.")
            return False
        return True
