from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("RAGENT_HOST", "0.0.0.0")
    port: int = int(os.getenv("RAGENT_PORT", "9090"))
    context_path: str = os.getenv("RAGENT_CONTEXT_PATH", "/api/ragent")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/ragent",
    )
    mcp_server_url: str = os.getenv("MCP_SERVER_URL", "http://localhost:9099")
    redis_url: str = os.getenv("REDIS_URL", "redis://:123456@127.0.0.1:6379/0")
    sse_timeout_ms: int = int(os.getenv("RAGENT_SSE_TIMEOUT_MS", "300000"))
    chat_max_concurrent: int = int(os.getenv("RAGENT_CHAT_MAX_CONCURRENT", "10"))
    chat_task_ttl_seconds: int = int(os.getenv("RAGENT_CHAT_TASK_TTL_SECONDS", "600"))
    chat_provider: str = os.getenv("RAGENT_CHAT_PROVIDER", "").lower()
    embedding_provider: str = os.getenv("RAGENT_EMBEDDING_PROVIDER", "").lower()
    rerank_provider: str = os.getenv("RAGENT_RERANK_PROVIDER", "").lower()
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_chat_model: str = os.getenv("OLLAMA_CHAT_MODEL", "qwen3:8b-fp16")
    ollama_embedding_model: str = os.getenv("OLLAMA_EMBEDDING_MODEL", "qwen3-embedding:8b-fp16")
    bailian_url: str = os.getenv("BAILIAN_URL", "https://dashscope.aliyuncs.com")
    bailian_api_key: str = os.getenv("BAILIAN_API_KEY", "")
    bailian_chat_model: str = os.getenv("BAILIAN_CHAT_MODEL", "qwen-plus-latest")
    bailian_rerank_model: str = os.getenv("BAILIAN_RERANK_MODEL", "qwen3-rerank")
    aihubmix_url: str = os.getenv("AIHUBMIX_URL", "https://aihubmix.com")
    aihubmix_api_key: str = os.getenv("AIHUBMIX_API_KEY", "")
    aihubmix_chat_model: str = os.getenv("AIHUBMIX_CHAT_MODEL", "gpt-5.4")
    aihubmix_embedding_model: str = os.getenv("AIHUBMIX_EMBEDDING_MODEL", "text-embedding-3-large")
    siliconflow_url: str = os.getenv("SILICONFLOW_URL", "https://api.siliconflow.cn")
    siliconflow_api_key: str = os.getenv("SILICONFLOW_API_KEY", "")
    siliconflow_chat_model: str = os.getenv("SILICONFLOW_CHAT_MODEL", "Pro/zai-org/GLM-4.7")
    siliconflow_embedding_model: str = os.getenv("SILICONFLOW_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B")
    milvus_uri: str = os.getenv("MILVUS_URI", "http://localhost:19530")
    vector_provider: str = os.getenv("RAGENT_VECTOR_PROVIDER", "pgvector").lower()
    rustfs_url: str = os.getenv("RUSTFS_URL", "http://localhost:9000")
    rustfs_access_key_id: str = os.getenv("RUSTFS_ACCESS_KEY_ID", "rustfsadmin")
    rustfs_secret_access_key: str = os.getenv("RUSTFS_SECRET_ACCESS_KEY", "rustfsadmin")
    object_storage_bucket: str = os.getenv("RAGENT_OBJECT_STORAGE_BUCKET", "ragent")
    rocketmq_name_server: str = os.getenv("ROCKETMQ_NAME_SERVER", "127.0.0.1:9876")


settings = Settings()
