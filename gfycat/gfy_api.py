import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal

from aiohttp import ClientResponseError, ClientSession
from redbot.core.bot import Red
from tsutils.errors import BadAPIKeyException, NoAPIKeyException

logger = logging.getLogger('red.aradiacogs.gfycat')


class GfycatAPI:
    def __init__(self, bot: Red, session: ClientSession):
        self.bot = bot

        self.session = session

        self.access_token = None
        self.expires = datetime.min

    async def ensure_login(self) -> None:
        """Ensure that the access_token is recent and valid"""
        keys = await self.bot.get_shared_api_tokens("gfycat")
        if not ("client_id" in keys and "client_secret" in keys):
            raise NoAPIKeyException((await self.bot.get_valid_prefixes())[0]
                                    + f"set api gfycat client_id <ID> client_secret <SECRET>")
        if self.access_token is None or self.expires < datetime.now():
            try:
                data = await self.do_api_call('POST', 'oauth/token',
                                              {'grant_type': "client_credentials",
                                               'client_id': keys['client_id'],
                                               'client_secret': keys['client_secret']})
            except ClientResponseError as e:
                if e.status == 500:
                    raise BadAPIKeyException((await self.bot.get_valid_prefixes())[0]
                                             + f"set api gfycat client_id <ID> client_secret <SECRET>")
                raise
            self.access_token = data['access_token']
            self.expires = datetime.now() + timedelta(seconds=data['expires_in'] - 30)  # 30 second buffer to be safe

    async def do_api_call(self, method: Literal['GET', 'POST'], service: str, data: Dict[str, Any] = None):
        """Make a single API call to https://api.gfycat.com/v1/"""
        endpoint = "https://api.gfycat.com/v1/"
        if data is None:
            data = {}

        if method == "GET":
            async with self.session.get(endpoint + service, headers=await self.get_headers(), params=data) as resp:
                resp.raise_for_status()
                data = await resp.json()
        elif method == "POST":
            async with self.session.post(endpoint + service, json=data) as resp:
                resp.raise_for_status()
                data = await resp.json()
        else:
            raise ValueError("HTTP Method must be GET or POST.")
        return data

    async def get_headers(self) -> Dict[str, str]:
        """Return headers for a GET request to the API"""
        await self.ensure_login()
        return {'Authorization': f'Bearer {self.access_token}'}

    async def get_gyfs(self, number: int, tag: str) -> List[str]:
        data = await self.do_api_call('GET', 'gfycats/search',
                                      {'search_text': tag,
                                       'count': 1000})
        gyfs = data['gfycats']
        random.shuffle(gyfs)
        gyfs = gyfs[:number]
        return ['https://gfycat.com/' + gyf['gfyId'] for gyf in gyfs]
