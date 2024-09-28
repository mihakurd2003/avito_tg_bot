from typing import List, Dict

import aiohttp

AVITO_ITEMS_URL = "https://api.avito.ru/core/v1/items"
AVITO_CALL_STATS_URL_TEMPLATE = "https://api.avito.ru/core/v1/accounts/{user_id}/calls/stats/"


class AvitoAPI:
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {self.token}'
        }
        self.session = aiohttp.ClientSession(headers=self.headers)

    async def get_user_account(self) -> Dict:
        url = "https://api.avito.ru/core/v1/accounts/self"
        async with self.session.get(url) as response:
            response.raise_for_status()
            return await response.json()

    async def get_items(self, account_id: str) -> List[Dict]:
        params = {
            'account_id': account_id,
            'per_page': 100
        }
        async with self.session.get(AVITO_ITEMS_URL, params=params) as response:
            response.raise_for_status()
            data = await response.json()
            return data.get('resources', [])

    async def get_call_stats(self, account_id: str, item_ids: list) -> Dict:
        url = AVITO_CALL_STATS_URL_TEMPLATE.format(user_id=account_id)
        body = {
            'dateFrom': '2024-01-20',
            'dateTo': '2024-09-27',
            'itemIds': item_ids,
        }
        headers = {'content-type': 'application/json'}
        async with self.session.post(url, headers=headers, json=body) as response:
            response.raise_for_status()
            return await response.json()

    async def close(self):
        await self.session.close()