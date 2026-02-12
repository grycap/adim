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
import json
import uuid
from pydantic import HttpUrl
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from awm.__main__ import create_app
from awm.models.deployment import DeploymentInfo, Deployment
from awm.models.tool import ToolId
from awm.models.allocation import AllocationId
from awm.utils.node_registry import EOSCNode
from awm.utils.db import DataBase
from awm.utils.allocation.allocation_store_vault import AllocationStoreVault
from awm.utils.allocation.allocation_store_db import AllocationStoreDB
import awm


@pytest.fixture
def client():
    return TestClient(app=create_app())


@pytest.fixture
def headers():
    return {"Authorization": "Bearer you-very-secret-token",
            "Content-Type": "application/json"}


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


@pytest.fixture
def db_mock(mocker):
    """Mock genérico para DataBase, retornando una instancia configurable."""
    instance = MagicMock()
    instance.connect.return_value = True
    instance.db_type = DataBase.SQLITE
    db = mocker.patch("awm.utils.allocation.allocation_store_db.DataBase", return_value=instance)
    db.MONGO = DataBase.MONGO
    db.SQLITE = DataBase.SQLITE
    return instance


@pytest.fixture
def vault_mock(mocker):
    client = MagicMock()
    client.is_authenticated.return_value = True
    mocker.patch("hvac.Client", return_value=client)
    return client


@pytest.fixture
def list_nodes_mock(mocker):
    return mocker.patch("awm.utils.node_registry.EOSCNodeRegistry.list_nodes")


@pytest.fixture
def requests_get_mock(mocker):
    return mocker.patch("requests.get")


@pytest.fixture
def requests_post_mock(mocker):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"auth": {"client_token": "ctoken", "entity_id": "eid"}}
    return mocker.patch("requests.post", return_value=response)


@pytest.fixture
def list_deployments_mock(mocker):
    list_dep_mock = mocker.patch("awm.deployments_manager.list_deployments")
    list_dep_mock.return_value = (0, [])
    return list_dep_mock


@pytest.fixture
def time_mock(mocker):
    return mocker.patch("time.time", return_value=1000)


@pytest.fixture
def uuid_mock(mocker):
    return mocker.patch("uuid.uuid4", return_value="new-id")


@pytest.fixture
def allocation_payload():
    return {"kind": "KubernetesEnvironment", "host": "http://k8s.io/"}


def _allocation_data(aid="id1"):
    return {'allocation': {'host': 'http://k8s.io/',
                           'kind': 'KubernetesEnvironment'},
            'id': aid,
            'self': f'http://testserver/allocation/{aid}'}


@pytest.fixture(params=["db", "mongo", "vault", "enc_vault"])
def backend_type(request):
    return request.param


ALLOC_1 = (
    [{
        "id": "id1",
        "data": {"kind": "KubernetesEnvironment", "host": "http://k8s.io"},
    }],
    1,
)

ALLOC_2 = (
    [],
    1
)

ALLOC_3 = (
    [{
        "id": "id1",
        "data": {"kind": "KubernetesEnvironment", "host": "http://k8s.io"},
    }],
    None,
)


@pytest.fixture
def seed_allocations(backend_type, db_mock, vault_mock):
    def _seed(allocations_list):
        if backend_type in ["db", "mongo"]:
            awm.allocation_store = AllocationStoreDB(AllocationStoreDB.DEFAULT_URL)
            awm.allocation_store.db = db_mock
            db_mock.db_type = DataBase.SQLITE
            if backend_type == "mongo":
                db_mock.db_type = DataBase.MONGO
            selects = []
            for allocations_elem in allocations_list:
                allocations, total = allocations_elem
                if backend_type == "mongo":
                    rows = allocations
                else:
                    rows = [[a["id"], json.dumps(a["data"])] for a in allocations]
                selects.append(rows)
                if total is not None:
                    selects.append([[total]])
            if backend_type == "mongo":
                db_mock.find.side_effect = selects
            else:
                db_mock.select.side_effect = selects
        elif backend_type in ["vault", "enc_vault"]:
            if backend_type == "enc_vault":
                awm.allocation_store = AllocationStoreVault(AllocationStoreVault.DEFAULT_URL,
                                                            key=AllocationStoreVault.DEFAULT_KEY)
            else:
                awm.allocation_store = AllocationStoreVault(AllocationStoreVault.DEFAULT_URL)
            res = []
            for allocations_elem in allocations_list:
                allocations, total = allocations_elem
                elems = {}
                for a in allocations:
                    data = json.dumps(a["data"])
                    if backend_type == "enc_vault":
                        key = Fernet(AllocationStoreVault.DEFAULT_KEY)
                        data = key.encrypt(data.encode()).decode()
                    elems[a["id"]] = data
                if total and len(elems) < total:
                    elems[str(uuid.uuid4())] = allocations[0]["data"]
                res.append({"data": elems})
            vault_mock.secrets.kv.v1.read_secret.side_effect = res

    return _seed


