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
    used: int | float = Field(..., description="Amount of the resource currently used")
    limit: int | float = Field(..., description="Maximum amount of the resource available")


class CloudQuota(BaseModel):
    cores: Quota = Field(..., description="CPU cores quota")
    memory: Quota = Field(..., alias="ram", description="Memory quota in megabytes")
    gpus: Quota | None = Field(None, description="GPU units quota")
    instances: Quota = Field(..., description="Number of instances quota")
    floating_ips: Quota | None = Field(None, description="Number of floating IPs quota")
    security_groups: Quota | None = Field(None, description="Number of security groups quota")
    volumes: Quota | None = Field(None, description="Number of volumes quota")
    volume_storage: Quota | None = Field(None, description="Storage in gigabytes quota for volumes")


class ComputeResource(BaseModel):
    cpuCores: float = Field(..., description="Number of CPU cores")
    memoryInMegabytes: float = Field(..., description="Amount of memory in megabytes")
    diskSizeInGigabytes: float | None = Field(None, description="Disk size in gigabytes")
    publicIP: int | None = Field(None, description="Number of public IPs")
    GPU: float | None = Field(None, description="Number of GPU units")


class StorageResource(BaseModel):
    sizeInGigabytes: float = Field(..., description="Storage size in gigabytes")
    type: str | None = Field(None, description="Type of storage (e.g. SSD, CEPH, etc.)")


class CloudResource(BaseModel):
    cloudType: str = Field(..., description="Type of the cloud resource (e.g. OpenStack, Kubernetes, etc.)")
    cloudEndpoint: HttpUrl = Field(..., description="Endpoint of the cloud resource")
    compute: List[ComputeResource] = Field(..., description="List of compute resources")
    storage: List[StorageResource] | None = Field(None, description="List of storage resources")
    quotas: CloudQuota | None = Field(None, description="Quotas for the cloud resource")


class DeploymentResources(RootModel[Dict[str, CloudResource]]):
    pass
