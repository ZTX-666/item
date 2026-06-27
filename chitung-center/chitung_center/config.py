from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8999

    agent_toolbox_base_url: str = "http://127.0.0.1:8899"
    agent_toolbox_timeout_seconds: float = 900.0

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    glm_api_key: str = ""
    zhipu_api_key: str = ""
    zhipuai_api_key: str = ""
    docmate_api_key: str = ""
    docmate_api_url: str = ""
    docmate_model: str = ""

    chitung_data_dir: Path = ROOT / "data"
    chitung_skills_dir: Path = ROOT / "skills"
    chitung_workflows_dir: Path = ROOT / "workflows"
    chitung_audit_log: Path = ROOT / "data" / "audit.jsonl"
    rag_chroma_dir: Path = ROOT / "data" / "rag_chroma"
    rag_meta_path: Path = ROOT / "data" / "rag_meta.json"
    rag_upload_dir: Path = ROOT / "data" / "rag_uploads"
    llm_embedding_base_url: str = ""
    llm_embedding_model: str = ""
    secureeye_base_url: str = ""
    secureeye_api_key: str = ""
    secureeye_model: str = "glm-4.5v"
    secureeye_timeout_seconds: int = 60
    secureeye_max_concurrency: int = 1
    secureeye_max_targets_per_camera: int = 2
    table_mapping_script_dir: Path = ROOT / "table-mapping" / "auto-fill-script"
    table_mapping_node_bin: str = "node"
    table_mapping_timeout_seconds: int = 180

    # Demo / presentation: skip auto patrol + external monitor schedulers on startup.
    disable_background_schedulers: bool = False

    lifting_alert_whatsapp_to: str = "+85284941215"

    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_verification_token: str = ""
    feishu_encrypt_key: str = ""
    feishu_api_base_url: str = "https://open.feishu.cn"
    feishu_long_connection_log_level: str = "INFO"
    feishu_bot_open_id: str = ""
    feishu_bot_names: str = "赤瞳,赤瞳机器人"

    enable_feishu_adapter: bool = False
    enable_zht_adapter: bool = False
    enable_chitong_lingxun_adapter: bool = False
    enable_docmate_adapter: bool = False
    enable_yaoyao_huidu_adapter: bool = False
    enable_openclaw_adapter: bool = False

    def model_post_init(self, __context: object) -> None:
        alias_key = self.llm_api_key or self.glm_api_key or self.zhipu_api_key or self.zhipuai_api_key or self.docmate_api_key
        if alias_key and not self.llm_api_key:
            self.llm_api_key = alias_key
        if self.llm_api_key and not self.llm_base_url:
            self.llm_base_url = self.docmate_api_url or "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        if self.llm_api_key and not self.llm_model:
            self.llm_model = self.docmate_model or "glm-5.1"
        if self.llm_base_url and not self.secureeye_base_url:
            self.secureeye_base_url = self.llm_base_url
        if self.llm_api_key and not self.secureeye_api_key:
            self.secureeye_api_key = self.llm_api_key

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)


settings = Settings(
    _env_file=str(ROOT / ".env"),
    _env_file_encoding="utf-8",
)