@pytest.mark.parametrize("backend_type", ["db", "mongo", "vault"], indirect=True)
def test_list_allocations(
    check_oidc_mock,
    requests_post_mock,
    client,
    headers,
    seed_allocations
):
    seed_allocations([ALLOC_1])

    response = client.get("/allocations/", headers=headers)

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json() == {'count': 1,
                               'elements': [_allocation_data()],
                               'from': 0,
                               'limit': 100}


@pytest.mark.parametrize("backend_type", ["db"], indirect=True)
def test_list_allocations_sql(check_oidc_mock, client, db_mock, headers, seed_allocations):
    seed_allocations([ALLOC_1])
    client.get('/allocations/', headers=headers)

    db_mock.select.assert_any_call(
        "SELECT id, data FROM allocations WHERE owner = %s order by created LIMIT %s OFFSET %s",
        ("user123", 100, 0)
    )

    db_mock.select.assert_any_call(
        "SELECT count(id) from allocations WHERE owner = %s",
        ("user123",)
    )


@pytest.mark.parametrize("backend_type", ["mongo"], indirect=True)
def test_list_allocations_mongo(check_oidc_mock, client, db_mock, headers, seed_allocations):
    seed_allocations([ALLOC_1])
    client.get('/allocations/', headers=headers)

    db_mock.find.assert_called_with(
        "allocations",
        filt={"owner": "user123"},
        projection={"data": True, "id": True},
        sort=[("created", -1)]
    )


@pytest.mark.parametrize("backend_type", ["db"], indirect=True)
def test_list_allocations_remote(
    client, check_oidc_mock, db_mock, list_nodes_mock, requests_get_mock, seed_allocations
):
    seed_allocations([ALLOC_1, ALLOC_2, ALLOC_2, ALLOC_2])

    node1 = EOSCNode(awmAPI=HttpUrl("http://server1.com"), nodeId="n1")
    node2 = EOSCNode(awmAPI=HttpUrl("http://server2.com"), nodeId="n2")
    list_nodes_mock.return_value = [node1, node2]
    resp1 = MagicMock()
    resp1.status_code = 200
    resp1.json.return_value = {'count': 1,
                               'elements': [_allocation_data()],
                               'from': 0,
                               'limit': 100}
    resp2 = MagicMock()
    resp2.status_code = 200
    resp2.json.return_value = {'count': 2,
                               'elements': [_allocation_data(),
                                            _allocation_data('id2')],
                               'from': 0,
                               'limit': 100}

    resp3 = MagicMock()
    resp3.status_code = 200
    resp3.json.return_value = {'count': 2,
                               'elements': [_allocation_data()],
                               'from': 0,
                               'limit': 100}
    requests_get_mock.side_effect = [resp1, resp2, resp1, resp1, resp1, resp2, resp1, resp3]

    headers = {"Authorization": "Bearer you-very-secret-token"}
    response = client.get("/allocations?allNodes=true", headers=headers)
    assert response.status_code == 200
    assert response.json()["count"] == 4
    assert len(response.json()["elements"]) == 4
    requests_get_mock.assert_any_call('http://server1.com/allocations?from0&limit=99',
                                      headers={'Authorization': 'Bearer token'}, timeout=30)
    requests_get_mock.assert_any_call('http://server2.com/allocations?from0&limit=98',
                                      headers={'Authorization': 'Bearer token'}, timeout=30)

    response = client.get("/allocations?allNodes=true&from=1&limit=2", headers=headers)
    assert response.status_code == 200
    assert response.json()["count"] == 3
    assert len(response.json()["elements"]) == 2
    requests_get_mock.assert_any_call('http://server1.com/allocations?from0&limit=2',
                                      headers={'Authorization': 'Bearer token'}, timeout=30)
    requests_get_mock.assert_any_call('http://server2.com/allocations?from0&limit=1',
                                      headers={'Authorization': 'Bearer token'}, timeout=30)

    response = client.get("/allocations?allNodes=true&from=3&limit=2", headers=headers)
    assert response.status_code == 200
    assert response.json()["count"] == 4
    assert len(response.json()["elements"]) == 1

    response = client.get("/allocations?allNodes=true&from=1&limit=2", headers=headers)
    assert response.status_code == 200
    assert response.json()["count"] == 4
    assert len(response.json()["elements"]) == 2
    requests_get_mock.assert_any_call('http://server1.com/allocations?from0&limit=2',
                                      headers={'Authorization': 'Bearer token'}, timeout=30)
    requests_get_mock.assert_any_call('http://server2.com/allocations?from0&limit=1',
                                      headers={'Authorization': 'Bearer token'}, timeout=30)
    assert str(response.json()["nextPage"]) == "http://testserver/allocations?allNodes=true&from=3&limit=2"
    assert str(response.json()["prevPage"]) == "http://testserver/allocations?allNodes=true&from=0&limit=2"


def test_get_allocation(check_oidc_mock, db_mock, client, headers, requests_post_mock, seed_allocations):
    seed_allocations([ALLOC_1])
    response = client.get('/allocation/id1', headers=headers)
    assert response.status_code == 200


