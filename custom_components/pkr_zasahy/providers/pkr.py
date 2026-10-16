"""Central Bohemian portal provider."""

from ..parser import parse_zasahy
from .base import async_fetch


class PkrProvider:
    supports_period_history = False
    name = "pkr"
    manufacturer = "Středočeský kraj"
    model = "Portál krizového řízení – zásahy JPO"
    history_start = None

    def __init__(self, session, url, executor):
        self.session = session
        self.url = url
        self.executor = executor

    async def async_fetch_incidents(self, now):
        html = await async_fetch(self.session, self.url)
        return await self.executor(parse_zasahy, html)

    async def async_fetch_period_history(self, now, recent):
        # The source table cannot establish complete month/year counts.
        return None
