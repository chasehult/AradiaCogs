import asyncio
import discord.utils
import json
import re
from collections import namedtuple
from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import box, inline, pagify

EmbedField = namedtuple("EmbedField", "name value inline")


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
            await ctx.send(box("Repo not found.\n\nAvaliable Repos:\n" +
                               "\n".join(
                                   DLCOG._repo_manager.get_all_repo_names())))
            return
        extensions = [i.name for i in repo.available_cogs]
        cogs = filter(lambda x: x.__module__.split(".")[0] in extensions,
                      self.bot.cogs.values())

        hs = await commands.help.HelpSettings.from_context(ctx)
        rhf = commands.help.RedHelpFormatter()
        coms = [(
            cog.__cog_name__,
            await commands.help.RedHelpFormatter().get_cog_help_mapping(ctx,
                                                                        cog, hs)
        ) for cog in cogs]

        if not coms:
            await ctx.send(inline("There are no loaded cogs on the repo!"))
            return

        if await ctx.embed_requested():

            emb = {"embed": {"title": "", "description": ""},
                   "footer": {"text": ""}, "fields": []}

            for cog_name, data in coms:

                if cog_name:
                    title = f"**__{cog_name}:__**"
                else:
                    title = "**__No Category:__**"

                def shorten_line(a_line: str) -> str:
                    if len(a_line) < 70:
                        return a_line
                    return a_line[:67] + "..."

                cog_text = "\n".join(
                    shorten_line(
                        f"**{name}** {command.format_shortdoc_for_context(ctx)}")
                    for name, command in sorted(data.items())
                )

                for i, page in enumerate(
                        pagify(cog_text, page_length=1000, shorten_by=0)):
                    title = title if i < 1 else f"{title} (continued)"
                    field = EmbedField(title, page, False)
                    emb["fields"].append(field)

            await rhf.make_and_send_embeds(ctx, emb, help_settings=hs)

        else:
            to_join = ["Commands for {}:\n".format(repo_name)]

            names = []
            for k, v in coms:
                names.extend(list(v.name for v in v.values()))

            max_width = max(
                discord.utils._string_width(name or "No Category:") for name in
                names)

            def width_maker(cmds):
                doc_max_width = 80 - max_width
                for nm, com in cmds:
                    width_gap = discord.utils._string_width(nm) - len(nm)
                    doc = com.format_shortdoc_for_context(ctx)
                    if len(doc) > doc_max_width:
                        doc = doc[: doc_max_width - 3] + "..."
                    yield nm, doc, max_width - width_gap

            for cog_name, data in coms:

                title = f"{cog_name}:" if cog_name else "No Category:"
                to_join.append(title)

                for name, doc, width in width_maker(sorted(data.items())):
                    to_join.append(f"  {name:<{width}} {doc}")

            to_page = "\n".join(to_join)
            pages = [box(p) for p in pagify(to_page)]
            await rhf.send_pages(ctx, pages, embed=False, help_settings=hs)
