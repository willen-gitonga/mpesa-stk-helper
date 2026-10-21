import re
import hmac
import httpx
from fastapi import FastAPI, HTTPException
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.daraja import DarajaClient, DarajaError

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    mock_mode: bool = True
    consumer_key: str = ""
    consumer_secret: str = ""
    shortcode: str = "174379"
    passkey: str = ""
    public_base_url: str = ""
    callback_secret: str = "change-me"


def normalize_phone(raw: str) -> str:
    """Turn 0712345678 or +254712345678 into 254712345678."""
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("0"):
        digits = "254" + digits[1:]
    if not re.fullmatch(r"254[71]\d{8}", digits):
        raise ValueError("Use a Kenyan mobile number such as 0712345678 or 254712345678")
    return digits


class StkPushRequest(BaseModel):
    phone_number: str = Field(examples=["0712345678"])
    amount: int = Field(ge=1, description="Whole Kenyan shillings")

    @field_validator("phone_number")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return normalize_phone(value)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    if not settings.mock_mode:
        required = ("consumer_key", "consumer_secret", "passkey", "public_base_url")
        missing = [name.upper() for name in required if not getattr(settings, name)]
        if missing:
            raise RuntimeError(f"MOCK_MODE is false but these settings are empty: {', '.join(missing)}")

    daraja = DarajaClient(
        settings.consumer_key,
        settings.consumer_secret,
        settings.shortcode,
        settings.passkey,
        callback_url=f"{settings.public_base_url.rstrip('/')}/callback/{settings.callback_secret}",
        mock=settings.mock_mode,
    )
    payments: dict[str, dict] = {}

    app = FastAPI(title="M-Pesa STK Push Helper", version="0.1.0")

    @app.post("/stk-push", status_code=202, summary="Send a payment prompt to a phone")
    async def stk_push(body: StkPushRequest) -> dict:
        try:
            data = await daraja.stk_push(body.phone_number, body.amount)
        except (DarajaError, httpx.HTTPError) as exc:
            raise HTTPException(status_code=502, detail=f"Daraja error: {exc}") from exc
        checkout_id = data["CheckoutRequestID"]
        payments[checkout_id] = {
            "checkout_request_id": checkout_id,
            "phone_number": body.phone_number,
            "amount": body.amount,
            "status": "pending",
            "result_desc": None,
            "receipt_number": None,
        }
        return payments[checkout_id]

    @app.get("/payments/{checkout_request_id}", summary="Get a payment's status")
    async def get_payment(checkout_request_id: str) -> dict:
        if checkout_request_id not in payments:
            raise HTTPException(status_code=404, detail="Payment not found")
        return payments[checkout_request_id]

    @app.post("/callback/{secret}", summary="Receive the payment result from Safaricom")
    async def callback(secret: str, payload: dict) -> dict:
        # Daraja callbacks aren't signed, so the URL contains a secret only we know.
        if not hmac.compare_digest(secret.encode(), settings.callback_secret.encode()):
            raise HTTPException(status_code=404, detail="Not Found")
        try:
            result = payload["Body"]["stkCallback"]
            checkout_id = result["CheckoutRequestID"]
            result_code = int(result["ResultCode"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Not an STK Push callback") from exc

        payment = payments.get(checkout_id)
        # Ignore callbacks for unknown payments and duplicates for finished ones.
        if payment and payment["status"] == "pending":
            items = result.get("CallbackMetadata", {}).get("Item", [])
            metadata = {item["Name"]: item.get("Value") for item in items}
            payment["status"] = "completed" if result_code == 0 else "failed"
            payment["result_desc"] = result.get("ResultDesc")
            payment["receipt_number"] = metadata.get("MpesaReceiptNumber")

        # Safaricom expects this acknowledgement.
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    return app


app = create_app()
