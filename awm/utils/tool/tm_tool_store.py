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
from typing import Tuple, Union, List
from fastapi import Request
from awm.models.tool import ToolInfo
from awm.models.error import Error
from .tool_store import ToolStore


class ToolStoreTM(ToolStore):

    def __init__(self, url: str = "https://api.open-science-cloud.ec.europa.eu"):
        super().__init__(url)

    @staticmethod
    def get_tool_info(elem: dict, request: Request) -> ToolInfo:
        pid = elem.get("pid").replace("/", "@")
        url = f"{request.base_url}{request.url.path[1:]}{pid}"
        tool = ToolInfo(id=pid,
                        self_=url,
                        type=ToolStore.get_tool_type(elem.get("toscaFile")),
                        name=elem.get("name"),
                        description=elem.get("description"),
                        blueprint=elem.get("toscaFile"),
                        blueprint_type="tosca",
                        author_name=elem.get("author"),)
        return tool

    def get_tool(self, tool_id: str, version: str, request: Request,
                 user_info: dict = None) -> Tuple[Union[ToolInfo, Error], int]:
        # tool_id was provided with @; convert back path
        tool_id = tool_id.replace("@", "%2F")
        response = requests.get(f"{self.url}/tools/api/v1/by-pid/{tool_id}",
                                headers={"Authorization": f"Bearer {user_info['token']}"},
                                timeout=10)

        # If the tool is not found it returns 200 with an empty body,
        # so we need to check if the pid is present in the response
        tool_info = response.json()
        if tool_info.get("pid") is None:
            msg = Error(description="Tool not found")
            return msg.model_dump_json(), 404

        tool = self.get_tool_info(tool_info, request)
        return tool, 200

    def _list(self, request: Request, from_: int, limit: int, user_info: dict) -> List[ToolInfo]:
        response = requests.get(f"{self.url}/tools/api/v1?pageSize={limit}&from={from_}",
                                headers={"Authorization": f"Bearer {user_info['token']}"},
                                timeout=10)
        response.raise_for_status()
        res = []
        for elem in response.json().get("content", []):
            tool = self.get_tool_info(elem, request)
            res.append(tool)
        return res
