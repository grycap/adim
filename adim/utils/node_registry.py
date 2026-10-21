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

import os

import requests
import logging
from pydantic import BaseModel, HttpUrl
from typing import List, Tuple, Union
from adim.models.page import PageOfItems
from adim.models.allocation import AllocationInfo
from adim.models.apps import ApplicationInfo
from adim.models.deployment import DeploymentInfo


logger = logging.getLogger(__name__)


ItemInfo = Union[AllocationInfo, ApplicationInfo, DeploymentInfo]


class EOSCNode(BaseModel):
    """Class that represents an EOSC Node"""
    nodeId: str
    nodeName: str
    admAPI: HttpUrl | None = None

    def list_applications(self, from_: int, limit: int, count: int, token: str) -> Tuple[int, List[ApplicationInfo]]:
        """Return the list of applications of this node"""
        return self.list_items("applications", from_, limit, count, token)

    def list_allocations(self, from_: int, limit: int, count: int, token: str) -> Tuple[int, List[AllocationInfo]]:
        """Return the list of allocations of this node"""
        return self.list_items("allocations", from_, limit, count, token)

    def list_deployments(self, from_: int, limit: int, count: int, token: str) -> Tuple[int, List[DeploymentInfo]]:
        """Return the list of deployments of this node"""
        return self.list_items("deployments", from_, limit, count, token)

    def list_items(self, item: str, from_: int, limit: int, count: int, token: str) -> Tuple[int, List[ItemInfo]]:
        """Return the list of Items of type 'item' of this node"""
        offset = max(0, from_ - count)
        elems = limit
        url = f"{self.admAPI}{item}?from={offset}&limit={elems}"
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            if response.status_code == 200:
                page = PageOfItems.model_validate(response.json())
                items = page.elements[:limit]
                return page.count, items
        except Exception:
            logger.exception(f"Error getting {item} from node: %s", self.nodeId)
        return 0, []


class EOSCNodeRegistry():
    """Class to interact with the central EOSC Node Registry"""

    EOSC_NODE_REGISTRY_URL = os.getenv("EOSC_NODE_REGISTRY_URL", "https://node-devel.eosc.grnet.gr/federation-backend/tenants/eosc-beyond")

    @staticmethod
    def list_nodes() -> List[str]:
        """Return the list of available nodes"""
        url = f"{EOSCNodeRegistry.EOSC_NODE_REGISTRY_URL}/services"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        nodes = response.json()
        return [str(node["id"]) for node in nodes]

    @staticmethod
    def get_node_by_id(node_id: str) -> EOSCNode:
        """Retun the node with ID `node_id`"""
        url = f"{EOSCNodeRegistry.EOSC_NODE_REGISTRY_URL}/nodes/{node_id}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        node_info = response.json()

        admAPI = None
        try:
            response = requests.get(node_info["service"]["endpoint"], timeout=30)
            response.raise_for_status()
            local_node_info = response.json()

            for cap in local_node_info["capabilities"]:
                if cap["capability_type"] == "Application Deployment Management":
                    admAPI = HttpUrl(cap["endpoint"])
                    break
        except Exception as ex:
            logger.error(f"Error getting information for node {node_id}. Ignoring... ({ex})")

        return EOSCNode(nodeId=node_id,
                        nodeName=node_info["service"]["service_name"],
                        admAPI=admAPI)

    @staticmethod
    def list_items(item: str, from_: int, limit: int, count: int, user_info) -> Tuple[int, List[ItemInfo]]:
        """Return the list of remote items"""
        total = 0
        offset = max(0, from_ - count)
        local_page_count = max(0, min(limit, count - from_))
        items = []
        try:
            nodes = EOSCNodeRegistry.list_nodes()
        except Exception as ex:
            logger.error(f"Error listing nodes: {ex}")
            return 0, []
        for node_id in nodes:
            try:
                node = EOSCNodeRegistry.get_node_by_id(node_id)
            except Exception as ex:
                logger.error(f"Error getting node {node_id}: {ex}")
                continue
            if node.admAPI is None:
                logger.debug(f"Node {node.nodeName} does not have an ADM API, skipping")
                continue
            node_offset = offset
            remaining = max(0, limit - local_page_count - len(items))
            node_total, node_items = node.list_items(
                item, node_offset, remaining, 0, user_info["token"]
            )
            if item == "applications":
                for application in node_items:
                    if isinstance(application, ApplicationInfo):
                        application.nodeId = node.nodeId
            offset = max(0, offset - node_total)
            if len(items) < limit - local_page_count:
                items.extend(node_items[:limit - local_page_count - len(items)])
            total += node_total
        return total, items

    @staticmethod
    def list_allocations(from_: int, limit: int, count: int, user_info) -> Tuple[int, List[AllocationInfo]]:
        """Return the list of remote allocations"""
        return EOSCNodeRegistry.list_items("allocations", from_, limit, count, user_info)

    @staticmethod
    def list_applications(from_: int, limit: int, count: int, user_info) -> Tuple[int, List[ApplicationInfo]]:
        """Return the list of remote applications"""
        return EOSCNodeRegistry.list_items("applications", from_, limit, count, user_info)

    @staticmethod
    def list_deployments(from_: int, limit: int, count: int, user_info) -> Tuple[int, List[DeploymentInfo]]:
        """Return the list of remote deployments"""
        return EOSCNodeRegistry.list_items("deployments", from_, limit, count, user_info)
