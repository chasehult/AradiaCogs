import json
import re
import discord.utils
import youtube_dl
import asyncio

from ply import lex
from redbot.core import checks, Config
from redbot.core import commands
from redbot.core.utils.chat_formatting import box, pagify, inline


class RepoInfo(commands.Cog):
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.config = Config.get_conf(self, identifier=23901770)


    @commands.command()
    async def repoinfo(self, ctx, repo_name):
        DLCOG = self.bot.get_cog("Downloader")
        if DLCOG is None:
            await ctx.send(inline("Downloader cog not loaded."))
            return
        repo = DLCOG._repo_manager.get_repo(repo_name)
        if repo is None:
            await ctx.send(box("Repo not found.\n\nAvaliable Repos:\n"+
                               "\n".join(DLCOG._repo_manager.get_all_repo_names())))
            return
        extensions = [i.name for i in repo.available_cogs]
        cogs = filter(lambda x: x.__module__.split(".")[0] in extensions,
                      self.bot.cogs.values())

        hs = await commands.help.HelpSettings.from_context(ctx)
        coms = [(
            cog.__cog_name__,
            await commands.help.RedHelpFormatter().get_cog_help_mapping(ctx, cog, hs)
        ) for cog in cogs]

        if not coms:
            await ctx.send(inline("There are no loaded cogs on the repo!"))
            return

        to_join = ["Commands for {}:\n".format(repo_name)]

        names = []
        for k, v in coms:
            names.extend(list(v.name for v in v.values()))

        max_width = max(discord.utils._string_width(name or "No Category:") for name in names)

        def width_maker(cmds):
            doc_max_width = 80 - max_width
            for nm, com in cmds:
                width_gap = discord.utils._string_width(nm) - len(nm)
                doc = com.format_shortdoc_for_context(ctx)
                if len(doc) > doc_max_width:
                    doc = doc[: doc_max_width - 3] + "..."
                yield nm, doc, max_width - width_gap

        for cog_name, data in coms:

            title = f"{cog_name}:" if cog_name else T_("No Category:")
            to_join.append(title)

            for name, doc, width in width_maker(sorted(data.items())):
                to_join.append(f"  {name:<{width}} {doc}")

        to_page = "\n".join(to_join)
        pages = [box(p) for p in pagify(to_page)]
        await commands.help.RedHelpFormatter().send_pages(ctx, pages, embed=False, help_settings=hs)
