from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

CONFIG_DIR = Path(__file__).resolve().parent
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_CONFIG_FILE = CONFIG_DIR / "config.yaml"
CONFIG_ENV_VAR = "APP_CONFIG_FILE"


@dataclass(frozen=True)
class AppConfig:
    name: str
    version: str
    log_level: str


@dataclass(frozen=True)
class DatabaseConfig:
    path: Path
    echo: bool

    def build_database_url(self) -> str:
        return f"sqlite:///{self.path}"


@dataclass(frozen=True)
class BinanceConfig:
    api_key: Optional[str]
    api_secret: Optional[str]
    testnet: bool
    binance_url: str
    websocket_url: str

@dataclass(frozen=True)
class Settings:
    app: AppConfig
    database: DatabaseConfig
    binance: BinanceConfig

    @property
    def database_url(self) -> str:
        return self.database.build_database_url()


def load_config(config_path: Optional[Path] = None) -> Settings:
    env_path = os.environ.get(CONFIG_ENV_VAR)
    if env_path:
        path = Path(env_path).expanduser().resolve()
    else:
        path = (config_path or DEFAULT_CONFIG_FILE).resolve()

    if not path.exists():
        fallback = (CONFIG_DIR / "config.yaml.example").resolve()
        if fallback.exists():
            path = fallback
        else:
            raise FileNotFoundError(f"Configuration file not found: {path}")

    with path.open("r", encoding="utf-8") as fp:
        raw = yaml.safe_load(fp) or {}

    app_cfg = raw.get("app", {})
    db_cfg = raw.get("database", {})
    binance_cfg = raw.get("binance", {})

    raw_db_path = Path(db_cfg.get("path", "data/grid_trading.db"))
    if raw_db_path.is_absolute():
        db_path = raw_db_path
    else:
        db_path = (path.parent.parent / raw_db_path).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    return Settings(
        app=AppConfig(
            name=app_cfg.get("name", "Binance Grid Trading Backend"),
            version=app_cfg.get("version", "1.0.0"),
            log_level=app_cfg.get("log_level", "INFO"),
        ),
        database=DatabaseConfig(
            path=db_path,
            echo=bool(db_cfg.get("echo", False)),
        ),
        binance=BinanceConfig(
            api_key=binance_cfg.get("api_key"),
            api_secret=binance_cfg.get("api_secret"),
            testnet=bool(binance_cfg.get("testnet", True)),
            binance_url=binance_cfg.get("binance_url", "https://testnet.binance.vision"),
            websocket_url=binance_cfg.get("websocket_url", "wss://testnet.binance.vision"),
        ),
    )


settings = load_config()
