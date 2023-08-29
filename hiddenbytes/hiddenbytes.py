import asyncio
import logging
import random
import re
from copy import deepcopy
from io import BytesIO

import discord
from discord import PermissionOverwrite
from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import humanize_list
from redbot.core.utils.predicates import MessagePredicate
from tsutils.user_interaction import StatusManager

from hiddenbytes.admin_mixin import AdminMixin
from hiddenbytes.constants import ASPECTS, BLURBS
from hiddenbytes.dm_mixin import DMMixin
from hiddenbytes.land_mixin import LandMixin
from hiddenbytes.sburb_mixin import SburbMixin

logger = logging.getLogger('red.aradia-cogs.hiddenbytes')


class HiddenBytes(commands.Cog, AdminMixin, DMMixin, SburbMixin, LandMixin):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

        self.config = Config.get_conf(self, identifier=hash('hiddenbytes'))
        self.config.register_guild(total_players=6, categories={},
                                   dms={})
        self.config.register_member(player={}, channels={}, dm_requests=[], sburb_requests=[])

        self.setup_lock = asyncio.Lock()

        if (old_cmd := bot.get_command('dm')):
            bot.remove_command(old_cmd.name)
        if (old_cmd := bot.get_command('help')):
            bot.remove_command(old_cmd.name)

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        data = "No data is stored for user with ID {}.\n".format(user_id)
        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data.

        No personal data is stored in this cog.
        """
        return

    @commands.Cog.listener()
    async def on_member_join(self, member):
        nar_category = member.guild.get_channel((await self.config.guild(member.guild).categories())['narrators'])
        chan = await member.guild.create_text_channel(name=member.name, category=nar_category, overwrites={
            member: PermissionOverwrite(read_messages=True)
        })
        async with self.config.member(member).channels() as chans:
            chans['narrator'] = chan.id

        await chan.send(f"Hello, {member.mention}.  Welcome to HiddenBytes.  This session will be unique, as you'll be"
                        f" left completely in the dark about everything, even the number of other narrators.  In"
                        f" order to start writing your story, you'll need a muse.  Please set one up with `> setup`."
                        f"  Hopefully this step won't take too long.  We'll need to wait for everyone to have a"
                        f" muse before we can start.  If you have any questions at any time, use"
                        f" `> contact <question>`, and you will receive help as soon as possible.")

        taken_aspects = set()
        for _, data in (await self.config.all_members(member.guild)).items():
            player = data['player']
            if player:
                taken_aspects.add(player['aspect'])

        await chan.send(f"Available aspects are:\n" + humanize_list([*map(str.capitalize, ASPECTS - taken_aspects)]))

    @commands.command(hidden=True)
    async def setup(self, ctx):
        if await self.config.member(ctx.author).player():
            return await ctx.send("You have already created your muse.  Please wait for everyone else to finish.")

        taken_aspects = set()
        taken_acronyms = set()
        finished_players = 0
        for mid, data in (await self.config.all_members(ctx.guild)).items():
            if mid == ctx.guild.owner:
                continue
            player = data['player']
            if player:
                taken_aspects.add(player['aspect'])
                taken_acronyms.add(player['acronym'])
                finished_players += 1

        if self.setup_lock.locked():
            return await ctx.send("Another narrator is creating their muse.  Please wait a few minutes and try again.")

        async with self.setup_lock, StatusManager(self.bot):
            blurb = ""
            # Aspect
            await ctx.send("What is your muse's aspect?")
            try:
                msg = await self.bot.wait_for("message", check=MessagePredicate.same_context(ctx), timeout=20)
            except asyncio.TimeoutError:
                return await ctx.send("You took too long to respond.  Use `> setup` to try again.")
            if (aspect := msg.content.lower()) not in ASPECTS:
                return await ctx.send("This is not a valid aspect.  Use `> setup` to try again.")
            elif aspect in taken_aspects:
                valid_aspects_str = humanize_list([*map(str.capitalize, ASPECTS - taken_aspects)])
                return await ctx.send(f"This apsect is taken.  The available choices are:\n{valid_aspects_str}"
                                      f"\nUse `> setup` to try again.")

            # Handle
            await ctx.send("What is your muse's handle?")
            try:
                msg = await self.bot.wait_for("message", check=MessagePredicate.same_context(ctx), timeout=20)
            except asyncio.TimeoutError:
                return await ctx.send("You took too long to respond.  Use `> setup` to try again.")
            if not re.fullmatch(r'[a-z]+[A-Z][a-z]+', (handle := msg.content)):
                return await ctx.send("Your handle is invalid.  Use `> setup` to try again.")
            elif (acronym := ''.join(re.match(r'(.)[a-z]*([A-Z])', handle).groups()).upper()) in taken_acronyms:
                return await ctx.send("This acronym is taken.  Use `> setup` to try another.")

            # Hex
            await ctx.send("What is your muse's hex code?")
            try:
                msg = await self.bot.wait_for("message", check=MessagePredicate.same_context(ctx), timeout=20)
            except asyncio.TimeoutError:
                return await ctx.send("You took too long to respond.  Use `> setup` to try again.")
            if not re.fullmatch(r'#?[0-9a-fA-F]{6}', msg.content):
                return await ctx.send("Your hex code is invalid.  Use `> setup` to try again.")
            hex_code = re.match(r'#?([0-9a-fA-F]{6})', msg.content).group(1)

            # Species
            await ctx.send("Is your muse a **human** or a **troll**?")
            try:
                msg = await self.bot.wait_for("message", check=MessagePredicate.same_context(ctx), timeout=20)
            except asyncio.TimeoutError:
                return await ctx.send("You took too long to respond.  Use `> setup` to try again.")
            if not (species := msg.content.lower()) in ('human', 'troll'):
                return await ctx.send("This species is not valid.  Use `> setup` to try again.")

            # Famous
            await ctx.send("Is your muse well known enough for other muses to have heard of them? (yes/no)")
            famous = MessagePredicate.yes_or_no(ctx)
            try:
                await self.bot.wait_for("message", check=famous, timeout=20)
            except asyncio.TimeoutError:
                return await ctx.send("You took too long to respond.  Use `> setup` to try again.")
            if famous.result:
                await ctx.send(f"Alright.  Please send a short blurb in proper English about your muse for me"
                               f" to send to other {species}s.  You have 5 minutes.")
                try:
                    msg = await self.bot.wait_for("message", check=MessagePredicate.same_context(ctx), timeout=60 * 5)
                except asyncio.TimeoutError:
                    return await ctx.send("You took too long to respond.  Use `> setup` to try again.")
                blurb = msg.content

            # Confirm
            role = await ctx.guild.create_role(name=handle, color=int(hex_code, 16))
            await ctx.send(f"To confirm, you would like {role.mention} to be a {species} of the {aspect.capitalize()}"
                           f" aspect with hex code #{hex_code.lower()}? (yes/no)")
            pred = MessagePredicate.yes_or_no(ctx)
            try:
                await self.bot.wait_for("message", check=pred, timeout=20)
            except asyncio.TimeoutError:
                await role.delete()
                return await ctx.send("You took too long to respond.  Use `> setup` to try again.")
            if not pred.result:
                await role.delete()
                return await ctx.send("Alright.  Use `> setup` to try again.")

            await ctx.send("Alright.  I'll set things up for you.")

            await self.config.member(ctx.author).player.set({
                'aspect': aspect,
                'acronym': acronym,
                'handle': handle,
                'role': role.id,
                'species': species,
                'blurb': blurb,
                'client': None,
            })
            await ctx.author.add_roles(role)
            try:
                await ctx.author.edit(nick=handle)
            except discord.Forbidden:
                pass

        await ctx.send("Your muse has been locked in.")
        land_category = ctx.guild.get_channel((await self.config.guild(ctx.guild).categories())['lands'])
        land_chan = await ctx.guild.create_text_channel(name=f"your-{'hive' if species == 'troll' else 'house'}",
                                                        category=land_category,
                                                        overwrites={
                                                            ctx.author: PermissionOverwrite(read_messages=True)
                                                        })
        await land_chan.send(
            "This is your muse's house channel.  Use `> land rename <new name>` to rename it.  When you"
            " see <>s in a command, that means whatever is there should be replaced.  For example, if"
            " you wrote `> land rename The Slut Shack`, your house channel would be renamd to \"The"
            " Slut Shack\".  You should not include the angle brackets.  Use this command again to rename"
            " to your land name once you enter the game.  I recommend you use all commands in your narrator channel,"
            " though they will work wherever you send them.  It's just cleaner that way.")

        async with self.config.member(ctx.author).channels() as chans:
            chans['land'] = land_chan.id

        for mid, data in (await self.config.all_members(ctx.guild)).items():
            if mid == ctx.guild.owner:
                continue
            if mid == ctx.author.id:
                continue
            member = ctx.guild.get_member(mid)
            chan = ctx.guild.get_channel(data['channels']['narrator'])
            await chan.send(f"The {aspect.capitalize()} aspect has been taken.")

        finished_players += 1
        if finished_players < await self.config.guild(ctx.guild).total_players():
            return await ctx.send("Please wait for everyone to submit their muse.")
        else:
            await ctx.send("It is time to begin.")
            await self.start_game(ctx.guild)

    async def start_game(self, guild: discord.Guild):
        blurbs = deepcopy(BLURBS)
        players = []
        for mid, data in (await self.config.all_members(guild)).items():
            if mid == guild.owner:
                continue
            player = data['player']
            if player['blurb']:
                blurbs[player['species']].append(player['blurb'])
            players.append(player['handle'])
        random.shuffle(blurbs['human'])
        random.shuffle(blurbs['troll'])

        shuffled = players[:]
        shuffled.append(shuffled.pop(0))

        for mid, data in (await self.config.all_members(guild)).items():
            if mid == guild.owner:
                continue
            member = guild.get_member(mid)
            chan = guild.get_channel(data['channels']['narrator'])
            await chan.send(
                f"{member.mention}\nAll muses have been submitted.  It's time to write your story.  Your muse has been sent"
                " a mysterious application known as HiddenBytes from an unknown email address.  Your"
                " muse could have chosen to ignore the message, but where's the fun in that.  Once"
                " the application is downloaded, a window appears showing a chat client.  Your muse has"
                " one pending message from a mysterious user.  It contains a single message: a username.")
            await chan.send("To send a message request to a user, use `> dm request <username>`.")

            dm_category = guild.get_channel((await self.config.guild(guild).categories())['dms'])
            dm_chan = await guild.create_text_channel(name=f'{data["player"]["acronym"]}-\N{FULL BLOCK}\N{FULL BLOCK}',
                                                      category=dm_category,
                                                      overwrites={
                                                          member: PermissionOverwrite(read_messages=True)
                                                      })
            webhook = await dm_chan.create_webhook(name="Unknown User")
            await webhook.send(
                content="\N{FULL BLOCK}\N{FULL BLOCK}: " + shuffled[players.index(data['player']['handle'])],
                username="\N{FULL BLOCK}" * 10,
                avatar_url="https://upload.wikimedia.org/wikipedia/commons/thumb/4/49/A_black_image.jpg/1600px-A_black_image.jpg?20201103073518",
            )

            await chan.send("For some worldbuilding, here is a handful of people your muse may have heard of:")
            for blurb in blurbs[data['player']['species']]:
                await chan.send("> " + blurb)
