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

import awm
import json
import pytest
from pydantic import HttpUrl
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from awm.__main__ import create_app
from awm.utils.db import DataBase
from awm.utils.node_registry import EOSCNode
from awm.utils.deployment_manager import DeploymentsManager


@pytest.fixture
def client():
    return TestClient(app=create_app())


@pytest.fixture
def db_mock(mocker):
    """Mock genérico para DataBase, retornando una instancia configurable."""
    instance = MagicMock()
    instance.connect.return_value = True
    instance.db_type = DataBase.SQLITE
    db = mocker.patch("awm.utils.deployment_manager.DataBase", return_value=instance)
    db.MONGO = DataBase.MONGO
    db.SQLITE = DataBase.SQLITE
    return instance


@pytest.fixture
def seed_deployments(db_mock):
    def _seed(deployments):
        awm.routers.deployments.deployments_manager = DeploymentsManager("", "")
        awm.routers.deployments.deployments_manager.db = db_mock
        if db_mock.db_type == DataBase.MONGO:
            db_mock.find.side_effect = deployments
        else:
            db_mock.select.side_effect = deployments
    return _seed


@pytest.fixture
def check_oidc_mock(mocker):
    """Mock para check_OIDC."""
    mocked = mocker.patch("awm.authorization.check_OIDC")
    mocked.return_value = {"sub": "test-user", "token": "astoken"}
    return mocked


@pytest.fixture
def im_mock(mocker):
    """Mock para IMClient."""
    mocked = mocker.patch("awm.utils.deployment_manager.IMClient.init_client")
    im_mocked = MagicMock()
    mocked.return_value = im_mocked
    return im_mocked


@pytest.fixture
def allocation_mock(mocker):
    """Mock para _get_allocation con un entorno estándar Kubernetes."""
    allocation = {"kind": "KubernetesEnvironment", "host": "http://some.url/"}
    return mocker.patch("awm.utils.deployment_manager.allocation_store.get_allocation", return_value=allocation)


@pytest.fixture
def ost_allocation_mock(mocker):
    """Mock para _get_allocation con un entorno estándar Kubernetes."""
    allocation = {"kind": "OpenStackEnvironment", "host": "http://some.url/", 
                  "userName": "user", "password": "pass", "tenant": "tenant", "domain": "domain"}
    return mocker.patch("awm.utils.deployment_manager.allocation_store.get_allocation", return_value=allocation)


@pytest.fixture
def list_nodes_mock(mocker):
    return mocker.patch("awm.utils.node_registry.EOSCNodeRegistry.list_nodes")


@pytest.fixture
def requests_get_mock(mocker):
    return mocker.patch("requests.get")


def _get_deployment_info(dep_id="dep_id"):
    return (f'{{"id": "{dep_id}", '
            '"deployment": {"tool": {"kind": "ToolId", "id": "toolid", '
            '"version": "latest", "infoLink": "http://some.url"}, '
            '"allocation": {"kind": "AllocationId", "id": "aid", "infoLink": "http://some.url"}}, '
            f'"status": "pending", "self_": "http://some.url/deployment/{dep_id}"}}')


