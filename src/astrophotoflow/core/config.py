from dataclasses import dataclass
import ipaddress
import os
from pathlib import Path
import tomllib
from urllib.parse import urlsplit


CONFIG_PATH = Path.home() / ".config/astrophotoflow/config.toml"


class ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ImportRoot:
    id: str
    path: Path


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    data_dir: Path
    allowed_origins: tuple[str, ...]
    import_roots: tuple[ImportRoot, ...] = ()
    file_workers: int = 2
    preview_workers: int = 1

    @property
    def service_url(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{host}:{self.port}"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "astrophotoflow.sqlite3"

    @property
    def token_path(self) -> Path:
        return self.data_dir / "service.token"

    @property
    def lock_path(self) -> Path:
        return self.data_dir / ".database.lock"


def resolve_config_path(path: Path | None = None) -> Path:
    if path is not None:
        return path.expanduser().resolve()
    configured = os.environ.get("ASTROPHOTOFLOW_CONFIG")
    if configured:
        return Path(configured).expanduser().resolve()
    pointer = CONFIG_PATH.parent / "active-workspace"
    if pointer.is_file():
        return Path(pointer.read_text(encoding="utf-8").strip()).expanduser().resolve()
    return CONFIG_PATH.resolve()


def load_settings(config_path: Path | None = None) -> Settings:
    config_path = resolve_config_path(config_path)
    if not config_path.is_file():
        raise ConfigurationError(f"配置文件不存在：{config_path}")
    try:
        with config_path.open("rb") as stream:
            raw = tomllib.load(stream)
        server = raw["server"]
        storage = raw["storage"]
        comfyui = raw["comfyui"]
        host = server["host"]
        port = server["port"]
        data_dir = storage["data_dir"]
        origins = comfyui["allowed_origins"]
        if not {"server", "storage", "comfyui"} <= set(raw) or set(raw) - {"server", "storage", "comfyui", "imports", "ingestion"}:
            raise ValueError("顶层配置包含未知字段")
        if set(server) != {"host", "port"} or set(storage) != {"data_dir"} or set(comfyui) != {"allowed_origins"}:
            raise ValueError("配置字段与约定不符")
        import_roots = []
        if "imports" in raw:
            imports = raw["imports"]
            if set(imports) != {"roots"} or not isinstance(imports["roots"], list):
                raise ValueError("imports 配置必须包含根目录列表")
            seen_root_ids = set()
            for root in imports["roots"]:
                if not isinstance(root, dict) or set(root) != {"id", "path"}:
                    raise ValueError("素材根目录只接受 id 和 path")
                root_id, root_path = root["id"], root["path"]
                if not isinstance(root_id, str) or not root_id.strip() or root_id in seen_root_ids:
                    raise ValueError("素材根目录 id 必须非空且唯一")
                if not isinstance(root_path, str) or not root_path.strip():
                    raise ValueError("素材根目录 path 必须为非空路径")
                root_path = Path(root_path).expanduser()
                if not root_path.is_absolute():
                    raise ValueError("素材根目录路径必须为绝对路径（可使用 ~ 展开）")
                seen_root_ids.add(root_id)
                import_roots.append(ImportRoot(root_id, root_path))

        ingestion = raw.get("ingestion", {})
        if not isinstance(ingestion, dict) or set(ingestion) - {"file_workers", "preview_workers"}:
            raise ValueError("ingestion 只接受 file_workers 和 preview_workers")
        file_workers = ingestion.get("file_workers", 2)
        preview_workers = ingestion.get("preview_workers", 1)
        if any(type(value) is not int or value < 1 for value in (file_workers, preview_workers)):
            raise ValueError("导入与预览并发数必须为正整数")
        address = ipaddress.ip_address(host)
        if not isinstance(host, str) or not address.is_loopback:
            raise ValueError("server.host 必须是本机回环地址")
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("server.port 必须是 1–65535 的整数")
        if not isinstance(data_dir, str) or not data_dir.strip():
            raise ValueError("storage.data_dir 必须是非空路径")
        if not isinstance(origins, list) or not origins:
            raise ValueError("comfyui.allowed_origins 必须是非空的本机 HTTP 来源列表")
        for origin in origins:
            parsed = urlsplit(origin) if isinstance(origin, str) else None
            if parsed is None or parsed.scheme != "http" or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
                raise ValueError("allowed_origins 必须是无路径的本机 HTTP 来源")
            if parsed.hostname != "localhost" and not ipaddress.ip_address(parsed.hostname).is_loopback:
                raise ValueError("allowed_origins 只能包含本机回环地址")
            if parsed.port is None or not 1 <= parsed.port <= 65535:
                raise ValueError("allowed_origins 必须包含有效端口")
        data_path = Path(data_dir).expanduser()
        if not data_path.is_absolute():
            data_path = config_path.parent / data_path
        return Settings(str(address), port, data_path.resolve(), tuple(origins), tuple(import_roots), file_workers, preview_workers)
    except (KeyError, TypeError, ValueError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError(f"配置文件无效：{exc}") from exc


def ensure_data_dir(settings: Settings) -> None:
    created = not settings.data_dir.exists()
    settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if created:
        os.chmod(settings.data_dir, 0o700)


def ensure_service_token(settings: Settings) -> str:
    import secrets

    ensure_data_dir(settings)
    if not settings.token_path.exists():
        token = secrets.token_urlsafe(32)
        descriptor = os.open(settings.token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(token)
    token = settings.token_path.read_text(encoding="utf-8").strip()
    if not token:
        raise ConfigurationError(f"服务令牌文件为空：{settings.token_path}")
    os.chmod(settings.token_path, 0o600)
    return token
