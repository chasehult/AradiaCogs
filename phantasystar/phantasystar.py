import re
from datetime import datetime
from io import BytesIO

import aiohttp
from bs4 import BeautifulSoup
from pytz import timezone
from redbot.core import commands
from redbot.core.utils.chat_formatting import humanize_timedelta, bold, inline, pagify

PST = timezone("America/Los_Angeles")


class PhantasyStar(commands.Cog):
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.b = None

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        data = "No data is stored for user with ID {}.\n".format(user_id)
        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data.

        No personal data is stored in this cog.
        """
        return

    @commands.command(aliases=["uq"])
    async def urgentquest(self, ctx, number: int = 4):
        if number > 10:
            await ctx.send("You can't see more than 10 events into the future.")
            return
        async with aiohttp.ClientSession() as session:
            async with session.get("https://rappy-burst.com/calendars/") as response:
                text = await response.read()

        cid = re.search(rb"rappy_calendar\('(\d+)'\)", text).group(1)
        soup = BeautifulSoup(text, 'html.parser')
        simcal = soup.find(attrs={'class': "simcal-calendar", 'data-calendar-id': cid})
        events = []
        for event in simcal.findAll(class_="simcal-event"):
            events.append({
                'name': event.strong.text,
                'start': datetime.fromisoformat(event.find(itemprop="startDate")['content']).astimezone(PST),
                'end': datetime.fromisoformat(event.find(itemprop="endDate")['content']).astimezone(PST)
            })
        now = datetime.now(PST)
        events = sorted((e for e in events if e['start'] > now), key=lambda x: x['start'])[:number]
        o = ""
        for event in events:
            duration = '{} - {} PST'.format(event['start'].strftime('%I:%M %p'), event['end'].strftime('%I:%M %p'))
            o += (f"{bold(event['name'])}\n"
                  f"{inline(duration)}\n"
                  f"in {humanize_timedelta(timedelta=event['start'] - now)}\n\n")
        for page in pagify(o):
            await ctx.send(page)
