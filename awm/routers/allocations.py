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

import os
import awm
import json
from fastapi import APIRouter, Query, Depends, Request, Response
from awm.authorization import authenticate
from awm.models.allocation import AllocationInfo, Allocation, AllocationId
from awm.models.page import PageOfAllocations
from awm.models.error import Error
from awm.models.success import Success
from awm.utils.node_registry import EOSCNodeRegistry
from . import return_error


router = APIRouter()
ALLOCATION_STORE = os.getenv("ALLOCATION_STORE", "db")

if ALLOCATION_STORE == "db":
    from awm.utils.allocation_store_db import AllocationStoreDB
    DB_URL = os.getenv("DB_URL", AllocationStoreDB.DEFAULT_URL)
    allocation_store = AllocationStoreDB(DB_URL)
elif ALLOCATION_STORE == "vault":
    from awm.utils.allocation_store_vault import AllocationStoreVault
    VAULT_URL = os.getenv("VAULT_URL", AllocationStoreVault.DEFAULT_URL)
    ENCRYPT_KEY = os.getenv("ENCRYPT_KEY", AllocationStoreVault.DEFAULT_KEY)
    allocation_store = AllocationStoreVault(VAULT_URL, key=ENCRYPT_KEY)
else:
    raise Exception(f"Allocation store '{ALLOCATION_STORE}' is not supported")


# GET /allocations
@router.get("/allocations",
            summary="List all credentials or EOSC environments of the user",
            responses={200: {"model": PageOfAllocations,
                             "description": "Success"},
                       400: {"model": Error,
                             "description": "Invalid parameters or configuration"},
                       401: {"model": Error,
                             "description": "Authorization required"},
                       403: {"model": Error,
                             "description": "Forbidden"},
                       419: {"model": Error,
                             "description": "Re-delegate credentials"},
                       503: {"model": Error,
                             "description": "Try again later"}})
def list_allocations(
    request: Request,
    from_: int = Query(0, alias="from", ge=0,
                       description="Index of the first element to return"),
    limit: int = Query(100, alias="limit", ge=1,
                       description="Maximum number of elements to return"),
    all_nodes: bool = Query(False, alias="allNodes"),
    user_info=Depends(authenticate)
):
    try:
        count, allocations = allocation_store.list_allocations(user_info, from_, limit)
    except Exception as ex:
        return return_error(str(ex), 503)

    res = []
    for elem in allocations:
        allocation_id = elem['id']
        allocation_data = elem['data']
        allocation = Allocation.model_validate(allocation_data)
        allocation_info = AllocationInfo(
            id=allocation_id,
            self_=str(request.url_for("get_allocation", allocation_id=allocation_id)),
            allocation=allocation
        )
        res.append(allocation_info)

    if all_nodes:
        remote_count, remote_tools = EOSCNodeRegistry.list_allocations(from_, limit, count, user_info)
        res.extend(remote_tools)
        count += remote_count

    page = PageOfAllocations(from_=from_, limit=limit, elements=res, count=count)
    page.set_next_and_prev_pages(request, all_nodes)
    return Response(content=page.model_dump_json(exclude_unset=True, by_alias=True),
                    status_code=200, media_type="application/json")


def _get_allocation(allocation_id: str, user_info: dict, request: Request) -> AllocationInfo:
    try:
        allocation_data = allocation_store.get_allocation(allocation_id, user_info)
    except Exception as ex:
        return return_error(str(ex), 503)

    allocation = Allocation.model_validate(allocation_data)
    allocation_info = AllocationInfo(
        id=allocation_id,
        self_=str(request.url_for("get_allocation", allocation_id=allocation_id)),
        allocation=allocation
    )
    return allocation_info


# GET /allocation/{allocation_id}
@router.get("/allocation/{allocation_id}",
            summary="Get information about an existing deployment",
            responses={200: {"model": AllocationInfo,
                             "description": "Accepted"},
                       400: {"model": Error,
                             "description": "Invalid parameters or configuration"},
                       401: {"model": Error,
                             "description": "Authorization required"},
                       403: {"model": Error,
                             "description": "Forbidden"},
                       404: {"model": Error,
                             "description": "Not found"},
                       419: {"model": Error,
                             "description": "Re-delegate credentials"},
                       503: {"model": Error,
                             "description": "Try again later"}})
def get_allocation(request: Request,
                   allocation_id,
                   user_info=Depends(authenticate)):
    """Get information about an existing allocation

    :rtype: AllocationInfo
    """
    allocation_info = _get_allocation(allocation_id, user_info, request)
    if allocation_info is None:
        return return_error("Allocation not found", status_code=404)

    return Response(content=allocation_info.model_dump_json(exclude_unset=True, by_alias=True),
                    status_code=200, media_type="application/json")


