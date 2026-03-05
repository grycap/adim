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

import adim
from fastapi import APIRouter, Query, Depends, Request, Response
from adim.authorization import authenticate
from adim.models.allocation import AllocationInfo, Allocation, AllocationId
from adim.models.page import PageOfAllocations
from adim.models.success import Success
from adim.utils.node_registry import EOSCNodeRegistry
from adim.utils import ConnectionException
from . import return_error, STANDARD_RESPONSES, GET_RESPONSES, DELETE_RESPONSES, POST_RESPONSES


router = APIRouter()


# GET /allocations
@router.get("/allocations",
            summary="List all credentials or EOSC environments of the user",
            responses=STANDARD_RESPONSES(PageOfAllocations))
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
        adim.logger.debug(f"Listing allocations from user '{user_info.get('sub')}'")
        count, allocations = adim.allocation_store.list_allocations(user_info, from_, limit)
    except Exception as ex:
        return return_error(str(ex), 503)

    res = []
    for elem in allocations:
        allocation = Allocation.model_validate(elem['data'])
        allocation_info = AllocationInfo(
            id=elem['id'],
            self_=str(request.url_for("get_allocation", allocation_id=elem['id'])),
            allocation=allocation
        )
        res.append(allocation_info)

    if all_nodes:
        adim.logger.debug(f"Listing allocations in all EOSC nodes for user '{user_info.get('sub')}'")
        remote_count, remote_tools = EOSCNodeRegistry.list_allocations(from_, limit, count, user_info)
        res.extend(remote_tools)
        count += remote_count

    page = PageOfAllocations(from_=from_, limit=limit, elements=res, count=count)
    page.set_next_and_prev_pages(request, all_nodes)
    return Response(content=page.model_dump_json(exclude_unset=True, exclude_none=True, by_alias=True),
                    status_code=200, media_type="application/json")


def _get_allocation_info(allocation_id: str, user_info: dict, request: Request) -> AllocationInfo:
    try:
        allocation_data = adim.allocation_store.get_allocation(allocation_id, user_info)
    except ConnectionException as ex:
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
            responses=GET_RESPONSES(AllocationInfo))
def get_allocation(request: Request,
                   allocation_id,
                   user_info=Depends(authenticate)):
    """Get information about an existing allocation"""
    adim.logger.debug(f"Getting allocation {allocation_id} from user '{user_info.get('sub')}'")
    allocation_info = _get_allocation_info(allocation_id, user_info, request)
    if allocation_info is None:
        return return_error("Allocation not found", status_code=404)

    return Response(content=allocation_info.model_dump_json(exclude_unset=True, exclude_none=True, by_alias=True),
                    status_code=200, media_type="application/json")


def _check_allocation_in_use(allocation_id: str, user_info: dict) -> Response | None:
    # check if this allocation is used in any deployment
    try:
        _, deployments = adim.deployments_manager.list_deployments(limit=999999999, user_info=user_info)
    except ConnectionException:
        return return_error("Database connection failed", 503)

    for dep_info in deployments:
        if dep_info.deployment.allocation.id == allocation_id:
            return return_error("Allocation in use", 409)

    return None


# PUT /allocation/{allocation_id}
@router.put("/allocation/{allocation_id}",
            summary="Update existing environment of the user",
            responses=GET_RESPONSES(AllocationInfo))
def update_allocation(allocation_id,
                      allocation: Allocation,
                      request: Request,
                      user_info=Depends(authenticate)):
    adim.logger.debug(f"Update allocation {allocation_id} from user '{user_info.get('sub')}'")
    allocation_info = _get_allocation_info(allocation_id, user_info, request)
    if allocation_info is None:
        return return_error("Allocation not found", status_code=404)

    # check if this allocation is used in any deployment
    response = _check_allocation_in_use(allocation_id, user_info)
    if response:
        return response

    data = allocation.model_dump(exclude_unset=True, mode="json")
    try:
        adim.allocation_store.replace_allocation(data, user_info, allocation_id)
    except Exception as ex:
        return return_error(str(ex), 503)

    allocation_info = _get_allocation_info(allocation_id, user_info, request)
    return Response(content=allocation_info.model_dump_json(exclude_unset=True, exclude_none=True, by_alias=True),
                    status_code=200, media_type="application/json")


# DELETE /allocation/{allocation_id}
@router.delete("/allocation/{allocation_id}",
               summary="Remove existing environment of the user",
               response_model=Success,
               responses=DELETE_RESPONSES(200))
def delete_allocation(allocation_id,
                      user_info=Depends(authenticate)):
    """Remove existing environment of the user"""
    adim.logger.debug(f"Delete allocation {allocation_id} from user '{user_info.get('sub')}'")
    if not adim.allocation_store.get_allocation(allocation_id, user_info):
        return return_error("Allocation not found", status_code=404)

    # check if this allocation is used in any deployment
    response = _check_allocation_in_use(allocation_id, user_info)
    if response:
        return response

    try:
        adim.allocation_store.delete_allocation(allocation_id, user_info)
    except ConnectionException as ex:
        return return_error(str(ex), 503)

    msg = Success(message="Deleted")
    return Response(content=msg.model_dump_json(exclude_unset=True),
                    status_code=200,
                    media_type="application/json")


# POST /allocations
@router.post("/allocations",
             summary="Record an environment of the user",
             responses=POST_RESPONSES(AllocationId, 201),
             response_model=AllocationId,
             status_code=201)
def create_allocation(allocation: Allocation,
                      request: Request,
                      user_info=Depends(authenticate)):
    """Record an environment of the user"""
    adim.logger.debug(f"Create allocation from user '{user_info.get('sub')}'")
    data = allocation.model_dump(exclude_unset=True, mode="json")
    adim.logger.debug(f"Allocation data: {allocation.model_dump()}")

    found_id = adim.allocation_store.check_allocation_exists(data, user_info)
    if found_id:
        url = str(request.url_for("get_allocation", allocation_id=found_id))
        return Response(status_code=303, media_type="application/json",
                        headers={"Location": url})

    try:
        allocation_id = adim.allocation_store.replace_allocation(data, user_info)
    except Exception as ex:
        return return_error(str(ex), 503)

    url = str(request.url_for("get_allocation", allocation_id=allocation_id))
    allocation_id_model = AllocationId(id=allocation_id, infoLink=url)
    return Response(content=allocation_id_model.model_dump_json(exclude_unset=True, by_alias=True),
                    status_code=201, media_type="application/json")
