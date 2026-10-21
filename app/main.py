import re
from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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


app = FastAPI(
    title="Daraja STK Push Helper",
    version="0.1.0",
)


@app.get("/health")
async def health():
    return {"status": "ok"}
