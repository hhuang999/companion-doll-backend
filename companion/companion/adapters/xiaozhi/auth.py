"""Per-device bearer credentials bind connections to server-owned user identities."""

import hmac
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class DeviceCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_key: str = Field(min_length=1, max_length=128)
    token: str = Field(min_length=32, max_length=256)
    enabled: bool = True


class AccessRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(default=1, ge=1, le=1)
    devices: dict[str, DeviceCredential]


class AccessDenied(ValueError):
    pass


def registry_path(options):
    return Path(
        options.get("access_file") or Path(options["project_root"]) / "data/device-access.json"
    )


def authenticate(options, headers):
    """Never use caller-supplied device IDs as the memory identity."""
    path = registry_path(options)
    if not path.is_file():
        raise AccessDenied("Device registry is not provisioned")
    registry = AccessRegistry.model_validate(json.loads(path.read_text(encoding="utf-8")))
    device = headers.get("device-id", "")
    authorization = headers.get("authorization", "")
    credential = registry.devices.get(device)
    if (
        not credential
        or not credential.enabled
        or not authorization.startswith("Bearer ")
        or not hmac.compare_digest(credential.token.encode(), authorization[7:].encode())
    ):
        raise AccessDenied("Invalid device credentials")
    return credential.user_key


def client_headers(path):
    """Read private connection details; callers must never log the returned headers."""
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    return {"device-id": value["device_id"], "authorization": "Bearer " + value["token"]}
