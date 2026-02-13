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

import awm
from fastapi import APIRouter, Query, Depends, Request, Response
from awm.authorization import authenticate
from awm.models.deployment import DeploymentInfo, DeploymentId, Deployment
from awm.models.page import PageOfDeployments
from awm.utils.node_registry import EOSCNodeRegistry
from awm.utils import DBConnectionException
from awm.models.success import Success

from . import return_error, STANDARD_RESPONSES, GET_RESPONSES, DELETE_RESPONSES, POST_RESPONSES


router = APIRouter()


def _list_deployments(from_: int = 0, limit: int = 100,
                      all_nodes: bool = False,
                      user_info: dict = None, request: Request = None) -> Response:
    try:
        count, deployments = awm.deployments_manager.list_deployments(from_, limit, user_info)
    except DBConnectionException:
        return return_error("Database connection failed", 503)

    if all_nodes:
        remote_count, remote_tools = EOSCNodeRegistry.list_deployments(from_, limit, count, user_info)
        deployments.extend(remote_tools)
        count += remote_count

    page = PageOfDeployments(from_=from_, limit=limit, elements=deployments, count=count, self_=str(request.url))
    page.set_next_and_prev_pages(request, all_nodes)
    return Response(content=page.model_dump_json(exclude_unset=True, by_alias=True, exclude_none=True),
                    status_code=200, media_type="application/json")


# GET /deployments
@router.get("/deployments",
            summary="List existing deployments",
            responses=STANDARD_RESPONSES(PageOfDeployments))
def list_deployments(
    request: Request,
    from_: int = Query(0, alias="from", ge=0,
                       description="Index of the first element to return"),
    limit: int = Query(100, alias="limit", ge=1,
                       description="Maximum number of elements to return"),
    all_nodes: bool = Query(False, alias="allNodes"),
    user_info=Depends(authenticate)
):
    awm.logger.debug(f"Listing deployments from user '{user_info.get('sub')}'")
    return _list_deployments(from_, limit, all_nodes, user_info, request)


# GET /deployment/{deployment_id}
@router.get("/deployment/{deployment_id}",
            summary="Get information about an existing deployment",
            responses=GET_RESPONSES(DeploymentInfo))
def get_deployment(deployment_id,
                   user_info=Depends(authenticate)):
    """Get information about an existing deployment"""
    awm.logger.debug(f"Getting deployment {deployment_id} from user '{user_info.get('sub')}'")
    deployment, status_code = awm.deployments_manager.get_deployment(deployment_id, user_info, True)
    return Response(content=deployment.model_dump_json(exclude_unset=True, exclude_none=True, by_alias=True),
                    status_code=status_code, media_type="application/json")


# DELETE /deployment/{deployment_id}
@router.delete("/deployment/{deployment_id}",
               summary="Tear down an existing deployment",
               status_code=202,
               response_model=Success,
               responses=DELETE_RESPONSES(202, "Deleting"))
def delete_deployment(deployment_id,
                      user_info=Depends(authenticate)):
    """Tear down an existing deployment"""
    awm.logger.debug(f"Deleting deployment {deployment_id} from user '{user_info.get('sub')}'")
    res, status_code = awm.deployments_manager.delete_deployment(deployment_id, user_info)
    return Response(content=res.model_dump_json(exclude_unset=True),
                    status_code=status_code, media_type="application/json")


# POST /deployments
@router.post("/deployments",
             summary="Deploy workload to an EOSC environment or an infrastructure for which the user has credentials",
             status_code=202,
             response_model=DeploymentId,
             responses=POST_RESPONSES(DeploymentId, msg="Deploying"))
def deploy_workload(deployment: Deployment,
                    request: Request,
                    user_info=Depends(authenticate)):
    """Deploy workload to an EOSC environment or an infrastructure for which the user has credentials"""
    awm.logger.debug(f"Creating deployment from user '{user_info.get('sub')}'")
    # Get the Tool from the ID
    tool, status_code = awm.tool_store.get_tool(deployment.tool.id, deployment.tool.version, request)
    if status_code != 200:
        awm.logger.warning(f"Tool {deployment.tool.id} not found")
        return Response(content=tool, status_code=400, media_type="application/json")

    # Get the allocation info from the Allocation
    allocation, status = awm.deployments_manager.get_allocation(deployment, user_info)
    if status != 200:
        awm.logger.warning(f"Allocation {deployment.allocation.id} not found")
        return allocation, status

    if allocation.root.kind == "EoscNodeEnvironment":
        awm.logger.error("EOSCNodeEnvironment support not implemented yet")
        raise NotImplementedError("EOSCNodeEnvironment support not implemented yet")

    try:
        deployment_info = awm.deployments_manager.update_deployment(deployment, tool, allocation,
                                                                    user_info, request)
    except DBConnectionException as dbe:
        return return_error(str(dbe), 503)
    except Exception as e:
        return return_error(str(e), 400)

    dep_id = DeploymentId(id=deployment_info.id, kind="DeploymentId", infoLink=deployment_info.self_)
    return Response(content=dep_id.model_dump_json(exclude_unset=True, by_alias=True),
                    status_code=202, media_type="application/json")
