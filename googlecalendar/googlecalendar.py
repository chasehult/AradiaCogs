import aiohttp
import asyncio
import datetime
import discord
import logging
import os.path
import pickle
import pytz
import re
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build
from redbot.core import Config, checks, commands, modlog
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box, inline, pagify
from urllib.parse import quote_plus

logger = logging.getLogger('red.misc-cogs.googlecalendar')

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

SECRET = {
    "client_id": None,
    "project_id": None,
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": None,
    "redirect_uris": [
        "urn:ietf:wg:oauth:2.0:oob",
        "http://localhost"
    ]
}

CALENDAR_URL = "https://www.googleapis.com/calendar/v3/calendars/{cid}/events?key={key}&timeMin={timeMin}&singleEvents=true&orderBy=startTime"


def discordify_format(desc):
    desc = re.sub(r"\*", r"\*", desc)
    desc = re.sub(r"_", r"\_", desc)
    desc = re.sub(r"</?(?:b|strong)>", "**", desc)
    desc = re.sub(r"</?(?:i|em)>", "*", desc)
    desc = re.sub(r"</?(?:u|ul)>", "__", desc)
    return desc


def humanize_delta(total_seconds):
    y, tsecs = divmod(total_seconds, 60 * 60 * 24 * 365)
    d, tsecs = divmod(tsecs, 60 * 60 * 24)
    h, tsecs = divmod(tsecs, 60 * 60)
    m, s = divmod(tsecs, 60)
    o = []
    if y: o.append("{} year".format(y) + ("s" if y > 1 else ''))
    if d: o.append("{} day".format(d) + ("s" if d > 1 else ''))
    if h: o.append("{} hour".format(h) + ("s" if h > 1 else ''))
    if m: o.append("{} minute".format(m) + ("s" if m > 1 else ''))
    if s: o.append("{} second".format(s) + ("s" if s > 1 else ''))
    return ", ".join(o)


class CalEvent:
    def __init__(self, data):
        self.data = data

        self.summary = data['summary']
        self.time = None
        if 'dateTime' in data['start']:
            self.time = datetime.datetime.fromisoformat(
                data['start']['dateTime']).astimezone(pytz.utc).replace(
                tzinfo=None)
        elif 'date' in data['start']:
            self.time = datetime.datetime.fromisoformat(data['start']['date'])
        self.description = data.get('description', '')

    def to_embed(self):
        diffsecs = int((self.time - datetime.datetime.now()).total_seconds())
        embed = discord.Embed()
        embed.title = self.summary
        embed.description = discordify_format(self.description)
        embed.set_footer(
            text="In {} from now.".format(humanize_delta(diffsecs)))

        return embed

    def is_valid(self):
        return self.time > datetime.datetime.now()


class GoogleCalendar(commands.Cog):
    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.config = Config.get_conf(self, identifier=90097334737042)
        self.config.register_guild(calendars={})
        self.config.register_global(auth=None)

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        data = "No data is stored for user with ID {}.\n".format(user_id)
        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data.

        No personal data is stored in this cog.
        """
        return

    @commands.group(aliases=['gcal'], invoke_without_command=True)
    async def googlecalendar(self, ctx, name, max_events: int = 5):
        """Posts upcoming Google calendar events."""
        if max_events > 20:
            await ctx.send("`max_events` must be less than 20.")
            return

        keys = await self.bot.get_shared_api_tokens("google")
        api_key = keys.get("api_key")
        if api_key is None:
            await ctx.send(("Please set your api key with `{0.prefix}set"
                            " api google api_key <APIKEY>`.").format(ctx))
            return

        auth = pickle.loads(bytes(await self.config.auth()))
        if auth is None:
            await ctx.send(
                "Authentification failed.  Please run `{0.prefix}googlecalendar authenticate`.")
            return

        if auth.expiry > datetime.datetime.now():
            auth.refresh(Request())
            await self.config.auth.set([b for b in pickle.dumps(auth)])

        cid = (await self.config.guild(ctx.guild).calendars()).get(name)
        if cid is None:
            await ctx.send("There is no calendar with that name.")
            return

        headers = {"Authorization": "Bearer {}".format(auth.token)}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    CALENDAR_URL.format(
                        cid=cid,
                        key=api_key,
                        timeMin=datetime.datetime.now().replace(
                            microsecond=0).isoformat() + "Z"),
                    headers=headers) as response:
                raw_data = await response.json()

        if 'error' in raw_data:
            await ctx.send((
                               "Error authenticating.  Ask the bot owner to run `{0.prefix}googlecalendar"
                               " authenticate` again.  Check your logs for more details.").format(
                ctx))
            logger.error(str(raw_data))
            return
        events = [CalEvent(i) for i in raw_data['items']]
        events = sorted([e for e in events if e.is_valid()],
                        key=lambda e: e.time)[:max_events]
        async with ctx.typing():
            for event in events:
                await ctx.send(embed=event.to_embed())
        if not events:
            await ctx.send("There are no future events in this calendar.")

    @googlecalendar.command()
    async def add(self, ctx, name, id):
        """Adds a Google calendar."""
        async with self.config.guild(ctx.guild).calendars() as cs:
            if name in cs:
                await ctx.send(
                    inline("A calendar with that name already exists."))
                return
            cs[name] = quote_plus(id)
        await ctx.tick()

    @googlecalendar.command(aliases=['rm', 'delete', 'dl'])
    async def remove(self, ctx, name):
        """Removes a Google calendar."""
        async with self.config.guild(ctx.guild).calendars() as cs:
            if name not in cs:
                await ctx.send(inline("No calendar with that name exists."))
                return
            del cs[name]
        await ctx.tick()

    @googlecalendar.command(name="list")
    async def gcal_list(self, ctx):
        """Lists current Google calendars."""
        cals = "\n".join(await self.config.guild(ctx.guild).calendars())
        for page in pagify(cals):
            await ctx.send(box(page))
        if not cals:
            await ctx.send("You have no calendars set up.")

    @googlecalendar.command()
    # @checks.is_owner()
    async def authenticate(self, ctx):
        """Create an authentication token (Needed before first run)."""
        installed = {**SECRET,
                     **(await self.bot.get_shared_api_tokens("google"))}

        if None in (installed['client_id'], installed['client_secret'],
                    installed['project_id']):
            await ctx.send((
                               "API key not set up.  Use `{0.prefix}set api google project_id <PROJECTID>"
                               " client_id <CLIENTID> client_secret <CLIENTSECRET>`").format(
                ctx))
            return

        flow = InstalledAppFlow.from_client_config(
            {'installed': installed},
            SCOPES,
            redirect_uri='urn:ietf:wg:oauth:2.0:oob')
        auth_url, _ = flow.authorization_url(prompt='consent')
        await ctx.send(
            "Please authenticate here and then send the key in chat.\n" + auth_url)
        msg = await self.bot.wait_for('message', check=lambda
            m: m.author == ctx.author and m.channel == ctx.channel)
        try:
            flow.fetch_token(code=msg.content)
            await self.config.auth.set(
                [b for b in pickle.dumps(flow.credentials)])
            await ctx.tick()
        except Exception as e:
            logger.exception("Error loading credentials.", exc_info=1)
            await ctx.send(
                "Invalid token.  Try running `{0.prefix}googlecalendar authenticate` again".format(
                    ctx))
