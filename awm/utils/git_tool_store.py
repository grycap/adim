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
import awm
from typing import Tuple, Union
from fastapi import Request
from awm.models.tool import ToolInfo
from awm.models.error import Error
from awm.utils.repository import Repository
from awm.utils import RepositoryConnectionException


class ToolStore:

    def __init__(self, repo_url: str):
        self.repo_url = repo_url

    @staticmethod
    def get_tool_type(tosca: dict) -> str:
        try:
            node_templates = tosca.get('topology_template', {}).get('node_templates', {})
            for _, node in node_templates.items():
                if node.get('type', '') == 'tosca.nodes.Container.Application.Docker':
                    return "container"
        except Exception:
            awm.logger.exception("Error getting tool type using default 'vm'")
        return "vm"

    @staticmethod
    def _get_tool_info_from_repo(elem: str, path: str, version: str, request: Request) -> ToolInfo:
        tosca = yaml.safe_load(elem)
        metadata = tosca.get("metadata", {})
        tool_id = path.replace("/", "@")
        url = str(request.url_for("get_tool", tool_id=tool_id))
        if version and version != "latest":
            url += "?version=%s" % version
        tool = ToolInfo(
            id=tool_id,
            self_=url,
            version='latest',
            type=ToolStore.get_tool_type(tosca),
            name=metadata.get("template_name", ""),
            description=tosca.get("description", ""),
            blueprint=elem,
            blueprintType="tosca"
        )
        if metadata.get("template_author"):
            tool.authorName = metadata.get("template_author")
        if version:
            tool.version = version
        return tool

    def get_tool_from_repo(self, tool_id: str, version: str, request: Request) -> Tuple[Union[ToolInfo, Error], int]:
        # tool_id was provided with underscores; convert back path
        repo_tool_id = tool_id.replace("@", "/")
        try:
            repo = Repository.create(self.repo_url)
            response = repo.get(repo_tool_id, version, details=True)
        except Exception as e:
            awm.logger.error("Failed to get tool info: %s", e)
            raise RepositoryConnectionException("Failed to get tool info: %s" % e)

        if response.status_code == 404:
            msg = Error(id="404", description="Tool not found")
            return msg, 404
        if response.status_code != 200:
            awm.logger.error("Failed to fetch tool: %s", response.text)
            msg = Error(id="503", description="Failed to fetch tool")
            return msg, 503

        template = base64.b64decode(response.json().get("content").encode()).decode()
        if not version or version == "latest":
            version = response.json().get("sha")

        tool = ToolStore._get_tool_info_from_repo(template, repo_tool_id, version, request)
        return tool, 200

    def list_tools(self, request: Request, from_: int = 0, limit: int = 100):
        tools = []
        try:
            repo = Repository.create(self.repo_url)
            tools_list = repo.list()
        except Exception as e:
            raise RepositoryConnectionException("Failed to get list of Tools: %s" % e)

        count = 0
        total = len(tools_list)
        for _, elem in tools_list.items():
            count += 1
            if from_ > count - 1:
                continue
            try:
                tool = self._get_tool_info_from_repo(repo.get(elem['path']).text, elem['path'], elem['sha'], request)
                tools.append(tool)
                if len(tools) >= limit:
                    break
            except Exception as ex:
                awm.logger.error("Failed to get tool info: %s", ex)

        return total, count, tools
