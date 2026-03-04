#
# Copyright (C) GRyCAP - I3M - UPV
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
import adm.authorization
from adm.oidc.client import OpenIDClient
from adm.authorization import check_OIDC
from unittest.mock import MagicMock
from fastapi import HTTPException


@pytest.fixture
def token(mocker):
    return ("eyJraWQiOiJyc2ExIiwiYWxnIjoiUlMyNTYifQ.eyJzdWIiOiJkYzVkNWFiNy02ZGI5LTQwNzktOTg1Yy04MGFjMDUwMTcw"
            "NjYiLCJpc3MiOiJodHRwczpcL1wvaWFtLXRlc3QuaW5kaWdvLWRhdGFjbG91ZC5ldVwvIiwiZXhwIjoxNDY2MDkzOTE3LCJ"
            "pYXQiOjE0NjYwOTAzMTcsImp0aSI6IjE1OTU2N2U2LTdiYzItNDUzOC1hYzNhLWJjNGU5MmE1NjlhMCJ9.eINKxJa2J--xd"
            "GAZWIOKtx9Wi0Vz3xHzaSJWWY-UHWy044TQ5xYtt0VTvmY5Af-ngwAMGfyaqAAvNn1VEP-_fMYQZdwMqcXLsND4KkDi1ygiC"
            "IwQ3JBz9azBT1o_oAHE5BsPsE2BjfDoVRasZxxW5UoXCmBslonYd8HK2tUVjz0")


@pytest.fixture
def jwt_mock(mocker):
    """Mock para requests.request()"""
    return mocker.patch("adm.oidc.client.JWT.get_info")


@pytest.fixture
def requests_mock(mocker):
    """Mock para requests.request()"""
    return mocker.patch("adm.oidc.client.requests.request")


@pytest.fixture
def time_mock(mocker):
    """Mock para time.time()"""
    return mocker.patch("adm.oidc.client.time.time")


