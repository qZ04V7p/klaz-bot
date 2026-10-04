from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMIN_IDS: str = ""  # через запятую: "123,456"

    # SQLite — путь к файлу базы данных
    DB_PATH: str = "klaz_bot.db"

    SERVER_IP: str = "0.0.0.0"
    BASE_URL: str = "http://localhost:8080"
    PROXY_URL: str = ""  # socks5://user:pass@host:port

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def admin_ids_list(self) -> List[int]:
        if not self.ADMIN_IDS:
            return []
        return [int(i.strip()) for i in self.ADMIN_IDS.split(",") if i.strip()]

    @property
    def database_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.DB_PATH}"


settings = Settings()