@pytest.mark.parametrize("backend_type", ["db", "mongo", "vault"], indirect=True)
def test_delete_allocation(check_oidc_mock, list_deployments_mock, client, headers,
                           requests_post_mock, seed_allocations):
    seed_allocations([ALLOC_3, ALLOC_3, ALLOC_3])

    response = client.delete('/allocation/id1', headers=headers)
    assert response.status_code == 200
    assert response.json() == {"message": "Deleted"}

    list_deployments_mock.return_value = (
        200,
        [
            DeploymentInfo(
                deployment=Deployment(
                    allocation=AllocationId(kind="AllocationId", id="id1", infoLink="http://some.url/"),
                    tool=ToolId(kind="ToolId", id="toolid", version="latest", infoLink="http://some.url/")
                ),
                id="dep_id",
                status="pending"
            )
        ]
    )

    response = client.delete('/allocation/id1', headers=headers)
    assert response.status_code == 409
    assert response.json() == {'description': 'Allocation in use', 'id': '409'}


@pytest.mark.parametrize("backend_type", ["db"], indirect=True)
def test_delete_allocation_sql(check_oidc_mock, list_deployments_mock, client, headers, db_mock, seed_allocations):
    seed_allocations([ALLOC_1, ALLOC_1])

    client.delete('/allocation/id1', headers=headers)
    db_mock.execute.assert_called_with("DELETE FROM allocations WHERE id = %s", ('id1',))


def test_create_allocation(check_oidc_mock, uuid_mock, client, headers, requests_post_mock,
                           seed_allocations, allocation_payload):
    seed_allocations([])
    response = client.post('/allocations', headers=headers, json=allocation_payload)
    assert response.status_code == 201
    assert response.json() == {'id': 'new-id', 'infoLink': 'http://testserver/allocation/new-id'}


@pytest.mark.parametrize("backend_type", ["db"], indirect=True)
def test_create_allocation_sql(check_oidc_mock, time_mock, uuid_mock, db_mock, client,
                               headers, seed_allocations, allocation_payload):
    seed_allocations([])
    client.post('/allocations', headers=headers, json=allocation_payload)
    db_mock.execute.assert_called_with(
        "replace into allocations (id, data, owner, created) values (%s, %s, %s, now())",
        ('new-id', '{"kind": "KubernetesEnvironment", "host": "http://k8s.io/"}', 'user123')
    )


@pytest.mark.parametrize("backend_type", ["mongo"], indirect=True)
def test_create_allocation_mongo(check_oidc_mock, time_mock, uuid_mock, db_mock, client,
                                 headers, seed_allocations, allocation_payload):
    seed_allocations([])
    client.post('/allocations', headers=headers, json=allocation_payload)
    db_mock.replace.assert_called_with(
        "allocations", {"id": "new-id"}, {"id": "new-id", "data": {"kind": "KubernetesEnvironment",
                                                                   "host": "http://k8s.io/"},
                                          "owner": "user123", "created": 1000}
    )


@pytest.mark.parametrize("backend_type", ["vault"], indirect=True)
def test_create_allocation_vault(check_oidc_mock, time_mock, uuid_mock, vault_mock, client, headers,
                                 requests_post_mock, seed_allocations, allocation_payload):
    seed_allocations([])
    client.post('/allocations', headers=headers, json=allocation_payload)
    vault_mock.secrets.kv.v1.create_or_update_secret.assert_called_with(
        'users/user123/allocations',
        {'new-id': '{"kind": "KubernetesEnvironment", "host": "http://k8s.io/"}'},
        mount_point='/secrets'
    )


@pytest.mark.parametrize("backend_type", ["enc_vault"], indirect=True)
def test_create_allocation_enc_vault(check_oidc_mock, time_mock, uuid_mock, vault_mock, client, headers,
                                     requests_post_mock, seed_allocations, allocation_payload):
    seed_allocations([])
    client.post('/allocations', headers=headers, json=allocation_payload)
    value = vault_mock.secrets.kv.v1.create_or_update_secret.call_args_list[0][0][1]
    key = Fernet(AllocationStoreVault.DEFAULT_KEY)
    data = json.loads(key.decrypt(value['new-id'].encode()).decode())
    assert data == {"kind": "KubernetesEnvironment", "host": "http://k8s.io/"}


@pytest.mark.parametrize("backend_type", ["db", "mongo", "vault"], indirect=True)
def test_update_allocation(check_oidc_mock, list_deployments_mock, db_mock, client, headers,
                           requests_post_mock, seed_allocations, allocation_payload):
    seed_allocations([ALLOC_3, ALLOC_3, ALLOC_3])

    response = client.put('/allocation/id1', headers=headers, json=allocation_payload)
    assert response.status_code == 200
    assert response.json() == _allocation_data()


@pytest.mark.parametrize("backend_type", ["db"], indirect=True)
def test_update_allocation_sql(check_oidc_mock, list_deployments_mock, db_mock, client, headers,
                               seed_allocations, allocation_payload):
    seed_allocations([ALLOC_3, ALLOC_3])

    client.put('/allocation/id1', headers=headers, json=allocation_payload)

    db_mock.execute.assert_called_with(
        "update allocations set data = %s where id = %s",
        ('{"kind": "KubernetesEnvironment", "host": "http://k8s.io/"}', 'id1')
    )
