"""服务配置"""

try:
    from pydantic_settings import BaseSettings

    class Settings(BaseSettings):
        host: str = "0.0.0.0"
        port: int = 8220
        debug: bool = False
        version: str = "0.1.0"
        # antgather 回调地址
        antgather_url: str = "http://localhost:8200"

        class Config:
            env_prefix = "DATA_CHECK_"

except ImportError:
    from dataclasses import dataclass, field

    @dataclass
    class Settings:
        host: str = "0.0.0.0"
        port: int = 8220
        debug: bool = False
        version: str = "0.1.0"
        antgather_url: str = "http://localhost:8200"


settings = Settings()
