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

from typing import Union, Literal, Annotated
from pydantic import BaseModel, Field, HttpUrl, RootModel
from datetime import datetime


class EoscNodeEnvironment_offer(BaseModel):
    offerId: str
    offerName: str = None
    offerType: Literal["openstack", "kubernetes"]
    cpus: int | None = Field(None, ge=1)
    gpus: int = None
    memory: int | None = Field(None, ge=1, description=("RAM quota in GB"))
    fastStorage: int | None = Field(None, description=("SSD or NVMe based (fast) storage quota in GB"))
    bulkStorage: int | None = Field(None, description=("HDD based (slow) storage quota in GB"))
    s3Storage: int | None = Field(None, description=("S3 storage quota in GB"))
    registryStorage: int | None = Field(None, description=("Container Registry storage quota in GB"))
    creditsPerDay: int = Field(..., ge=1, description=("Credits per day"))


class EoscNodeEnvironment(BaseModel):
    """Environment variables for EOSC node"""
    kind: Literal['EoscNodeEnvironment'] = 'EoscNodeEnvironment'
    offer: EoscNodeEnvironment_offer
    projectId: str
    hostname: HttpUrl = None
    provisionedOn: datetime = None
    expiresOn: datetime = None
    nodeName: str | None = Field(None, description="Name of the EOSC node where this environment was allocated")
    nodeId: str = Field(..., description=("URL to the interactive UI of the EOSC "
                                          "node where this environment was allocated"))
    awmApi: HttpUrl = Field(..., description=("Base URL for the AWM API of the EOSC node where this "
                                              "environment was allocated, or null for environments "
                                              "private to the calling user that accessed via explicit credentials"))


class OpenStackEnvironment(BaseModel):
    """Credentials for OpenStack"""
    kind: Literal['OpenStackEnvironment'] = 'OpenStackEnvironment'
    userName: str
    domain: str
    domainId: str = None
    tenant: str
    tenantId: str = None
    region: str = None
    host: HttpUrl
    authVersion: Literal['3.x-oidc'] = '3.x-oidc'
    apiVersion: str = None


class KubernetesEnvironment(BaseModel):
    """Credentials for Kubernetes"""
    kind: Literal['KubernetesEnvironment'] = 'KubernetesEnvironment'
    host: HttpUrl


AllocationUnion = Annotated[
    Union[OpenStackEnvironment,
          KubernetesEnvironment,
          EoscNodeEnvironment],
    Field(discriminator='kind')
]


class Allocation(RootModel[AllocationUnion]):
    pass


class AllocationId(BaseModel):
    kind: Literal['AllocationId'] = 'AllocationId'
    id: str = Field(..., description="Unique identifier for this allocation")
    infoLink: HttpUrl | None = Field(None, description="Endpoint that returns more details about this entity")


class AllocationInfo(BaseModel):
    id: str = Field(..., description="Unique identifier for this allocation")
    self_: HttpUrl | None = Field(None, alias="self",
                                  description="Endpoint that returns the details of this allocation")
    allocation: Allocation

    model_config = {"populate_by_name": True}
