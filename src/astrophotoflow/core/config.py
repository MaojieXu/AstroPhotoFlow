import base64
import hashlib
import ipaddress
import json
import logging
import os
import subprocess
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

from filelock import FileLock, Timeout
from pydantic import ValidationError

from astrophotoflow.contracts.workbench import ConfigState, ConfigValues
from astrophotoflow.core.errors import ApiError

CONFIG_PATH = Path.home() / ".config/astrophotoflow/config.toml"
logger = logging.getLogger("astrophotoflow.configuration")


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
    workspace: Path = field(kw_only=True)

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


def default_workspace() -> Path | None:
    return _default_workspace(_default_bytes())


def resolve_config_path(path: Path | None = None) -> Path:
    if path is not None:
        return path.expanduser().resolve()
    configured = os.environ.get("ASTROPHOTOFLOW_CONFIG")
    if configured:
        return Path(configured).expanduser().resolve()
    default = default_workspace()
    if default is None:
        raise ConfigurationError(
            "未设置默认 workspace；请运行 apf init --workspace <路径> 初始化，或用 --workspace / ASTROPHOTOFLOW_CONFIG 明确指定。")
    config_path = default / "config.toml"
    if not config_path.is_file():
        raise ConfigurationError(
            f"默认 workspace 无效：{default} 下没有 config.toml；请运行 apf init --workspace <路径> 重新设置，"
            "或用 --workspace / ASTROPHOTOFLOW_CONFIG 明确指定。")
    return config_path


def load_settings(config_path: Path | None = None) -> Settings:
    config_path = resolve_config_path(config_path)
    if not config_path.is_file():
        raise ConfigurationError(f"配置文件不存在：{config_path}")
    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigurationError(f"配置文件无效：{exc}") from exc
    return _settings_from_raw(raw, config_path)


def _settings_from_raw(raw: dict, config_path: Path) -> Settings:
    try:
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
        return Settings(str(address), port, data_path.resolve(), tuple(origins), tuple(import_roots), file_workers, preview_workers,
                        workspace=config_path.parent)
    except (KeyError, TypeError, ValueError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError(f"配置文件无效：{exc}") from exc


def _default_bytes() -> bytes:
    return CONFIG_PATH.read_bytes() if CONFIG_PATH.is_file() else b""


def _default_workspace(content: bytes) -> Path | None:
    try:
        raw = tomllib.loads(content.decode("utf-8"))
        if not raw:
            return None
        if set(raw) != {"workspace"} or set(raw["workspace"]) != {"default"}:
            raise ValueError("用户配置只接受 [workspace] default。")
        value = raw["workspace"]["default"]
        if not isinstance(value, str) or not value.strip():
            raise ValueError("默认 workspace 必须为非空路径。")
        return Path(value).expanduser().resolve()
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigurationError(f"默认 workspace 配置无效：{exc}") from exc


def _raw_from_values(values: ConfigValues) -> dict:
    return {
        "server": {"host": values.host, "port": values.service_port},
        "storage": {"data_dir": values.data_dir},
        "comfyui": {"allowed_origins": values.allowed_origins},
        "imports": {"roots": [root.model_dump() for root in values.import_roots]},
        "ingestion": {"file_workers": values.file_workers, "preview_workers": values.preview_workers},
    }


def _values_from_raw(raw: dict) -> ConfigValues:
    return ConfigValues(
        host=raw["server"]["host"], service_port=raw["server"]["port"], data_dir=raw["storage"]["data_dir"],
        allowed_origins=raw["comfyui"]["allowed_origins"], import_roots=raw.get("imports", {}).get("roots", []),
        file_workers=raw.get("ingestion", {}).get("file_workers", 2),
        preview_workers=raw.get("ingestion", {}).get("preview_workers", 1),
    )


def _running_values(workspace: Path, raw: dict) -> ConfigValues:
    if Path(raw["workspace"]).resolve() != workspace or Path(raw["config_path"]).resolve() != workspace / "config.toml":
        raise ValueError("运行采用记录不属于目标 workspace。")
    return ConfigValues.model_validate(raw["effective_settings"])


def load_running_settings(workspace: Path) -> Settings:
    workspace = workspace.expanduser().resolve()
    path = workspace / "run" / "processes.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        values = _running_values(workspace, raw)
        return _settings_from_raw(_raw_from_values(values), workspace / "config.toml")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise ConfigurationError(f"无法读取运行采用配置：{exc}") from exc


def get_configuration(config_path: Path | None = None) -> ConfigState:
    config_path = resolve_config_path(config_path)
    content = config_path.read_bytes()
    try:
        raw = tomllib.loads(content.decode("utf-8"))
    except ValueError as exc:
        raise ConfigurationError(f"配置文件无效：{exc}") from exc
    saved_settings = _settings_from_raw(raw, config_path)
    default_content = _default_bytes()
    default = _default_workspace(default_content)
    token_content = json.dumps([str(config_path), content.hex(), default_content.hex()]).encode("utf-8")
    effective = None
    restart_required = False
    run_path = saved_settings.workspace / "run" / "processes.json"
    if run_path.is_file():
        try:
            run = json.loads(run_path.read_text(encoding="utf-8"))
            if run["processes"]:
                effective = _running_values(saved_settings.workspace, run)
                running = _settings_from_raw(_raw_from_values(effective), config_path)
                restart_required = saved_settings != running
        except (OSError, KeyError, TypeError, ValueError, ConfigurationError) as exc:
            raise ApiError(503, 'RUNNING_CONFIGURATION_UNAVAILABLE', str(exc), message_key='running_configuration_unavailable', fields=[{'path': 'configuration', 'message': str(exc)}]) from exc
    return ConfigState(
        config_path=str(config_path), default_workspace=str(default) if default is not None else None,
        data_dir_absolute=str(saved_settings.data_dir),
        saved=_values_from_raw(raw), config_token=hashlib.sha256(token_content).hexdigest(),
        effective=effective, restart_required=restart_required,
    )


def select_directory(initial_path: Path) -> Path | None:
    if os.name != "nt":
        raise ConfigurationError("系统文件夹选择窗口目前仅支持Windows。")
    encoded_path = base64.b64encode(str(initial_path).encode("utf-8")).decode("ascii")
    script = """
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
[Windows.Forms.Application]::EnableVisualStyles()
$dialog = New-Object Windows.Forms.FolderBrowserDialog
$dialog.Description = '选择文件夹'
$dialog.SelectedPath = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('""" + encoded_path + """'))
try {
    if ($dialog.ShowDialog() -eq [Windows.Forms.DialogResult]::OK) {
        [Console]::Write($dialog.SelectedPath)
    }
} finally {
    $dialog.Dispose()
}
"""
    command = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-STA", "-EncodedCommand", command],
        capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    selected = result.stdout.decode("utf-8-sig").strip()
    return Path(selected).resolve() if selected else None


def write_configuration_file(path: Path, text: str) -> None:
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                break
            except PermissionError as exc:
                if os.name != "nt" or exc.winerror != 5 or attempt == 4:
                    raise
                logger.warning("Windows读句柄暂时阻止配置原子替换 path=%s attempt=%s", path, attempt + 1)
                time.sleep(0.05)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _write_default_workspace(workspace: Path) -> None:
    write_configuration_file(CONFIG_PATH, '[workspace]\ndefault = ' + json.dumps(str(workspace), ensure_ascii=False) + '\n')


def set_default_workspace(workspace: Path) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(CONFIG_PATH) + ".lock", timeout=0):
        _write_default_workspace(workspace.expanduser().resolve())


