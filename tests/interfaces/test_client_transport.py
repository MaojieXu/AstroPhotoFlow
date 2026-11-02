import httpx
import pytest

from astrophotoflow.client import AssetClient, ServiceApiError
from astrophotoflow.interfaces.client.errors import ServiceApiError as TransportError


@pytest.mark.parametrize("payload", [[], None, "failure", {"error": []}, {"detail": "failure"}])
def test_invalid_error_envelope_is_diagnostic_instead_of_attribute_error(payload):
    client = AssetClient.__new__(AssetClient)
    with pytest.raises(ServiceApiError) as caught:
        client._result(httpx.Response(502, json=payload, headers={"X-Request-ID": "proxy-request"}))
    assert caught.value.status == 502
    assert caught.value.code == "INVALID_RESPONSE"
    assert caught.value.request_id == "proxy-request"


def test_public_client_retains_unique_error_and_closes_transport_after_failure():
    assert ServiceApiError is TransportError
    client = AssetClient.__new__(AssetClient)
    client.client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200)))
    with pytest.raises(RuntimeError, match="consumer failure"), client as opened:
        assert opened is client
        raise RuntimeError("consumer failure")
    assert client.client.is_closed
