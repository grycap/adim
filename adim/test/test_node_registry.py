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

from unittest.mock import Mock

import pytest
from pydantic import HttpUrl

from adim.utils.node_registry import EOSCNode, EOSCNodeRegistry


def _response(payload, status_code=200):
    response = Mock(status_code=status_code)
    response.json.return_value = payload
    return response


def test_list_nodes_returns_service_ids(mocker):
    get = mocker.patch(
        "adim.utils.node_registry.requests.get",
        return_value=_response([{"id": "node-1"}, {"id": 42}]),
    )

    assert EOSCNodeRegistry.list_nodes() == ["node-1", "42"]
    get.assert_called_once_with(f"{EOSCNodeRegistry.EOSC_NODE_REGISTRY_URL}/services", timeout=30)
    get.return_value.raise_for_status.assert_called_once_with()


def test_list_nodes_propagates_http_errors(mocker):
    response = _response([])
    response.raise_for_status.side_effect = RuntimeError("registry unavailable")
    mocker.patch("adim.utils.node_registry.requests.get", return_value=response)

    with pytest.raises(RuntimeError, match="registry unavailable"):
        EOSCNodeRegistry.list_nodes()


def test_get_node_by_id_finds_adm_capability(mocker):
    get = mocker.patch(
        "adim.utils.node_registry.requests.get",
        side_effect=[
            _response({"service": {"service_name": "Node One", "endpoint": "https://node.example/info"}}),
            _response({"capabilities": [
                {"capability_type": "Other", "endpoint": "https://node.example/other"},
                {"capability_type": "Application Deployment Management",
                 "endpoint": "https://node.example/adm/"},
                {"capability_type": "Application Deployment Management",
                 "endpoint": "https://node.example/ignored/"},
            ]}),
        ],
    )

    node = EOSCNodeRegistry.get_node_by_id("node-1")

    assert node.nodeId == "node-1"
    assert node.nodeName == "Node One"
    assert node.admAPI == HttpUrl("https://node.example/adm/")
    assert get.call_args_list[0].args == (f"{EOSCNodeRegistry.EOSC_NODE_REGISTRY_URL}/nodes/node-1",)
    assert get.call_args_list[1].args == ("https://node.example/info",)
    assert all(call.kwargs == {"timeout": 30} for call in get.call_args_list)


def test_get_node_by_id_keeps_node_when_local_info_fails(mocker):
    mocker.patch(
        "adim.utils.node_registry.requests.get",
        side_effect=[_response({"service": {"service_name": "Node One", "endpoint": "https://node.example/info"}}),
                     RuntimeError("node unavailable")],
    )

    node = EOSCNodeRegistry.get_node_by_id("node-1")

    assert node.nodeName == "Node One"
    assert node.admAPI is None


def test_eosc_node_list_items_applies_pagination_and_token(mocker):
    page = {"from": 0, "limit": 5, "count": 8, "elements": [
        {"id": f"app-{i}", "name": f"App {i}", "version": "1.0", "description": "test",
         "licenses": [], "inputs": [], "outputs": []}
        for i in range(5)
    ]}
    get = mocker.patch("adim.utils.node_registry.requests.get", return_value=_response(page))
    node = EOSCNode(nodeId="node-1", nodeName="Node One", admAPI="https://node.example/adm/")

    count, items = node.list_applications(from_=3, limit=4, count=2, token="secret")

    assert count == 8
    assert [item.id for item in items] == ["app-1", "app-2"]
    get.assert_called_once_with(
        "https://node.example/adm/applications?from=0&limit=3",
        headers={"Authorization": "Bearer secret"},
        timeout=30,
    )


def test_eosc_node_list_items_returns_empty_on_request_error(mocker):
    get = mocker.patch("adim.utils.node_registry.requests.get", side_effect=RuntimeError("offline"))
    node = EOSCNode(nodeId="node-1", nodeName="Node One", admAPI="https://node.example/adm/")

    assert node.list_items("deployments", 0, 10, 0, "secret") == (0, [])
    get.assert_called_once()


@pytest.mark.parametrize(
    ("method", "item"),
    [("list_allocations", "allocations"), ("list_applications", "applications"),
     ("list_deployments", "deployments")],
)
def test_registry_list_methods_select_item(mocker, method, item):
    list_items = mocker.patch.object(EOSCNodeRegistry, "list_items", return_value=(0, []))
    user_info = {"token": "secret"}

    assert getattr(EOSCNodeRegistry, method)(1, 5, 0, user_info) == (0, [])
    list_items.assert_called_once_with(item, 1, 5, 0, user_info)


def test_registry_list_items_aggregates_nodes_and_advances_count(mocker):
    mocker.patch.object(EOSCNodeRegistry, "list_nodes", return_value=["node-1", "node-2", "node-3"])
    node1 = EOSCNode(nodeId="node-1", nodeName="Node One", admAPI="https://node1.example/adm/")
    node2 = EOSCNode(nodeId="node-2", nodeName="Node Two", admAPI=None)
    node3 = EOSCNode(nodeId="node-3", nodeName="Node Three", admAPI="https://node3.example/adm/")
    mocker.patch.object(EOSCNodeRegistry, "get_node_by_id", side_effect=[node1, node2, node3])
    list_remote = mocker.patch.object(EOSCNode, "list_items", side_effect=[(8, ["item-1", "item-2"]), (4, ["item-3"])])

    result = EOSCNodeRegistry.list_items("applications", 3, 4, 1, {"token": "secret"})

    assert result == (12, ["item-1", "item-2", "item-3"])
    assert list_remote.call_args_list[0].args == ("applications", 3, 4, 1, "secret")
    assert list_remote.call_args_list[1].args == ("applications", 3, 4, 3, "secret")


def test_registry_list_items_skips_failed_nodes_and_handles_registry_error(mocker):
    mocker.patch.object(EOSCNodeRegistry, "list_nodes", return_value=["bad-node", "good-node"])
    good_node = EOSCNode(nodeId="good-node", nodeName="Good Node", admAPI="https://good.example/adm/")
    mocker.patch.object(EOSCNodeRegistry, "get_node_by_id", side_effect=[RuntimeError("bad node"), good_node])
    mocker.patch.object(EOSCNode, "list_items", return_value=(2, []))

    assert EOSCNodeRegistry.list_items("allocations", 0, 10, 0, {"token": "secret"}) == (2, [])

    mocker.patch.object(EOSCNodeRegistry, "list_nodes", side_effect=RuntimeError("registry down"))
    assert EOSCNodeRegistry.list_items("allocations", 0, 10, 0, {"token": "secret"}) == (0, [])
