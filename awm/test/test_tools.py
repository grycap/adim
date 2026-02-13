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
from awm.__main__ import create_app
from pydantic import HttpUrl
from awm.utils.node_registry import EOSCNode
from awm.utils.tool.repository import Repository
import awm


@pytest.fixture
def client():
    return TestClient(app=create_app())


@pytest.fixture
def headers():
    return {"Authorization": "Bearer you-very-secret-token"}


@pytest.fixture
def check_oidc_mock():
    with patch('awm.authorization.check_OIDC') as mock_func:
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
    mocker.patch("awm.utils.tool.repository.Repository.create", return_value=repo)
    return repo


@pytest.fixture
def list_nodes_mock(mocker):
    return mocker.patch("awm.utils.node_registry.EOSCNodeRegistry.list_nodes")


@pytest.fixture
def requests_get_mock(mocker):
    return mocker.patch("requests.get")


@pytest.fixture
def seed_tools(backend_type, repo_mock, requests_get_mock):
    def _seed(tools_list):
        if backend_type == "git":
            from awm.utils.tool.git_tool_store import ToolStoreGit
            awm.tool_store = ToolStoreGit("https://github.com/grycap/tosca/blob/eosc_lot1/templates/")

            # Mock the repository responses for git backend
            responses = []
            for tools_elem in tools_list:
                responses.append(tools_elem)
            repo_mock.cache_session.get.side_effect = responses

        elif backend_type == "rc":
            from awm.utils.tool.rc_tool_store import ToolStoreRC
            awm.tool_store = ToolStoreRC("https://providers.sandbox.eosc-beyond.eu/api")

            # Mock the requests.get responses for rc backend
            responses = []
            for tools_elem in tools_list:
                responses.append(tools_elem)
            requests_get_mock.side_effect = responses

    return _seed


@pytest.mark.parametrize("backend_type", ["git", "rc"], indirect=True)
def test_list_tools(client, check_oidc_mock, backend_type, repo_mock, requests_get_mock,
                    headers, seed_tools):
    blueprint = "description: DESC\nmetadata:\n  template_name: NAME"

    if backend_type == "git":
        seed_tools([
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
                    "id": "tool1",
                    "version": "version",
                    "url": "http://catalog.url/tool1"
                }
            ]
        }
        resp_get = MagicMock(status_code=200)
        resp_get.text = blueprint
        seed_tools([resp_list, resp_get])

    response = client.get("/tools", headers=headers)
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert len(response.json()["elements"]) == 1
    assert response.json()["elements"][0]["description"] == "DESC"
    assert response.json()["elements"][0]["name"] == "NAME"


def test_list_tools_remote(
    client, mocker, check_oidc_mock, repo_mock, list_nodes_mock, requests_get_mock, headers
):
    from awm.utils.tool.git_tool_store import ToolStoreGit
    awm.tool_store = ToolStoreGit("test")

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

    node1 = EOSCNode(awmAPI=HttpUrl("http://server1.com"), nodeId="n1")
    node2 = EOSCNode(awmAPI=HttpUrl("http://server2.com"), nodeId="n2")
    list_nodes_mock.return_value = [node1, node2]

    # Mock remotos
    resp1 = mocker.MagicMock()
    resp1.status_code = 200
    resp1.json.return_value = {
        "count": 1,
        "elements": [{
            "blueprint": blueprint,
            "blueprintType": "tosca",
            "id": "tool1",
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
            {"blueprint": blueprint, "blueprintType": "tosca", "id": "tool2", "type": "vm"},
            {"blueprint": blueprint, "blueprintType": "tosca", "id": "tool3", "type": "vm"},
        ],
        "from": 0,
        "limit": 100,
    }

    requests_get_mock.side_effect = [resp1, resp2, resp1, resp1, resp1, resp2]

    # 1) Sin paginación
    response = client.get("/tools?allNodes=true", headers=headers)
    assert response.status_code == 200
    assert response.json()["count"] == 4
    assert len(response.json()["elements"]) == 4

    requests_get_mock.assert_any_call(
        "http://server1.com/tools?from=0&limit=99",
        headers={"Authorization": "Bearer token"},
        timeout=30
    )
    requests_get_mock.assert_any_call(
        "http://server2.com/tools?from=0&limit=98",
        headers={"Authorization": "Bearer token"},
        timeout=30
    )

    # 2) from=1 limit=2
    response = client.get("/tools?allNodes=true&from=1&limit=2", headers=headers)
    assert response.status_code == 200
    assert response.json()["count"] == 3
    assert len(response.json()["elements"]) == 2

    requests_get_mock.assert_any_call(
        "http://server1.com/tools?from=0&limit=2",
        headers={"Authorization": "Bearer token"},
        timeout=30
    )
    requests_get_mock.assert_any_call(
        "http://server2.com/tools?from=0&limit=1",
        headers={"Authorization": "Bearer token"},
        timeout=30
    )

    # 3) from=3 limit=2
    response = client.get("/tools?allNodes=true&from=3&limit=2", headers=headers)
    assert response.status_code == 200
    assert response.json()["count"] == 4
    assert len(response.json()["elements"]) == 1


@pytest.mark.parametrize("backend_type", ["git", "rc"], indirect=True)
def test_get_tool(client, check_oidc_mock, backend_type, repo_mock, requests_get_mock, headers, seed_tools):
    blueprint = "description: DESC\nmetadata:\n  template_name: NAME"
    tool_id = "toolid"

    if backend_type == "git":
        resp = MagicMock(status_code=200,
                         json=MagicMock(return_value={
                             "sha": "version",
                             "content": base64.b64encode(
                                 blueprint.encode()
                             ).decode()
                         }))
        seed_tools([resp])

    else:  # rc
        resp = MagicMock(status_code=200)
        resp.text = blueprint
        resp.json.return_value = {
            "id": "toolid",
            "version": "version",
            "url": "http://catalog.url/tool1"
        }
        resp_get = MagicMock(status_code=200)
        resp_get.text = blueprint
        seed_tools([resp, resp_get])

    response = client.get(f"/tool/{tool_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["description"] == "DESC"
    assert response.json()["name"] == "NAME"
    assert response.json()["id"] == tool_id
    assert response.json()["blueprintType"] == "tosca"
