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
import base64
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from adim.__main__ import create_app
from pydantic import HttpUrl
from adim.utils.node_registry import EOSCNode
from adim.utils.application.repository import Repository
from adim.utils.application.app_store import ApplicationStore
import adim


@pytest.fixture
def client():
    return TestClient(app=create_app())


@pytest.fixture
def headers():
    return {"Authorization": "Bearer you-very-secret-token"}


@pytest.fixture
def check_oidc_mock():
    with patch('adim.authorization.check_OIDC') as mock_func:
        mock_func.return_value = {
            "sub": "user123",
            "name": "User DN",
            "eduperson_entitlement": ["vos1", "vos2"],
            "token": "token"
        }
        yield mock_func


@pytest.fixture(params=["git", "rc"])
def backend_type(request):
    return request.param


@pytest.fixture
def repo_mock(mocker):
    repo = Repository.create("https://github.com/grycap/tosca/blob/eosc_lot1/templates/")
    repo.cache_session = MagicMock(["get"])
    mocker.patch("adim.utils.application.repository.Repository.create", return_value=repo)
    return repo


@pytest.fixture
def list_nodes_mock(mocker):
    return mocker.patch("adim.utils.node_registry.EOSCNodeRegistry.list_nodes")


@pytest.fixture
def requests_get_mock(mocker):
    return mocker.patch("requests.get")


@pytest.fixture
def seed_apps(backend_type, repo_mock, requests_get_mock, monkeypatch):
    def _seed(app_list):
        # Set environment variable for the application store type
        monkeypatch.setenv("APPLICATIONS_STORE", backend_type)

        # Use the factory method to create the application store
        adim.application_store = ApplicationStore.get_application_store()

        # Mock the responses based on backend type
        if backend_type == "git":
            repo_mock.cache_session.get.side_effect = app_list
        elif backend_type == "rc":
            requests_get_mock.side_effect = app_list

    return _seed


@pytest.mark.parametrize("backend_type", ["git", "rc"], indirect=True)
def test_list_applications(client, check_oidc_mock, backend_type, repo_mock, requests_get_mock,
                    headers, seed_apps):
    blueprint = "description: DESC\nmetadata:\n  template_name: NAME"

    if backend_type == "git":
        seed_apps([
            MagicMock(status_code=200, json=MagicMock(return_value={
                "tree": [{"type": "blob", "path": "templates/tosca.yaml", "sha": "version"}]
            })),
            MagicMock(status_code=200, text=blueprint)
        ])
    else:  # rc
        resp_list = MagicMock(status_code=200)
        resp_list.json.return_value = {
            "results": [
                {
                    "id": "app1",
                    "version": "version",
                    "url": "http://catalog.url/app1"
                }
            ]
        }
        resp_get = MagicMock(status_code=200)
        resp_get.text = blueprint
        seed_apps([resp_list, resp_get])

    response = client.get("/applications", headers=headers)
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert len(response.json()["elements"]) == 1
    assert response.json()["elements"][0]["description"] == "DESC"
    assert response.json()["elements"][0]["name"] == "NAME"


def test_list_applications_remote(
    client, mocker, check_oidc_mock, repo_mock, list_nodes_mock, requests_get_mock, headers
):
    mocker.patch.dict('os.environ', {'APPLICATIONS_STORE': 'git', 'APPLICATIONS_REPO': 'test'})
    adim.application_store = ApplicationStore.get_application_store()

    blueprint = "description: DESC\nmetadata:\n  template_name: NAME"

    mock_list = MagicMock(status_code=200, json=MagicMock(return_value={
        "tree": [{"type": "blob", "path": "templates/tosca.yaml", "sha": "version"}]
    }))
    mock_get = MagicMock(status_code=200, text=blueprint)
    repo_mock.cache_session.get.side_effect = [
        mock_list,
        mock_get,
        mock_list,
        mock_get,
        mock_list,
        mock_get,
    ]

    node1 = EOSCNode(admAPI=HttpUrl("http://server1.com"), nodeId="n1")
    node2 = EOSCNode(admAPI=HttpUrl("http://server2.com"), nodeId="n2")
    list_nodes_mock.return_value = [node1, node2]

    # Mock remotos
    resp1 = mocker.MagicMock()
    resp1.status_code = 200
    resp1.json.return_value = {
        "count": 1,
        "elements": [{
            "blueprint": blueprint,
            "blueprintType": "tosca",
            "id": "app1",
            "type": "vm",
        }],
        "from": 0,
        "limit": 100,
    }

    resp2 = mocker.MagicMock()
    resp2.status_code = 200
    resp2.json.return_value = {
        "count": 2,
        "elements": [
            {"blueprint": blueprint, "blueprintType": "tosca", "id": "app2", "type": "vm"},
            {"blueprint": blueprint, "blueprintType": "tosca", "id": "app3", "type": "vm"},
        ],
        "from": 0,
        "limit": 100,
    }

    requests_get_mock.side_effect = [resp1, resp2, resp1, resp1, resp1, resp2]

    # 1) Sin paginación
    response = client.get("/applications?allNodes=true", headers=headers)
    assert response.status_code == 200
    assert response.json()["count"] == 4
    assert len(response.json()["elements"]) == 4

    requests_get_mock.assert_any_call(
        "http://server1.com/applications?from=0&limit=99",
        headers={"Authorization": "Bearer token"},
        timeout=30
    )
    requests_get_mock.assert_any_call(
        "http://server2.com/applications?from=0&limit=98",
        headers={"Authorization": "Bearer token"},
        timeout=30
    )

    # 2) from=1 limit=2
    response = client.get("/applications?allNodes=true&from=1&limit=2", headers=headers)
    assert response.status_code == 200
    assert response.json()["count"] == 3
    assert len(response.json()["elements"]) == 2

    requests_get_mock.assert_any_call(
        "http://server1.com/applications?from=0&limit=2",
        headers={"Authorization": "Bearer token"},
        timeout=30
    )
    requests_get_mock.assert_any_call(
        "http://server2.com/applications?from=0&limit=1",
        headers={"Authorization": "Bearer token"},
        timeout=30
    )

    # 3) from=3 limit=2
    response = client.get("/applications?allNodes=true&from=3&limit=2", headers=headers)
    assert response.status_code == 200
    assert response.json()["count"] == 4
    assert len(response.json()["elements"]) == 1


@pytest.mark.parametrize("backend_type", ["git", "rc"], indirect=True)
def test_get_application(client, check_oidc_mock, backend_type, repo_mock, requests_get_mock, headers, seed_apps):
    blueprint = "description: DESC\nmetadata:\n  template_name: NAME"
    application_id = "app1"

    if backend_type == "git":
        resp = MagicMock(status_code=200,
                         json=MagicMock(return_value={
                             "sha": "version",
                             "content": base64.b64encode(
                                 blueprint.encode()
                             ).decode()
                         }))
        seed_apps([resp])

    else:  # rc
        resp = MagicMock(status_code=200)
        resp.text = blueprint
        resp.json.return_value = {
            "id": "app1",
            "version": "version",
            "url": "http://catalog.url/app1"
        }
        resp_get = MagicMock(status_code=200)
        resp_get.text = blueprint
        seed_apps([resp, resp_get])

    response = client.get(f"/application/{application_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["description"] == "DESC"
    assert response.json()["name"] == "NAME"
    assert response.json()["id"] == application_id
    assert response.json()["blueprintType"] == "tosca"
