import json

import pytest
from companion.adapters.xiaozhi.auth import AccessDenied, authenticate, client_headers
from companion.tools.provision_device import provision


def test_identity_requires_its_own_credential_and_rotation_revokes_old(tmp_path):
    registry = tmp_path / "data/device-access.json"
    one, two = tmp_path / "one.json", tmp_path / "two.json"
    options = {"project_root": str(tmp_path)}
    provision(registry, one, "device-one", "user-one")
    provision(registry, two, "device-two", "user-two")
    headers = client_headers(one)
    assert authenticate(options, headers) == "user-one"
    assert authenticate(options, client_headers(two)) == "user-two"
    for forged in (
        {"device-id": "device-one"},
        {**headers, "device-id": "device-two"},
        {**headers, "authorization": "Bearer 中文伪造"},
    ):
        with pytest.raises(AccessDenied):
            authenticate(options, forged)
    # The credential cannot choose another memory identity via a client header.
    assert authenticate(options, {**headers, "user-key": "user-two"}) == "user-one"
    provision(registry, one, "device-one", "user-one", rotate=True)
    with pytest.raises(AccessDenied):
        authenticate(options, headers)
    assert authenticate(options, client_headers(one)) == "user-one"
    data = json.loads(registry.read_text(encoding="utf-8"))
    data["devices"]["device-one"]["enabled"] = False
    registry.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(AccessDenied):
        authenticate(options, client_headers(one))


def test_missing_registry_fails_closed(tmp_path):
    with pytest.raises(AccessDenied, match="not provisioned"):
        authenticate({"project_root": str(tmp_path)}, {"device-id": "anything"})
