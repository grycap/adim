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

import requests
import logging
from pydantic import BaseModel, HttpUrl
from typing import List, Tuple, Union
from adm.models.page import PageOfItems
from adm.models.allocation import AllocationInfo
from adm.models.tool import ToolInfo
from adm.models.deployment import DeploymentInfo


logger = logging.getLogger(__name__)


ItemInfo = Union[AllocationInfo, ToolInfo, DeploymentInfo]


class EOSCNode(BaseModel):
    """Class that represents an EOSC Node"""
    nodeId: str
    nodeName: str = None
    admAPI: HttpUrl

    def list_tools(self, from_: int, limit: int, count: int, token: str) -> Tuple[int, List[ToolInfo]]:
        """Return the list of tools of this node"""
        return self.list_items("tools", from_, limit, count, token)

    def list_allocations(self, from_: int, limit: int, count: int, token: str) -> Tuple[int, List[AllocationInfo]]:
        """Return the list of allocations of this node"""
        return self.list_items("allocations", from_, limit, count, token)

    def list_deployments(self, from_: int, limit: int, count: int, token: str) -> Tuple[int, List[DeploymentInfo]]:
        """Return the list of deployments of this node"""
        return self.list_items("deployments", from_, limit, count, token)

    def list_items(self, item: str, from_: int, limit: int, count: int, token: str) -> Tuple[int, List[ItemInfo]]:
        """Return the list of Items of type 'item' of this node"""
        init = max(0, from_ - count)
        elems = limit - (count - from_)
        url = f"{self.admAPI}{item}?from=0&limit={elems}"
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            if response.status_code == 200:
                page = PageOfItems.model_validate(response.json())
                items = page.elements[init:] if len(page.elements) > init else []
                return page.count, items
        except Exception:
            logger.exception(f"Error getting {item} from node: %s", self.nodeId)
        return 0, []


class EOSCNodeRegistry():
    """Class to interact with the central EOSC Node Registry"""

    @staticmethod
    def list_nodes() -> List[EOSCNode]:
        """Return the list of available nodes"""
        # @TODO(list): Complete
        return []

    @staticmethod
    def get_node_by_id(node_id: str) -> EOSCNode:
        """Retun the node with ID `node_id`"""
        # @TODO(get): Complete
        return None

    @staticmethod
    def list_items(item: str, from_: int, limit: int, count: int, user_info) -> Tuple[int, List[ItemInfo]]:
        """Return the list of remote items"""
        total = 0
        num_items = 0
        items = []
        for node in EOSCNodeRegistry.list_nodes():
            node_total, node_items = node.list_items(item, from_, limit, count + num_items, user_info["token"])
            num_items += len(node_items) if node_items else node_total
            total += node_total
            items.extend(node_items)
        return total, items

    @staticmethod
    def list_allocations(from_: int, limit: int, count: int, user_info) -> Tuple[int, List[AllocationInfo]]:
        """Return the list of remote allocations"""
        return EOSCNodeRegistry.list_items("allocations", from_, limit, count, user_info)

    @staticmethod
    def list_tools(from_: int, limit: int, count: int, user_info) -> Tuple[int, List[ToolInfo]]:
        """Return the list of remote tools"""
        return EOSCNodeRegistry.list_items("tools", from_, limit, count, user_info)

    @staticmethod
    def list_deployments(from_: int, limit: int, count: int, user_info) -> Tuple[int, List[DeploymentInfo]]:
        """Return the list of remote deployments"""
        return EOSCNodeRegistry.list_items("deployments", from_, limit, count, user_info)