def _check_allocation_in_use(allocation_id: str, user_info: dict, request: Request) -> Response:
    # check if this allocation is used in any deployment
    response = awm.routers.deployments._list_deployments(user_info=user_info, request=request)
    if response.status_code != 200:
        return response

    for dep_info in json.loads(response.body).get("elements"):
        if dep_info.get('deployment', {}).get('allocation', {}).get('id') == allocation_id:
            return return_error("Allocation in use", 409)

    return None


# PUT /allocation/{allocation_id}
@router.put("/allocation/{allocation_id}",
            summary="Update existing environment of the user",
            responses={200: {"model": AllocationInfo,
                             "description": "Updated"},
                       400: {"model": Error,
                             "description": "Invalid parameters or configuration"},
                       401: {"model": Error,
                             "description": "Authorization required"},
                       403: {"model": Error,
                             "description": "Forbidden"},
                       419: {"model": Error,
                             "description": "Re-delegate credentials"},
                       503: {"model": Error,
                             "description": "Try again later"}})
def update_allocation(allocation_id,
                      allocation: Allocation,
                      request: Request,
                      user_info=Depends(authenticate)):
    allocation_info = _get_allocation(allocation_id, user_info, request)
    if allocation_info is None:
        return return_error("Allocation not found", status_code=404)

    # check if this allocation is used in any deployment
    response = _check_allocation_in_use(allocation_id, user_info, request)
    if response:
        return response

    data = allocation.model_dump(exclude_unset=True, mode="json")
    try:
        allocation_store.replace_allocation(data, user_info, allocation_id)
    except Exception as ex:
        return return_error(str(ex), 503)

    allocation_info = _get_allocation(allocation_id, user_info, request)
    return Response(content=allocation_info.model_dump_json(exclude_unset=True, by_alias=True),
                    status_code=200, media_type="application/json")


# DELETE /allocation/{allocation_id}
@router.delete("/allocation/{allocation_id}",
               summary="Remove existing environment of the user",
               responses={204: {"description": "Accepted"},
                          400: {"model": Error,
                                "description": "Invalid parameters or configuration"},
                          401: {"model": Error,
                                "description": "Authorization required"},
                          403: {"model": Error,
                                "description": "Forbidden"},
                          404: {"model": Error,
                                "description": "Not found"},
                          419: {"model": Error,
                                "description": "Re-delegate credentials"},
                          503: {"model": Error,
                                "description": "Try again later"}})
def delete_allocation(allocation_id,
                      request: Request,
                      user_info=Depends(authenticate)):
    """Remove existing environment of the user

    :rtype: Success
    """
    allocation_info = _get_allocation(allocation_id, user_info, request)
    if allocation_info is None:
        return return_error("Allocation not found", status_code=404)

    # check if this allocation is used in any deployment
    response = _check_allocation_in_use(allocation_id, user_info, request)
    if response:
        return response

    try:
        allocation_store.delete_allocation(allocation_id, user_info)
    except Exception as ex:
        return return_error(str(ex), 503)

    msg = Success(message="Deleted")
    return Response(content=msg.model_dump_json(exclude_unset=True),
                    status_code=200,
                    media_type="application/json")


# POST /allocations
@router.post("/allocations",
             summary="Record an environment of the user",
             responses={201: {"model": AllocationId,
                              "description": "Accepted"},
                        400: {"model": Error,
                              "description": "Invalid parameters or configuration"},
                        401: {"model": Error,
                              "description": "Authorization required"},
                        403: {"model": Error,
                              "description": "Forbidden"},
                        419: {"model": Error,
                              "description": "Re-delegate credentials"},
                        503: {"model": Error,
                              "description": "Try again later"}})
def create_allocation(allocation: Allocation,
                      request: Request,
                      user_info=Depends(authenticate)):
    """Record an environment of the user
    :rtype: AllocationId
    """
    data = allocation.model_dump(exclude_unset=True, mode="json")
    try:
        allocation_id = allocation_store.replace_allocation(data, user_info)
    except Exception as ex:
        return return_error(str(ex), 503)

    url = str(request.url_for("get_allocation", allocation_id=allocation_id))
    allocation_id_model = AllocationId(id=allocation_id, infoLink=url)
    return Response(content=allocation_id_model.model_dump_json(exclude_unset=True, by_alias=True),
                    status_code=201, media_type="application/json")
