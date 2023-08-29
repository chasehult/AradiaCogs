from redbot.core import Config, commands


class LandMixin:
    config: Config

    @commands.group(hidden=True, invoke_without_command=True)
    async def land(self, ctx):
        pass

    @land.command(hidden=True)
    async def rename(self, ctx, *, name: str):
        land_chan = ctx.guild.get_channel((await self.config.member(ctx.author).channels())['land'])
        await land_chan.edit(name=name)
        await ctx.send("It is done.")

    @land.command(hidden=True)
    async def travel(self, ctx, user: str):
        players = {}
        for mid, data in (await self.config.all_members(ctx.guild)).items():
            if mid == ctx.guild.owner:
                continue
            player = data['player']
            players[player['handle']] = data['channels']['land']
        if user not in players:
            return await ctx.send(f"User `{user}` not found.  Check your capitalization and try again.")
        land_chan = ctx.guild.get_channel(players[user])
        await land_chan.set_permissions(ctx.author, read_messages=True)
        await ctx.send(f"You can now see {user}'s land.")

    @land.command(hidden=True)
    async def leave(self, ctx, user: str):
        players = {}
        my_handle = None
        for mid, data in (await self.config.all_members(ctx.guild)).items():
            if mid == ctx.guild.owner:
                continue
            player = data['player']
            if mid == ctx.author.id:
                my_handle = player['handle']
            players[player['handle']] = {'cid': data['channels']['land'], 'mid': mid, 'client': data['player']['client']}
        if user not in players:
            return await ctx.send(f"User `{user}` not found.  Check your capitalization and try again.")
        elif players[user]['mid'] == ctx.author.id:
            return await ctx.send("You cannot stop seeing your own land.  You will always have access to this channel.")
        elif players[user]['mid'] == players[my_handle]['client']:
            return await ctx.send("You cannot stop seeing your client's land.  You will always have access to this channel.")
        land_chan = ctx.guild.get_channel(players[user]['cid'])
        await land_chan.set_permissions(ctx.author, read_messages=False)
        await ctx.send(f"You can no longer see {user}'s land.")
