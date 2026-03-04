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

from typing import List, Union, Literal
from pydantic import BaseModel, Field, EmailStr, HttpUrl
from datetime import datetime


class ToolId(BaseModel):
    kind: Literal['ToolId'] = 'ToolId'
    id: str = Field(..., description="Unique identifier for this tool blueprint")
    version: str = 'latest'
    infoLink: HttpUrl | None = Field(None, description="URL that returns the full details of this tool blueprint")


class ToolInfo(BaseModel):
    kind: Literal['ToolInfo'] = 'ToolInfo'
    id: str
    nodeId: str = None
    type: Literal["vm", "container"]
    blueprint: str = Field(..., description="Blueprint of the tool's workload")
    blueprintType: Literal["tosca", "ansible", "helm"]
    name: str = None
    description: str = None
    published: bool = None
    favorite: bool = None
    authorName: str = None
    authorEmail: EmailStr = None
    organisation: str = None
    keywords: List[str] = []
    license: str = None
    version: str = None
    versionFrom: datetime = None
    versionLatest: datetime = None
    repository: HttpUrl = None
    helpdesk: HttpUrl = None
    validated: bool = False
    validatedOn: datetime = None
    self_: HttpUrl | None = Field(None, alias="self",
                                  description="Endpoint that returns the details of this tool blueprint")

    model_config = {"populate_by_name": True}


Tool = Union[ToolId, ToolInfo]
