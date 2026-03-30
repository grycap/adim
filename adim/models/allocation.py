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

from typing import Any, Union, Literal, Annotated
from pydantic import BaseModel, Field, HttpUrl, RootModel, model_validator, model_serializer
from datetime import datetime

from pydantic_core import CoreSchema
from pydantic.json_schema import GetJsonSchemaHandler, JsonSchemaValue


class EoscNodeEnvironment_offer(BaseModel):
    offerId: str
    offerName: str | None = None
    offerType: Literal["openstack", "kubernetes"]
    cpus: int | None = Field(None, ge=1)
    gpus: int | None = None
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
    hostname: HttpUrl | None = None
    provisionedOn: datetime | None = None
    expiresOn: datetime | None = None
    nodeName: str | None = Field(None, description="Name of the EOSC node where this environment was allocated")
    nodeUI: HttpUrl | None = Field(None, description=("URL to the interactive UI of the EOSC node where "
                                                      "this environment was allocated"))
    nodeId: str = Field(..., description=("URL to the interactive UI of the EOSC "
                                          "node where this environment was allocated"))
    admApi: HttpUrl = Field(..., description=("Base URL for the ADM API of the EOSC node where this "
                                              "environment was allocated, or null for environments "
                                              "private to the calling user that accessed via explicit credentials"))


class OpenStackEnvironment(BaseModel):
    """Credentials for OpenStack"""
    kind: Literal['OpenStackEnvironment'] = 'OpenStackEnvironment'
    userName: str
    domain: str
    domainId: str | None = None
    tenant: str
    tenantId: str | None = None
    region: str | None = None
    host: HttpUrl
    authVersion: Literal['3.x-oidc'] = '3.x-oidc'
    apiVersion: str | None = None


class EGIComputeEnvironment(OpenStackEnvironment):
    """Credentials for EGI"""
    kind: Literal['EGIComputeEnvironment'] = 'EGIComputeEnvironment'
    userName: Literal["egi.eu"] = "egi.eu"
    domain: str = Field(..., description="The project name or ID of the EGI allocation")
    tenant: Literal["openid"] = "openid"
    authVersion: Literal['3.x-oidc'] = '3.x-oidc'


class KubernetesEnvironment(BaseModel):
    """Credentials for Kubernetes"""
    kind: Literal['KubernetesEnvironment'] = 'KubernetesEnvironment'
    host: HttpUrl
    namespace: str | None = Field(None, description="Kubernetes namespace where applications should be deployed")
    apps_dns: str | None = Field(None, description="DNS domain for applications deployed "
                                 "in this Kubernetes environment")


class DummyEnvironment(BaseModel):
    """Dummy environment for testing purposes"""
    kind: Literal['DummyEnvironment'] = 'DummyEnvironment'


AllocationValue = Annotated[
    Union[
        DummyEnvironment,
        OpenStackEnvironment,
        EGIComputeEnvironment,
        KubernetesEnvironment,
        EoscNodeEnvironment,
    ],
    Field(discriminator='kind'),
]


class Allocation(RootModel[AllocationValue]):
    root: AllocationValue

    def __getattr__(self, name: str) -> Any:
        return getattr(self.root, name)

    def model_dump(self, *args, **kwargs):
        return self.root.model_dump(*args, **kwargs)


class AllocationId(BaseModel):
    kind: Literal['AllocationId'] = 'AllocationId'
    id: str = Field(..., description="Unique identifier for this allocation")
    infoLink: HttpUrl = Field(..., description="Endpoint that returns more details about this entity")


# This model is used because the API response for AllocationInfo includes both the allocation data
# and some metadata (id and self link), and we want to be able to serialize/deserialize it in a flat
# way (i.e., with the allocation fields at the top level, together with id and self).
class AllocationInfo(BaseModel):
    allocation: Allocation
    id: str = Field(..., description="Unique identifier for this allocation")
    self_: HttpUrl = Field(..., alias="self", description="Endpoint that returns more details about this entity")

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def _from_flat_payload(cls, value: Any) -> Any:
        if isinstance(value, cls):
            return value

        if not isinstance(value, dict):
            return value

        data = dict(value)
        if "allocation" in data:
            if "self_" in data and "self" not in data:
                data["self"] = data.pop("self_")
            return data

        parsed = {
            "allocation": {
                key: val
                for key, val in data.items()
                if key not in {"id", "self", "self_"}
            }
        }
        if "id" in data:
            parsed["id"] = data["id"]
        if "self" in data:
            parsed["self"] = data["self"]
        elif "self_" in data:
            parsed["self"] = data["self_"]

        return parsed

    @model_serializer(mode="wrap")
    def _serialize_flat(self, handler):
        data = handler(self)
        allocation_data = data.pop("allocation", {})
        return {**allocation_data, **data}

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        json_schema = handler(core_schema)
        resolved_schema = handler.resolve_ref_schema(json_schema)
        properties = resolved_schema.get("properties", {})
        allocation_schema = properties.get("allocation", {"$ref": "#/components/schemas/Allocation"})

        return {
            "title": "AllocationInfo",
            "allOf": [
                allocation_schema,
                {
                    "type": "object",
                    "properties": {
                        "id": properties.get("id", {"type": "string"}),
                        "self": properties.get("self", {"type": "string", "format": "uri"}),
                    },
                    "required": ["id", "self"],
                },
            ],
        }

    def __getattr__(self, name: str) -> Any:
        return getattr(self.allocation, name)

    @property
    def value(self) -> Allocation:
        return self.allocation
