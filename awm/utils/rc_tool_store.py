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


import yaml
import awm
import requests
from typing import Tuple, Union
from fastapi import Request
from urllib.parse import urlparse
from awm.models.tool import ToolInfo
from awm.models.error import Error
from awm.utils import RepositoryConnectionException


class ToolStore:

    def __init__(self, repo_url: str = "https://providers.sandbox.eosc-beyond.eu/api"):
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
    def _convert_url_to_raw(url: str) -> str:
        parsed = urlparse(url)
        # Only convert well-formed GitHub blob URLs with the expected host.
        if parsed.scheme == "https" and parsed.hostname == "github.com":
            # Expected path format: /{owner}/{repo}/blob/{path/to/file}
            path_parts = parsed.path.lstrip("/").split("/", 4)
            if len(path_parts) >= 4 and path_parts[2] == "blob":
                owner = path_parts[0]
                repo = path_parts[1]
                file_path = path_parts[3] if len(path_parts) == 4 else path_parts[3] + "/" + path_parts[4]
                return f"https://raw.githubusercontent.com/{owner}/{repo}/{file_path}"
        return url

    @staticmethod
    def _get_tool_info_from_repo(elem: dict, request: Request) -> ToolInfo:
        tosca = yaml.safe_load(requests.get(ToolStore._convert_url_to_raw(elem['url'])).text)
        metadata = tosca.get("metadata", {})
        tool_id = elem['id'].replace("/", "@")
        url = str(request.url_for("get_tool", tool_id=tool_id))
        if elem['version'] and elem['version'] != "latest":
            url += "?version=%s" % elem['version']
        tool = ToolInfo(
            id=tool_id,
            self_=url,
            version='latest',
            type=ToolStore.get_tool_type(tosca),
            name=metadata.get("template_name", ""),
            description=tosca.get("description", ""),
            blueprint=yaml.safe_dump(tosca),
            blueprintType="tosca"
        )
        if metadata.get("template_author"):
            tool.authorName = metadata.get("template_author")
        if elem.get('version'):
            tool.version = elem['version']
        return tool

    def get_tool_from_repo(self, tool_id: str, version: str, request: Request) -> Tuple[Union[ToolInfo, Error], int]:
        # tool_id was provided with underscores; convert back path
        repo_tool_id = tool_id.replace("@", "/")
        try:
            response = requests.get(f"{self.repo_url}/deployableService/{repo_tool_id}")
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

        tool = ToolStore._get_tool_info_from_repo(response.json(), request)
        return tool, 200

    def list_tools(self, request: Request, from_: int = 0, limit: int = 100):
        tools = []
        try:
            response = requests.get(f"{self.repo_url}/deployableService/all")
            tools_list = response.json().get("results")
        except Exception as e:
            raise RepositoryConnectionException("Failed to get list of Tools: %s" % e)

        count = 0
        total = len(tools_list)
        for elem in tools_list:
            count += 1
            if from_ > count - 1:
                continue
            try:
                tool = self._get_tool_info_from_repo(elem, request)
                tools.append(tool)
                if len(tools) >= limit:
                    break
            except Exception as ex:
                awm.logger.error("Failed to get tool info: %s", ex)

        return total, count, tools
