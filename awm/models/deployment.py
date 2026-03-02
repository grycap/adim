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

from typing import Literal, Dict, Any, List
from pydantic import BaseModel, Field, HttpUrl, RootModel
from awm.models.allocation import AllocationId
from awm.models.tool import ToolId


class DeploymentId(BaseModel):
    id: str = Field(..., description="Unique identifier for this deployment")
    kind: Literal["DeploymentId"] = "DeploymentId"
    infoLink: HttpUrl | None = Field(None, description="Endpoint that returns more details about this entity")


class Deployment(BaseModel):
    allocation: AllocationId
    tool: ToolId
    inputs: Dict[str, Any] | None = Field(None, description="Input values for the template",
                                          json_schema_extra={"type": "object", "additionalProperties": {}})


class DeploymentInfo(BaseModel):
    deployment: Deployment
    id: str = Field(..., description="Unique identifier for this tool blueprint")
    status: Literal["unknown",
                    "pending",
                    "running",
                    "stopped",
                    "off",
                    "failed",
                    "configured",
                    "unconfigured",
                    "deleting",
                    "deleted"]
    details: str | None = Field(None, description="Additional information about the deployment status")
    outputs: Dict[str, Any] | None = Field(None, description="Deployed Template output values",
                                           json_schema_extra={"type": "object", "additionalProperties": {}})
    self_: HttpUrl | None = Field(None, alias="self",
                                  description="Endpoint that returns the details of this tool blueprint")

    model_config = {"populate_by_name": True}


class Quota(BaseModel):
    used: int | float | None = Field(None, description="Amount of the resource currently used")
    limit: int | float | None = Field(None, description="Maximum amount of the resource available")
    to_use: int | float | None = Field(None, description="Amount of the resources the user needs with the deployment")


class CloudQuota(BaseModel):
    cores: Quota = Field(..., description="CPU cores quota")
    memory: Quota = Field(..., alias="ram", description="Memory quota in megabytes")
    gpus: Quota | None = Field(None, description="GPU units quota")
    instances: Quota = Field(..., description="Number of instances quota")
    floating_ips: Quota | None = Field(None, description="Number of floating IPs quota")
    security_groups: Quota | None = Field(None, description="Number of security groups quota")
    volumes: Quota | None = Field(None, description="Number of volumes quota")
    volume_storage: Quota | None = Field(None, description="Storage in gigabytes quota for volumes")
