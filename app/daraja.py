
import base64
import time
from datetime import datetime, timedelta, timezone

import httpx


SANDBOX_URL = "https://sandbox.safaricom.co.ke"
EAT = timezone(timedelta(hours=3))


def make_timestamp(now: datetime | None = None) -> str:
    return (now or datetime.now(EAT)).astimezone(EAT).strftime("%Y%m%d%H%M%S")


def build_password(shortcode: str, passkey: str, timestamp: str) -> str:
    return base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()


class DarajaError(Exception):
    """Raised when the Daraja API returns an error."""


class DarajaClient:
    def __init__(self,consumer_key: str,consumer_secret: str,shortcode: str, passkey: str, callback_url: str,mock: bool = False):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.shortcode = shortcode
        self.passkey = passkey
        self.callback_url = callback_url
        self.mock = mock

        self._token: str | None = None
        self._expires_at = 0.0

    async def _get_token(
        self,
        http: httpx.AsyncClient,
    ) -> str:
        # Reuse the token until a minute before it expires.
        if self._token and time.monotonic() < self._expires_at - 60:
            return self._token

        response = await http.get(
            f"{SANDBOX_URL}/oauth/v1/generate",
            params={"grant_type": "client_credentials"},
            auth=(self.consumer_key, self.consumer_secret),
        )

        if response.status_code != 200:
            raise DarajaError(
                f"Authentication failed ({response.status_code}). Check CONSUMER_KEY and CONSUMER_SECRET."
            )

        data = response.json()
        token = data.get("access_token")
        expires_in = int(data.get("expires_in", 3600))

        if not token:
            raise DarajaError("OAuth response did not contain a token")

        self._token = token
        self._expires_at = time.monotonic() + expires_in

        return token
