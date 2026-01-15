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
from fastapi import APIRouter, Query, Depends, Request, Response
from awm.authorization import authenticate
from awm.models.deployment import DeploymentInfo, DeploymentId, Deployment
from awm.models.page import PageOfDeployments
from awm.models.error import Error
from awm.models.allocation import Allocation
from awm.utils.node_registry import EOSCNodeRegistry
from awm.utils.deployment_manager import DeploymentsManager
from awm.utils import ConnectionException, DBConnectionException
from awm.routers.tools import tool_store
from awm.routers.allocations import allocation_store

from . import return_error


router = APIRouter()
IM_URL = os.getenv("IM_URL", "http://localhost:8800")
DB_URL = os.getenv("DB_URL", "file:///tmp/awm.db")


deployments_manager = DeploymentsManager(DB_URL, IM_URL)


def _list_deployments(from_: int = 0, limit: int = 100,
                      all_nodes: bool = False,
                      user_info: dict = None, request: Request = None) -> Response:
    try:
        count, deployments = deployments_manager.list_deployments(from_, limit, user_info)
    except DBConnectionException:
        return return_error("Database connection failed", 503)

    if all_nodes:
        remote_count, remote_tools = EOSCNodeRegistry.list_deployments(from_, limit, count, user_info)
        deployments.extend(remote_tools)
        count += remote_count

    page = PageOfDeployments(from_=from_, limit=limit, elements=deployments, count=count, self_=str(request.url))
    page.set_next_and_prev_pages(request, all_nodes)
    return Response(content=page.model_dump_json(exclude_unset=True, by_alias=True),
                    status_code=200, media_type="application/json")


# GET /deployments
@router.get("/deployments",
            summary="List existing deployments",
            responses={200: {"model": PageOfDeployments,
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
def list_deployments(
    request: Request,
    from_: int = Query(0, alias="from", ge=0,
                       description="Index of the first element to return"),
    limit: int = Query(100, alias="limit", ge=1,
                       description="Maximum number of elements to return"),
    all_nodes: bool = Query(False, alias="allNodes"),
    user_info=Depends(authenticate)
):
    return _list_deployments(from_, limit, all_nodes, user_info, request)


# GET /deployment/{deployment_id}
@router.get("/deployment/{deployment_id}",
            summary="Get information about an existing deployment",
            responses={200: {"model": DeploymentInfo,
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
def get_deployment(deployment_id,
                   user_info=Depends(authenticate)):
    """Get information about an existing deployment"""
    deployment, status_code = deployments_manager.get_deployment(deployment_id, user_info, True)
    return Response(content=deployment.model_dump_json(exclude_unset=True, by_alias=True),
                    status_code=status_code, media_type="application/json")


# DELETE /deployment/{deployment_id}
@router.delete("/deployment/{deployment_id}",
               summary="Tear down an existing deployment",
               responses={202: {"description": "Deleting"},
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
def delete_deployment(deployment_id,
                      user_info=Depends(authenticate)):
    """Tear down an existing deployment"""
    res, status_code = deployments_manager.delete_deployment(deployment_id, user_info)
    return Response(content=res.model_dump_json(exclude_unset=True), status_code=status_code, media_type="application/json")


# POST /deployments
@router.post("/deployments",
             summary="Deploy workload to an EOSC environment or an infrastructure for which the user has credentials",
             responses={202: {"model": DeploymentId,
                              "description": "Deploying"},
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
def deploy_workload(deployment: Deployment,
                    request: Request,
                    user_info=Depends(authenticate)):
    """Deploy workload to an EOSC environment or an infrastructure for which the user has credentials"""
    # Get the Tool from the ID
    tool, status_code = tool_store.get_tool_from_repo(deployment.tool.id, deployment.tool.version, request)
    if status_code != 200:
        return Response(content=tool, status_code=400, media_type="application/json")

    # Get the allocation info from the Allocation
    try:
        allocation_data = allocation_store.get_allocation(deployment.allocation.id, user_info)
    except ConnectionException as ex:
        return return_error(str(ex), 503)
    if not allocation_data:
        return return_error("Invalid AllocationId.", status_code=400)
    allocation = Allocation.model_validate(allocation_data)

    if allocation.root.kind == "EoscNodeEnvironment":
        raise NotImplementedError("EOSCNodeEnvironment support not implemented yet")

    try:
        deployment_info = deployments_manager.update_deployment(deployment, tool, allocation,
                                                                user_info, request)
    except DBConnectionException as dbe:
        return return_error(str(dbe), 503)
    except Exception as e:
        return return_error(str(e), 400)

    dep_id = DeploymentId(id=deployment_info.id, kind="DeploymentId", infoLink=deployment_info.self_)
    return Response(content=dep_id.model_dump_json(exclude_unset=True, by_alias=True),
                    status_code=202, media_type="application/json")
