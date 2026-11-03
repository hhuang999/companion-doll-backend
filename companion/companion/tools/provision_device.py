"""Create local device credentials without printing secrets; no external provisioning service."""

import argparse
import json
import secrets
import uuid
from pathlib import Path

from companion.adapters.xiaozhi.auth import AccessRegistry, DeviceCredential


def simulation_credentials(root, prefix):
    from companion.adapters.xiaozhi.auth import client_headers

    identifier = f"synthetic-{prefix}-{uuid.uuid4().hex[:12]}"
    path = root / "artifacts/private-clients" / f"{identifier}.json"
    provision(root / "data/device-access.json", path, identifier, identifier)
    return identifier, client_headers(path)


def provision(registry_path, output_path, device_id, user_key, *, rotate=False):
    if not device_id or len(device_id) > 128:
        raise ValueError("Device ID must contain 1-128 characters")
    registry = (
        AccessRegistry.model_validate_json(registry_path.read_text(encoding="utf-8"))
        if registry_path.exists()
        else AccessRegistry(devices={})
    )
    current = registry.devices.get(device_id)
    if current and current.user_key != user_key and not rotate:
        raise ValueError("Existing mapping differs; explicit --rotate required")
    credential = (
        current
        if current and not rotate
        else DeviceCredential(user_key=user_key, token=secrets.token_urlsafe(32))
    )
    registry.devices[device_id] = credential
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(registry.model_dump_json(indent=2), encoding="utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {"device_id": device_id, "token": credential.token, "user_key": credential.user_key},
            indent=2,
        ),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=Path("data/device-access.json"))
    parser.add_argument("--output", type=Path, default=Path("data/device-client.json"))
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--user-key", required=True)
    parser.add_argument("--rotate", action="store_true")
    args = parser.parse_args()
    provision(args.registry, args.output, args.device_id, args.user_key, rotate=args.rotate)
    print(f"Private client credential written to {args.output}; keep it off Git and public Pages.")


if __name__ == "__main__":
    main()
