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
from typing import Tuple, Union, List
from fastapi import Request
from urllib.parse import urlparse
from awm.models.tool import ToolInfo
from awm.models.error import Error
from awm.utils import ConnectionException
from .tool_store import ToolStore


class ToolStoreRC(ToolStore):

    def __init__(self, url: str = "https://providers.sandbox.eosc-beyond.eu/api"):
        super().__init__(url)

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
    def get_tool_info(elem: dict, request: Request) -> ToolInfo:
        tosca = yaml.safe_load(requests.get(ToolStoreRC._convert_url_to_raw(elem['url'])).text)
        metadata = tosca.get("metadata", {})
        tool_id = elem['id'].replace("/", "@")
        url = str(request.url_for("get_tool", tool_id=tool_id))
        url += "?version=%s" % elem['version']
        tool = ToolInfo(
            id=tool_id,
            self_=url,
            version='latest',
            type=ToolStore.get_tool_type(tosca),
            name=elem.get("name", metadata.get("template_name", "")),
            description=elem.get("description", tosca.get("description", "")),
            blueprint=yaml.safe_dump(tosca),
            blueprintType="tosca"
        )
        if elem.get("creators"):
            creator = elem["creators"][0].get("creatorNameTypeInfo", {}).get("creatorName")
            if creator:
                tool.authorName = creator
            if elem["creators"][0].get("creatorAffiliationInfo"):
                tool.organisation = elem["creators"][0].get("creatorAffiliationInfo").get("affiliation")
        elif metadata.get("template_author"):
            tool.authorName = metadata.get("template_author")

        if elem.get("node"):
            tool.nodeId = elem["node"]
        if elem.get('version'):
            tool.version = elem['version']
        if elem.get('softwareLicense'):
            tool.license = elem['softwareLicense']
        return tool

    def get_tool(self, tool_id: str, version: str, request: Request,
                 user_info: dict = None) -> Tuple[Union[ToolInfo, Error], int]:
        # tool_id was provided with underscores; convert back path
        repo_tool_id = tool_id.replace("@", "/")
        try:
            response = requests.get(f"{self.url}/deployableService/{repo_tool_id}")
        except Exception as e:
            awm.logger.error("Failed to get tool info: %s", e)
            raise ConnectionException("Failed to get tool info: %s" % e)

        if response.status_code == 404:
            msg = Error(id="404", description="Tool not found")
            return msg, 404
        if response.status_code != 200:
            awm.logger.error("Failed to fetch tool: %s", response.text)
            msg = Error(id="503", description="Failed to fetch tool")
            return msg, 503

        tool = self.get_tool_info(response.json(), request)
        return tool, 200

    def _list(self, request: Request, from_: int, limit: int, user_info: dict) -> List[ToolInfo]:
        response = requests.get(f"{self.url}/deployableService/all")
        response.raise_for_status()
        res = []
        for elem in response.json().get("results", []):
            tool = self.get_tool_info(elem, request)
            res.append(tool)
        return res