def test_list_deployments(client, db_mock, check_oidc_mock, seed_deployments):
    seed_deployments([[[_get_deployment_info()]], [[1]]])

    response = client.get("/deployments",
                          headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["elements"][0]["id"] == "dep_id"

    db_mock.select.assert_any_call(
        "SELECT data FROM deployments WHERE owner = %s order by created LIMIT %s OFFSET %s",
        ("test-user", 100, 0)
    )

    db_mock.select.assert_any_call(
        "SELECT count(id) from deployments WHERE owner = %s",
        ("test-user",)
    )


def test_list_deployments_mongo(client, db_mock, check_oidc_mock, seed_deployments):
    db_mock.db_type = DataBase.MONGO
    seed_deployments([[{"data": json.loads(_get_deployment_info())}]])

    response = client.get("/deployments",
                          headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["elements"][0]["id"] == "dep_id"

    db_mock.find.assert_called_with(
        "deployments",
        filt={"owner": "test-user"},
        projection={"data": True},
        sort=[("created", -1)]
    )


def test_list_deployments_remote(client, db_mock, check_oidc_mock, list_nodes_mock, requests_get_mock, seed_deployments):
    selects = [
        [[_get_deployment_info()]],
        [[1]],
        [],
        [[1]],
        [],
        [[1]],
        [],
        [[1]]
    ]
    seed_deployments(selects)

    node1 = EOSCNode(awmAPI=HttpUrl("http://server1.com"), nodeId="n1")
    node2 = EOSCNode(awmAPI=HttpUrl("http://server2.com"), nodeId="n2")
    list_nodes_mock.return_value = [node1, node2]
    resp1 = MagicMock()
    resp1.status_code = 200
    resp1.json.return_value = {'count': 1,
                               'elements': [json.loads(_get_deployment_info('dep_id1'))],
                               'from': 0,
                               'limit': 100}
    resp2 = MagicMock()
    resp2.status_code = 200
    resp2.json.return_value = {'count': 2,
                               'elements': [json.loads(_get_deployment_info('dep_id1')),
                                            json.loads(_get_deployment_info('dep_id2'))],
                               'from': 0,
                               'limit': 100}

    resp3 = MagicMock()
    resp3.status_code = 200
    resp3.json.return_value = {'count': 2,
                               'elements': [json.loads(_get_deployment_info('dep_id1'))],
                               'from': 0,
                               'limit': 100}
    requests_get_mock.side_effect = [resp1, resp2, resp1, resp1, resp1, resp2, resp1, resp3]

    headers = {"Authorization": "Bearer you-very-secret-token"}
    response = client.get("/deployments?allNodes=true", headers=headers)
    assert response.status_code == 200
    assert response.json()["count"] == 4
    assert len(response.json()["elements"]) == 4
    requests_get_mock.assert_any_call('http://server1.com/deployments?from0&limit=99',
                                      headers={'Authorization': 'Bearer astoken'}, timeout=30)
    requests_get_mock.assert_any_call('http://server2.com/deployments?from0&limit=98',
                                      headers={'Authorization': 'Bearer astoken'}, timeout=30)

    response = client.get("/deployments?allNodes=true&from=1&limit=2", headers=headers)
    assert response.status_code == 200
    assert response.json()["count"] == 3
    assert len(response.json()["elements"]) == 2
    requests_get_mock.assert_any_call('http://server1.com/deployments?from0&limit=2',
                                      headers={'Authorization': 'Bearer astoken'}, timeout=30)
    requests_get_mock.assert_any_call('http://server2.com/deployments?from0&limit=1',
                                      headers={'Authorization': 'Bearer astoken'}, timeout=30)

    response = client.get("/deployments?allNodes=true&from=3&limit=2", headers=headers)
    assert response.status_code == 200
    assert response.json()["count"] == 4
    assert len(response.json()["elements"]) == 1

    response = client.get("/deployments?allNodes=true&from=1&limit=2", headers=headers)
    assert response.status_code == 200
    assert response.json()["count"] == 4
    assert len(response.json()["elements"]) == 2
    requests_get_mock.assert_any_call('http://server1.com/deployments?from0&limit=2',
                                      headers={'Authorization': 'Bearer astoken'}, timeout=30)
    requests_get_mock.assert_any_call('http://server2.com/deployments?from0&limit=1',
                                      headers={'Authorization': 'Bearer astoken'}, timeout=30)
    assert str(response.json()["nextPage"]) == "http://testserver/deployments?allNodes=true&from=3&limit=2"
    assert str(response.json()["prevPage"]) == "http://testserver/deployments?allNodes=true&from=0&limit=2"


def test_get_deployment(client, db_mock, check_oidc_mock, im_mock, allocation_mock, seed_deployments):
    seed_deployments([[[_get_deployment_info()]]])

    im_mock.get_infra_property.side_effect = [
        (True, {"state": "running"}),
        (True, "contmsg")
    ]

    response = client.get("/deployment/dep_id",
                          headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert response.json()["deployment"]["tool"]["id"] == "toolid"
    assert response.json()["details"] == "contmsg"

    db_mock.select.assert_called_with(
        "SELECT data FROM deployments WHERE id = %s and owner = %s",
        ("dep_id", "test-user")
    )


def test_get_deployment_no_im(client, db_mock, check_oidc_mock, im_mock, allocation_mock, seed_deployments):
    seed_deployments([[[_get_deployment_info()]]])

    im_mock.get_infra_property.side_effect = [
        (False, "error"),
        (False, "error")
    ]

    im_mock.list_infras.return_value = True, ["other_dep_id"]

    response = client.get("/deployment/dep_id",
                          headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    assert response.json()["deployment"]["tool"]["id"] == "toolid"

    db_mock.select.assert_called_with(
        "SELECT data FROM deployments WHERE id = %s and owner = %s",
        ("dep_id", "test-user")
    )


def test_delete_deployment(client, db_mock, check_oidc_mock, im_mock, ost_allocation_mock, seed_deployments):
    seed_deployments([[[_get_deployment_info()]]])

    im_mock.destroy.return_value = True, ""

    response = client.delete("/deployment/dep_id",
                             headers={"Authorization": "Bearer token"})

    assert response.status_code == 202
    assert response.json() == {"message": "Deleting"}

    db_mock.execute.assert_called_with(
        "DELETE FROM deployments WHERE id = %s",
        ("dep_id",)
    )


@pytest.fixture
def get_tool_mock(mocker):
    tool = MagicMock()
    tool.blueprint = "tool blueprint"
    return mocker.patch("awm.routers.deployments.tool_store.get_tool_from_repo", return_value=(tool, 200))

@pytest.fixture
def allocation_mock_router(mocker):
    """Mock para _get_allocation con un entorno estándar Kubernetes."""
    allocation = {"kind": "KubernetesEnvironment", "host": "http://some.url/"}
    return mocker.patch("awm.utils.deployment_manager.allocation_store.get_allocation", return_value=allocation)


def test_deploy_workload(
    client, db_mock, check_oidc_mock, im_mock, get_tool_mock, allocation_mock_router
):
    im_mock.create.return_value = True, "new_dep_id"

    payload = ('{"tool": {"kind": "ToolId", "id": "toolid"}, '
               '"allocation": {"kind": "AllocationId", "id": "aid"}}')

    response = client.post("/deployments",
                           headers={"Authorization": "Bearer token"},
                           content=payload)

    assert response.status_code == 202
    assert response.json()["id"] == "new_dep_id"
    assert response.json()["infoLink"] == "http://testserver/deployment/new_dep_id"
