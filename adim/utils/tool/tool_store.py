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

import adim
import os
from typing import List, Tuple, Union
from fastapi import Request
from adim.models.tool import ToolInfo
from adim.models.error import Error
from adim.utils import ConnectionException


class ToolStore:

    def __init__(self, url: str):
        self.url = url

    @staticmethod
    def get_tool_type(tosca: dict) -> str:
        try:
            node_templates = tosca.get('topology_template', {}).get('node_templates', {})
            for _, node in node_templates.items():
                if node.get('type', '') == 'tosca.nodes.Container.Application.Docker':
                    return "container"
        except Exception:
            adim.logger.exception("Error getting tool type using default 'vm'")
        return "vm"

    def _list(self, request: Request, from_: int, limit: int, user_info: dict) -> List[ToolInfo]:
        raise NotImplementedError()

    def list_tools(self, request: Request, from_: int = 0, limit: int = 100,
                   user_info: dict = None) -> Tuple[int, int, List[ToolInfo]]:
        tools = []
        try:
            tools_list = self._list(request, from_, limit, user_info)
        except Exception as e:
            raise ConnectionException(f"Failed to get list of Tools: {e}") from e

        count = 0
        total = len(tools_list)
        for tool in tools_list:
            count += 1
            if from_ > count - 1:
                continue
            try:
                tools.append(tool)
                if len(tools) >= limit:
                    break
            except Exception as ex:
                adim.logger.error("Failed to get tool info: %s", ex)

        return total, count, tools

    @staticmethod
    def get_tool_info(elem: dict, request: Request) -> ToolInfo:
        raise NotImplementedError()

    def get_tool(self, tool_id: str, version: str, request: Request,
                 user_info: dict = None) -> Tuple[Union[ToolInfo, Error], int]:
        raise NotImplementedError()

    @staticmethod
    def get_tool_store() -> 'ToolStore':
        """Factory method to get the ToolStore instance based on the configuration"""
        tool_type = os.getenv("TOOL_STORE", "git")
        if tool_type == "git":
            tools_repo = os.getenv("TOOLS_REPO", "https://github.com/grycap/tosca/blob/eosc_lot1/templates/")
            from adim.utils.tool.git_tool_store import ToolStoreGit
            tool_store = ToolStoreGit(tools_repo)
        elif tool_type == "rc":
            resource_catalog = os.getenv("RESOURCE_CATALOG", "https://providers.sandbox.eosc-beyond.eu/api")
            from adim.utils.tool.rc_tool_store import ToolStoreRC
            tool_store = ToolStoreRC(resource_catalog)
        else:
            raise ValueError(f"Tool store '{tool_type}' is not supported")
        return tool_store
