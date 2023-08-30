import discord
from discord import CategoryChannel
from redbot.core import Config, checks, commands


class AdminMixin:
    config: Config

    @commands.group()
    @checks.admin()
    async def admin(self, ctx):
        pass

    @admin.command()
    async def setplayercount(self, ctx, players: int):
        await self.config.guild(ctx.guild).total_players.set(players)
        await ctx.tick()

    @admin.command()
    async def setcategories(self, ctx, narrators: CategoryChannel, dms: CategoryChannel, lands: CategoryChannel):
        await self.config.guild(ctx.guild).categories.set({
            'narrators': narrators.id,
            'dms': dms.id,
            'lands': lands.id})
        await ctx.tick()

    @admin.command()
    async def announce(self, ctx, *, announcement: str):
        for mid, data in (await self.config.all_members(ctx.guild)).items():
            member = ctx.guild.get_member(mid)
            chan = ctx.guild.get_channel(data['channels']['narrator'])
            await chan.send(announcement)

    @admin.command()
    async def announcesburb(self, ctx):
        for mid, data in (await self.config.all_members(ctx.guild)).items():
            member = ctx.guild.get_member(mid)
            chan = ctx.guild.get_channel(data['channels']['narrator'])
            await chan.send("Whether you know it or not, Sburb has begun.  Once you've gotten your hands on the file,"
                            " you can use `> sburb request <username>` to send a Sburb server request to someone.  This"
                            " will request for them to be your client, and for you to be their server.  To travel"
                            " across lands, use `> land travel <username>` to gain access to a user's land channel,"
                            " and `> land leave <username>` to remove access from yourself.  Please do not use these"
                            " commands unless you have a reason to in canon.")

    @admin.command()
    async def restart(self, ctx):
        await self.config.guild(ctx.guild).dms.clear()
        for mid in await self.config.all_members(ctx.guild):
            await self.config.member_from_ids(ctx.guild.id, mid).clear()
        await ctx.tick()

    @admin.command()
    async def setlurkrole(self, ctx, role: discord.Role):
        await self.config.guild(ctx.guild).lurk_role.set(role.id)
        await ctx.tick()
