"""Select a source without changing existing config entries."""

from ..const import (
    CONF_DISTRICT,
    CONF_PROVIDER,
    CONF_REGION,
    CONF_URL,
    DEFAULT_REGION,
    PROVIDER_FIREBRNO,
    PROVIDER_PKR,
)
from ..models import ParseError
from .base import IncidentProvider
from .firebrno import FireBrnoProvider
from .pkr import PkrProvider


def create_provider(hass, session, data) -> IncidentProvider:
    provider = data.get(CONF_PROVIDER, PROVIDER_PKR)
    if provider == PROVIDER_PKR:
        return PkrProvider(session, data[CONF_URL], hass.async_add_executor_job)
    if provider == PROVIDER_FIREBRNO:
        return FireBrnoProvider(
            session,
            int(data.get(CONF_REGION, DEFAULT_REGION)),
            int(data[CONF_DISTRICT]) if data.get(CONF_DISTRICT) else None,
        )
    raise ParseError(f"Unknown incident provider: {provider}")
