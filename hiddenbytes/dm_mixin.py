from typing import Optional

import discord
from discord import PermissionOverwrite
from redbot.core import Config, commands


class DMMixin:
    config: Config

    @commands.group(hidden=True, invoke_without_command=True)
    async def dm(self, ctx):
        pass

    @dm.command(hidden=True)
    async def request(self, ctx, user: str):
        players = {}
        from_handle = None
        for mid, data in (await self.config.all_members(ctx.guild)).items():
            if mid == ctx.guild.owner:
                continue
            player = data['player']
            if mid == ctx.author.id:
                from_handle = player['handle']
            players[player['handle']] = {'mid': mid, 'narr_chan': data['channels']['narrator']}
        if user not in players:
            return await ctx.send(f"User `{user}` not found.  Check your capitalization and try again.")
        to_player = players[user]
        nar_chan = ctx.guild.get_channel(to_player['narr_chan'])

        async with self.config.member(ctx.author).dm_requests() as dmreqs:
            if to_player['mid'] not in dmreqs:
                dmreqs.append(to_player['mid'])

        await nar_chan.send(f"Your muse has received a DM request from `{from_handle}`.  Use"
                            f" `> dm accept {from_handle}` to accept.")
        await ctx.send("The DM request has been sent.")

    @dm.command(hidden=True)
    async def accept(self, ctx, user: str):
        players = {}
        my_handle = None
        for mid, data in (await self.config.all_members(ctx.guild)).items():
            if mid == ctx.guild.owner:
                continue
            player = data['player']
            if mid == ctx.author.id:
                my_handle = player['handle']
            players[player['handle']] = {'mid': mid,
                                         'narr_chan': data['channels']['narrator'],
                                         'reqs': data['dm_requests'],
                                         'acronym': player['acronym']}
        if user not in players or ctx.author.id not in players[user]['reqs']:
            return await ctx.send(f"You do not have a DM request from user `{user}`."
                                  f"  Check your capitalization and try again.")
        from_player = players[user]
        from_member = ctx.guild.get_member(from_player['mid'])
        if (dm_chan := await self.get_dm(ctx.guild, ctx.author.id, from_player['mid'])) \
                and (await self.config.guild(ctx.guild).dms()).get(str(sorted([ctx.author.id, from_player['mid']])))[
            'open']:
            return await ctx.send(f"You already have an existing DM with this user: {dm_chan.mention}")

        async with self.config.member(from_member).dm_requests() as dmreqs:
            dmreqs.remove(ctx.author.id)

        if dm_chan is None:
            dm_category = ctx.guild.get_channel((await self.config.guild(ctx.guild).categories())['dms'])
            dm_chan = await ctx.guild.create_text_channel(
                name=f'{from_player["acronym"]}-{players[my_handle]["acronym"]}', category=dm_category)
            async with self.config.guild(ctx.guild).dms() as dms:
                dms[str(sorted([ctx.author.id, from_player['mid']]))] = {'channel': dm_chan.id, 'open': True}
        await dm_chan.edit(overwrites={
            ctx.author: PermissionOverwrite(read_messages=True, send_messages=True),
            from_member: PermissionOverwrite(read_messages=True, send_messages=True)
        })
        async with self.config.guild(ctx.guild).dms() as dms:
            dms[str(sorted([ctx.author.id, from_player['mid']]))]['open'] = True
        await dm_chan.send(f"\\* {user} has begun private messaging {my_handle}.")
        await ctx.send(f"The DM request has been accepted.  Use `> dm close {user}` to close it at any time.")

    @dm.command(hidden=True)
    async def close(self, ctx, user: str):
        players = {}
        my_handle = None
        for mid, data in (await self.config.all_members(ctx.guild)).items():
            if mid == ctx.guild.owner:
                continue
            player = data['player']
            if mid == ctx.author.id:
                my_handle = player['handle']
            players[player['handle']] = {'mid': mid,
                                         'narr_chan': data['channels']['narrator']}
        if user not in players \
                or (not (dm_chan := await self.get_dm(ctx.guild, ctx.author.id, players[user]['mid']))
                    and
                    not (await self.config.guild(ctx.guild).dms()).get(str(sorted([ctx.author.id, players[user]['mid']])))[
                        'open']):
            return await ctx.send(f"You do not have an open DM with user `{user}`."
                                  f"  Check your capitalization and try again.")
        await dm_chan.send(f"\\* {my_handle} has ceased private messaging {user}.")
        from_member = ctx.guild.get_member(players[user]['mid'])
        await dm_chan.edit(overwrites={
            ctx.author: PermissionOverwrite(read_messages=True, send_messages=False),
            from_member: PermissionOverwrite(read_messages=True, send_messages=False)
        })
        async with self.config.guild(ctx.guild).dms() as dms:
            dms[str(sorted([ctx.author.id, players[user]['mid']]))]['open'] = False
        await ctx.guild.get_channel(players[my_handle]['narr_chan']).send(f"The DM has been closed."
                                                                          f"  Use `> dm request {user}`"
                                                                          f" to request to start again.")
        await ctx.guild.get_channel(players[user]['narr_chan']).send(f"Your DM with {my_handle} has been closed."
                                                                     f"  Use `> dm request {user}`"
                                                                     f" to request to start again.")

    async def get_dm(self, guild: discord.Guild, player1: int, player2: int) -> Optional[discord.TextChannel]:
        chan_id = (await self.config.guild(guild).dms()).get(str(sorted([player1, player2])))
        if chan_id is None:
            return None
        return guild.get_channel(chan_id['channel'])
