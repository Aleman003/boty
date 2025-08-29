import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    PORT: int = int(os.getenv("PORT", "3000"))

    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "mi_verify_2025")
    VERIFY_SIGNATURE: bool = bool(int(os.getenv("VERIFY_SIGNATURE", "0")))
    APP_SECRET: str = os.getenv("APP_SECRET", "")

    GRAPH_VER: str = os.getenv("GRAPH_VER", "v20.0")
    WHATSAPP_PHONE_ID: str = os.getenv("WHATSAPP_PHONE_ID", "")
    WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN", "")

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    DB_PATH: str = os.getenv("DB_PATH", "agent_api.db")

settings = Settings()
