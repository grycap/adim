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

import base64
import yaml
import adm
from typing import Tuple, Union, List
from fastapi import Request
from adm.models.tool import ToolInfo
from adm.models.error import Error
from adm.utils.tool.repository import Repository
from adm.utils import ConnectionException
from .tool_store import ToolStore


class ToolStoreGit(ToolStore):

    def __init__(self, url: str):
        super().__init__(url)

    @staticmethod
    def get_tool_type(tosca: dict) -> str:
        try:
            node_templates = tosca.get('topology_template', {}).get('node_templates', {})
            for _, node in node_templates.items():
                if node.get('type', '') == 'tosca.nodes.Container.Application.Docker':
                    return "container"
        except Exception:
            adm.logger.exception("Error getting tool type using default 'vm'")
        return "vm"

    @staticmethod
    def get_tool_info(elem: dict, request: Request) -> ToolInfo:
        tosca = yaml.safe_load(elem["template"])
        metadata = tosca.get("metadata", {})
        tool_id = elem['path'].replace("/", "%2F")
        url = str(request.url_for("get_tool", tool_id=tool_id))
        version = elem.get("version", "latest")
        if version != "latest":
            url += "?version=%s" % version
        tool = ToolInfo(
            id=elem['path'],
            self_=url,
            version='latest',
            type=ToolStore.get_tool_type(tosca),
            name=metadata.get("template_name", ""),
            description=tosca.get("description", ""),
            blueprint=elem["template"],
            blueprintType="tosca"
        )
        if metadata.get("template_author"):
            tool.authorName = metadata.get("template_author")
        if version:
            tool.version = version
        return tool

    def get_tool(self, tool_id: str, version: str, request: Request,
                 user_info: dict = None) -> Tuple[Union[ToolInfo, Error], int]:
        # tool_id was provided with underscores; convert back path
        repo_tool_id = tool_id.replace("%2F", "/")
        try:
            repo = Repository.create(self.url)
            response = repo.get(repo_tool_id, version, details=True)
        except Exception as e:
            adm.logger.error("Failed to get tool info: %s", e)
            raise ConnectionException("Failed to get tool info: %s" % e)

        if response.status_code == 404:
            msg = Error(id="404", description="Tool not found")
            return msg, 404
        if response.status_code != 200:
            adm.logger.error("Failed to fetch tool: %s", response.text)
            msg = Error(id="503", description="Failed to fetch tool")
            return msg, 503

        template = base64.b64decode(response.json().get("content").encode()).decode()
        if not version or version == "latest":
            version = response.json().get("sha")

        tool = self.get_tool_info({"path": repo_tool_id, "version": version,
                                   "template": template}, request)
        return tool, 200

    def _list(self, request: Request, from_: int, limit: int, user_info: dict) -> List[ToolInfo]:
        repo = Repository.create(self.url)
        res = []
        for _, elem in repo.list().items():
            tool = self.get_tool_info({"path": elem['path'], "version": elem['sha'],
                                       "template": repo.get(elem['path']).text}, request)
            res.append(tool)
        return res
