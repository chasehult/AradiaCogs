import urllib.parse

import aiohttp
import hmac
import base64
import time
import uuid

from typing import Dict, Optional, Literal

from aiohttp.web_exceptions import HTTPInternalServerError, HTTPError


class NoAuthKey(Exception):
    pass


class PapagoTranslate:
    def __init__(self, client_id, client_secret):
        self.headers = {
            'X-Naver-Client-Id': client_id,
            "X-Naver-Client-Secret": client_secret
        }
        self.session = aiohttp.ClientSession()

    async def close(self):
        await self.session.close()

    async def translate(self, source: str, target: str, text: str, honorific: bool = False) -> Dict[str, str]:
        url = 'https://openapi.naver.com/v1/papago/n2mt'
        if any(v is None for v in self.headers.values()):
            raise NoAuthKey()

        response = await self.session.post(url, data=urllib.parse.urlencode({
            'source': source,
            'target': target,
            'text': text,
        }).encode("utf-8"))

        if response.status != 200:
            raise HTTPError(reason=f'{response.status}: request aborted\n\n{await response.json()}')
        content = await response.json()
        return content['translatedText']