def test_get_openid_configuration_success(requests_mock):
    """Test obtener configuración OpenID exitosamente"""
    iss = "https://issuer.example.com"
    response_data = {
        "userinfo_endpoint": "https://issuer.example.com/userinfo",
        "introspection_endpoint": "https://issuer.example.com/introspect",
        "token_endpoint": "https://issuer.example.com/token"
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = response_data
    requests_mock.return_value = mock_response

    OpenIDClient.ISSUER_CONFIG_CACHE = {}
    result = OpenIDClient.get_openid_configuration(iss)

    assert "userinfo_endpoint" in result
    assert result["userinfo_endpoint"] == "https://issuer.example.com/userinfo"
    assert result["introspection_endpoint"] == "https://issuer.example.com/introspect"
    requests_mock.assert_called_once_with(
        "GET",
        "https://issuer.example.com/.well-known/openid-configuration",
        verify=False,
        timeout=OpenIDClient.DEFAULT_TIMEOUT
    )


def test_get_user_info_request_success(requests_mock, token):
    """Test obtener user info exitosamente"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "userinfo_endpoint": "https://issuer.example.com/userinfo",
        "introspection_endpoint": "https://issuer.example.com/introspect"
    }
    mock_response2 = MagicMock()
    mock_response2.status_code = 200
    mock_response2.json.return_value = {
        "sub": "user123",
        "name": "Test User",
        "email": "user@example.com"
    }
    requests_mock.side_effect = [mock_response, mock_response2]

    OpenIDClient.ISSUER_CONFIG_CACHE = {}
    success, user_info = OpenIDClient.get_user_info_request(token)

    assert success is True
    assert user_info["sub"] == "user123"
    assert user_info["name"] == "Test User"
    assert user_info["email"] == "user@example.com"

    # Verificar que se hizo la llamada con los headers correctos
    requests_mock.assert_called()
    call_args = requests_mock.call_args
    assert call_args[1]["headers"]["Authorization"] == f"Bearer {token}"


def test_get_token_introspection_success(requests_mock, token):
    """Test obtener introspección de token exitosamente"""
    client_id = "client123"
    client_secret = "secret456"

    jwt_mock.return_value = {"iss": "https://issuer.example.com"}

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "userinfo_endpoint": "https://issuer.example.com/userinfo",
        "introspection_endpoint": "https://issuer.example.com/introspect"
    }
    mock_response2 = MagicMock()
    mock_response2.status_code = 200
    mock_response2.json.return_value = {
        "active": True,
        "exp": 9999999999,
        "sub": "user123"
    }
    requests_mock.side_effect = [mock_response, mock_response2]

    OpenIDClient.ISSUER_CONFIG_CACHE = {}
    adm.authorization.OIDC_ISSUERS = ["https://issuer.example.com"]
    success, introspection = OpenIDClient.get_token_introspection(token, None, client_id, client_secret)

    assert success is True
    assert introspection["active"] is True
    assert introspection["sub"] == "user123"


def test_token_not_expired(jwt_mock, time_mock, token):
    """Test token válido (no expirado)"""
    current_time = 1000
    expiration_time = 2000

    jwt_mock.return_value = {"exp": expiration_time}
    time_mock.return_value = current_time

    is_expired, message = OpenIDClient.is_access_token_expired(token)

    assert is_expired is False
    assert "Valid Token" in message
    assert "1000 seconds" in message


def test_token_expired(token):
    """Test token expirado"""
    is_expired, message = OpenIDClient.is_access_token_expired(token)

    assert is_expired is True
    assert "Token expired" in message


def test_auth_check_oidc_expired(token):
    with pytest.raises(HTTPException):
        check_OIDC(token)


def test_auth_check_oidc_success(requests_mock, jwt_mock, time_mock, token):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "userinfo_endpoint": "https://issuer.example.com/userinfo",
        "introspection_endpoint": "https://issuer.example.com/introspect"
    }
    mock_response2 = MagicMock()
    mock_response2.status_code = 200
    mock_response2.json.return_value = {
        "sub": "user123",
        "name": "Test User",
        "email": "user@example.com"
    }
    requests_mock.side_effect = [mock_response, mock_response2]

    current_time = 1000
    expiration_time = 2000

    jwt_mock.return_value = {"exp": expiration_time, "iss": "https://issuer.example.com"}
    time_mock.return_value = current_time

    OpenIDClient.ISSUER_CONFIG_CACHE = {}
    adm.authorization.OIDC_ISSUERS = ["https://issuer.example.com"]
    res = check_OIDC(token)

    assert res["sub"] == "user123"
    assert res["name"] == "Test User"
    assert res["email"] == "user@example.com"


def test_auth_check_oidc_issuers(requests_mock, jwt_mock, time_mock, token):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "userinfo_endpoint": "https://issuer.example.com/userinfo",
        "introspection_endpoint": "https://issuer.example.com/introspect"
    }
    mock_response2 = MagicMock()
    mock_response2.status_code = 200
    mock_response2.json.return_value = {
        "sub": "user123",
        "name": "Test User",
        "email": "user@example.com"
    }
    requests_mock.side_effect = [mock_response, mock_response2]

    current_time = 1000
    expiration_time = 2000

    jwt_mock.return_value = {"exp": expiration_time, "iss": "https://issuer.example.com"}
    time_mock.return_value = current_time

    OpenIDClient.ISSUER_CONFIG_CACHE = {}
    adm.authorization.OIDC_ISSUERS = ["https://issuer.example.com"]
    res = check_OIDC(token)
    assert res["sub"] == "user123"

    adm.authorization.OIDC_ISSUERS = ["https://other-issuer.example.com"]
    with pytest.raises(HTTPException):
        check_OIDC(token)


def test_auth_check_oidc_aud(requests_mock, jwt_mock, time_mock, token):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "userinfo_endpoint": "https://issuer.example.com/userinfo",
        "introspection_endpoint": "https://issuer.example.com/introspect"
    }
    mock_response2 = MagicMock()
    mock_response2.status_code = 200
    mock_response2.json.return_value = {
        "sub": "user123",
        "name": "Test User",
        "email": "user@example.com"
    }
    requests_mock.side_effect = [mock_response, mock_response2]

    current_time = 1000
    expiration_time = 2000

    jwt_mock.return_value = {"exp": expiration_time, "iss": "https://issuer.example.com",
                             "aud": "adm"}
    time_mock.return_value = current_time

    OpenIDClient.ISSUER_CONFIG_CACHE = {}
    adm.authorization.OIDC_ISSUERS = ["https://issuer.example.com"]
    adm.authorization.OIDC_AUDIENCE = "adm"
    res = check_OIDC(token)
    assert res["sub"] == "user123"

    jwt_mock.return_value = {"exp": expiration_time, "iss": "https://issuer.example.com"}
    with pytest.raises(HTTPException):
        res = check_OIDC(token)

    adm.authorization.OIDC_AUDIENCE = ""


def test_auth_check_oidc_groups(requests_mock, jwt_mock, time_mock, token):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "userinfo_endpoint": "https://issuer.example.com/userinfo",
        "introspection_endpoint": "https://issuer.example.com/introspect"
    }
    mock_response2 = MagicMock()
    mock_response2.status_code = 200
    mock_response2.json.return_value = {
        "sub": "user123",
        "name": "Test User",
        "email": "user@example.com",
        "groups": ["adm"]
    }
    mock_response3 = MagicMock()
    mock_response3.status_code = 200
    mock_response3.json.return_value = {
        "sub": "user123",
        "name": "Test User",
        "email": "user@example.com"
    }
    requests_mock.side_effect = [mock_response, mock_response2, mock_response3]

    current_time = 1000
    expiration_time = 2000

    jwt_mock.return_value = {"exp": expiration_time, "iss": "https://issuer.example.com"}
    time_mock.return_value = current_time

    OpenIDClient.ISSUER_CONFIG_CACHE = {}
    adm.authorization.OIDC_ISSUERS = ["https://issuer.example.com"]
    adm.authorization.OIDC_GROUPS = "adm"
    res = check_OIDC(token)
    assert res["sub"] == "user123"

    with pytest.raises(HTTPException):
        res = check_OIDC(token)

    adm.authorization.OIDC_GROUPS = ""