def configuration_text(values: ConfigValues) -> str:
    quote = json.dumps
    roots = ", ".join("{ id = " + quote(root.id) + ", path = " + quote(root.path) + " }" for root in values.import_roots)
    return (
        f'[server]\nhost = {quote(values.host)}\nport = {values.service_port}\n\n'
        f'[storage]\ndata_dir = {quote(values.data_dir)}\n\n'
        f'[comfyui]\nallowed_origins = [{", ".join(quote(origin) for origin in values.allowed_origins)}]\n\n'
        f'[imports]\nroots = [{roots}]\n\n'
        f'[ingestion]\nfile_workers = {values.file_workers}\npreview_workers = {values.preview_workers}\n'
    )




def save_configuration(config_path: Path, values: ConfigValues, config_token: str, *,
                       default_workspace: Path | None = None) -> ConfigState:
    config_path = resolve_config_path(config_path)
    try:
        values = ConfigValues.model_validate(values.model_dump())
        _settings_from_raw(_raw_from_values(values), config_path)
        if default_workspace is not None and not str(default_workspace).strip():
            raise ValueError("默认 workspace 必须为非空路径。")
    except (ValidationError, ConfigurationError, ValueError) as exc:
        raise ApiError(422, 'INVALID_CONFIGURATION', str(exc), message_key='configuration_invalid', fields=[{'path': 'configuration', 'message': str(exc)}]) from exc
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(str(CONFIG_PATH) + ".lock", timeout=0):
            if get_configuration(config_path).config_token != config_token:
                raise ApiError(409, "CONFIGURATION_CONFLICT", "配置已被修改，请重新读取。", message_key='configuration_has_changed_read_it_again')
            write_configuration_file(config_path, configuration_text(values))
            if default_workspace is not None:
                try:
                    _write_default_workspace(default_workspace.expanduser().resolve())
                except OSError as exc:
                    raise ApiError(503, "CONFIGURATION_PARTIALLY_SAVED", "workspace 配置已保存，但默认位置保存失败；请重新读取。", message_key='workspace_configuration_was_saved_but_the_default_location_could_not_be_sav') from exc
            return get_configuration(config_path)
    except Timeout as exc:
        raise ApiError(409, "CONFIGURATION_BUSY", "配置正在保存，请重新读取后再提交。", message_key='configuration_is_being_saved_read_it_again_before_submitting') from exc


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


def settings_from_values(values: ConfigValues, config_path: Path) -> Settings:
    return _settings_from_raw(_raw_from_values(values), config_path)
