import logging
import random
from io import BytesIO

from redbot.core import commands

logger = logging.getLogger('red.misc-cogs.grantrole')


class Pick(commands.Cog):
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
    async def pick(self, ctx, number: int, *, from_list):
        """Pick items out of a group.

        Usage:
        [p]pick 1 one two three
        [p]pick 2 item one, item two, item three
        [p]pick 2 "item one" "item two" "item three"
        [p]pick 4 in #voice-channel
        [p]pick 3 in @Role
        """
        if from_list.startswith("in "):
            in_syntax = True
            group = from_list[3:]
            try:
                role = await commands.RoleConverter().convert(ctx, group)
                pickfrom = [m.mention for m in ctx.guild.members if role in m.roles]
            except commands.CommandError:
                try:
                    vc = await commands.VoiceChannelConverter().convert(ctx, group)
                    pickfrom = [m.mention for m in vc.members]
                except commands.CommandError:
                    await ctx.send("Invalid role or voice channel.")
                    return
        else:
            in_syntax = False
            if '"' in from_list:
                pickfrom = [e.strip() for e in from_list.replace('",', '"').split('"') if e.strip()]
            elif "," in from_list:
                pickfrom = [e.strip() for e in from_list.split(",")]
            else:
                pickfrom = from_list.split(" ")

        if number > len(pickfrom):
            await ctx.send(f"There aren't enough {'members' if in_syntax else 'items'} to pick from.")
            return

        random.shuffle(pickfrom)

        await ctx.send(", ".join(pickfrom[:number]))
