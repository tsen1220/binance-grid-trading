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
    log_dir: Path


@dataclass(frozen=True)
class MySQLConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str
    echo: bool

    def build_database_url(self) -> str:
        return (
            f"mysql+mysqlconnector://{self.user}:{self.password}@"
            f"{self.host}:{self.port}/{self.database}?charset={self.charset}"
        )


@dataclass(frozen=True)
class TestingConfig:
    database_url: Optional[str] = None


@dataclass(frozen=True)
class Settings:
    app: AppConfig
    mysql: MySQLConfig
    testing: TestingConfig

    @property
    def database_url(self) -> str:
        return self.testing.database_url or self.mysql.build_database_url()


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
    mysql_cfg = raw.get("mysql", {})
    testing_cfg = raw.get("testing", {})

    raw_log_dir = Path(app_cfg.get("log_dir", "logs"))
    if raw_log_dir.is_absolute():
        log_dir = raw_log_dir
    else:
        log_dir = (path.parent / raw_log_dir).resolve()
    log_dir.mkdir(parents=True, exist_ok=True)

    return Settings(
        app=AppConfig(
            name=app_cfg.get("name", "Binance Grid Trading Backend"),
            version=app_cfg.get("version", "1.0.0"),
            log_level=app_cfg.get("log_level", "INFO"),
            log_dir=log_dir,
        ),
        mysql=MySQLConfig(
            host=mysql_cfg.get("host", "localhost"),
            port=int(mysql_cfg.get("port", 3306)),
            user=mysql_cfg.get("user", "grid_trading"),
            password=mysql_cfg.get("password", "dev_password"),
            database=mysql_cfg.get("database", "binance_grid_trading"),
            charset=mysql_cfg.get("charset", "utf8mb4"),
            echo=bool(mysql_cfg.get("echo", False)),
        ),
        testing=TestingConfig(
            database_url=testing_cfg.get("database_url"),
        ),
    )


settings = load_config()
