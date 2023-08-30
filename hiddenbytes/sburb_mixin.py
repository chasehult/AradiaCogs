from redbot.core import Config, commands


class SburbMixin:
    config: Config

    @commands.group(hidden=True, invoke_without_command=True)
    async def sburb(self, ctx):
        pass

    @sburb.command(name="request", hidden=True)
    async def sburb_request(self, ctx, user: str):
        if (await self.config.member(ctx.author).player())['client'] is not None:
            return await ctx.send("You already have a client player.  You cannot add another.")
        players = {}
        from_handle = None
        for mid, data in (await self.config.all_members(ctx.guild)).items():
            if not data['player'] or not ctx.guild.get_member(mid):
                continue
            player = data['player']
            if mid == ctx.author.id:
                from_handle = player['handle']
            players[player['handle']] = {'mid': mid, 'narr_chan': data['channels']['narrator']}
        if user not in players:
            return await ctx.send(f"User `{user}` not found.  Check your capitalization and try again.")
        to_player = players[user]
        nar_chan = ctx.guild.get_channel(to_player['narr_chan'])

        async with self.config.member(ctx.author).sburb_requests() as sbreqs:
            if to_player['mid'] not in sbreqs:
                sbreqs.append(to_player['mid'])

        await nar_chan.send(f"Your muse has received a Sburb Server request from `{from_handle}`.  Use"
                            f" `> sburb accept {from_handle}` to become their client.")
        await ctx.send("The Sburb request has been sent.")

    @sburb.command(name="accept", hidden=True)
    async def sburb_accept(self, ctx, user: str):
        players = {}
        clients = []
        my_handle = None
        for mid, data in (await self.config.all_members(ctx.guild)).items():
            if not data['player'] or not ctx.guild.get_member(mid):
                continue
            player = data['player']
            if mid == ctx.author.id:
                my_handle = player['handle']
            clients.append(player['client'])
            players[player['handle']] = {'mid': mid, 'narr_chan': data['channels']['narrator'],
                                         'reqs': data['sburb_requests'], 'land_chan': data['channels']['land']}
        if user not in players or ctx.author.id not in players[user]['reqs']:
            return await ctx.send(f"You do not have a Sburb request from user `{user}`."
                                  f"  Check your capitalization and try again.")
        elif ctx.author.id in clients:
            return await ctx.send("You already have a server player.  You may not accept multiple requests.")
        client = players[user]
        client_member = ctx.guild.get_member(client['mid'])
        async with self.config.member(client_member).player() as player:
            player['client'] = ctx.author.id

        await ctx.guild.get_channel(players[my_handle]['land_chan']).set_permissions(client_member, read_messages=True)
        await ctx.guild.get_channel(client['narr_chan']).send(f"{my_handle} has accepted your Sburb request.")
