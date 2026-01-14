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
import time
import awm
from imclient import IMClient
from fastapi import APIRouter, Query, Depends, Request, Response
from awm.authorization import authenticate
from awm.models.deployment import DeploymentInfo, DeploymentId, Deployment
from awm.models.page import PageOfDeployments
from awm.models.error import Error
from awm.models.success import Success
from awm.models.allocation import AllocationUnion
from awm.utils.node_registry import EOSCNodeRegistry
from typing import Tuple, Union
from awm.utils.db import DataBase

from . import return_error


router = APIRouter()
#IM_URL = os.getenv("IM_URL", "http://localhost:8800")
IM_URL = os.getenv("IM_URL", "https://appsgrycap.i3m.upv.es/im-dev")
DB_URL = os.getenv("DB_URL", "file:///tmp/awm.db")


def _init_table(db: DataBase) -> bool:
    """Creates de database."""
    if not db.table_exists("deployments"):
        awm.logger.info("Creating deployments table")
        if db.db_type == DataBase.MYSQL:
            db.execute("CREATE TABLE IF NOT EXISTS deployments (id VARCHAR(255) PRIMARY KEY, data TEXT"
                       ", owner VARCHAR(255), created TIMESTAMP)")
        elif db.db_type == DataBase.SQLITE:
            db.execute("CREATE TABLE IF NOT EXISTS deployments (id TEXT PRIMARY KEY, data TEXT"
                       ", owner VARCHAR(255), created TIMESTAMP)")
        elif db.db_type == DataBase.MONGO:
            db.connection.create_collection("deployments")
            db.connection["deployments"].create_index([("id", 1), ("owner", 1)], unique=True)
        return True
    return False


def _get_im_auth_header(token: str, allocation: AllocationUnion = None) -> dict:
    auth_data = [{"type": "InfrastructureManager", "token": token}]
    if allocation:
        if allocation.kind == "OpenStackEnvironment":
            ost_auth_data = {"id": "ost", "type": "OpenStack", "auth_version": "3.x_oidc_access_token"}
            ost_auth_data["username"] = allocation.userName
            ost_auth_data["password"] = token
            ost_auth_data["tenant"] = allocation.tenant
            ost_auth_data["host"] = str(allocation.host)
            ost_auth_data["domain"] = allocation.domain
            if allocation.region:
                ost_auth_data["service_region"] = allocation.region
            if allocation.domainId:
                ost_auth_data["tenant_domain_id"] = allocation.domainId
            if allocation.tenantId:
                ost_auth_data["tenant_id"] = allocation.tenantId
            if allocation.apiVersion:
                ost_auth_data["api_version"] = allocation.apiVersion
            auth_data.append(ost_auth_data)
        elif allocation.kind == "KubernetesEnvironment":
            k8s_auth_data = {"type": "kubernetes", "token": token}
            k8s_auth_data["host"] = str(allocation.host)
            k8s_auth_data["password"] = token
            auth_data.append(k8s_auth_data)
        else:
            raise ValueError("Allocation kind not supported")
    return auth_data


def _get_deployment(deployment_id: str, user_info: dict, request: Request,
                    get_state: bool = True) -> Tuple[Union[Error, Deployment], int]:
    dep_info = None
    user_token = user_info['token']
    user_id = user_info['sub']
    db = DataBase(DB_URL)
    if db.connect():
        _init_table(db)
        if db.db_type == DataBase.MONGO:
            res = db.find("deployments", {"id": deployment_id, "owner": user_id}, {"data": True})
        else:
            res = db.select("SELECT data FROM deployments WHERE id = %s and owner = %s", (deployment_id, user_id))
        db.close()
        if res:
            if db.db_type == DataBase.MONGO:
                deployment_data = res[0]["data"]
            else:
                deployment_data = res[0][0]
            try:
                dep_info = DeploymentInfo.model_validate_json(deployment_data)
            except Exception as ex:
                awm.logger.error(f"Failed to parse deployment info from database: {str(ex)}")
                msg = Error(id="500", description="Internal server error: corrupted deployment data")
                return msg, 500

            try:
                if get_state:
                    # Get the allocation info from the Allocation
                    allocation_info = awm.routers.allocations._get_allocation(dep_info.deployment.allocation.id,
                                                                              user_info,
                                                                              request)
                    if not allocation_info:
                        return "Invalid AllocationId.", 400

                    if allocation_info.allocation.root.kind == "EoscNodeEnvironment":
                        raise NotImplementedError("EOSCNodeEnvironment support not implemented yet")
                    else:
                        auth_data = _get_im_auth_header(user_token, allocation_info.allocation.root)
                        client = IMClient.init_client(IM_URL, auth_data)
                        success, state_info = client.get_infra_property(deployment_id, "state")
                        if not success:
                            msg = Error(description=state_info)
                            return msg, 400
                        success, cont_msg = client.get_infra_property(deployment_id, "contmsg")
                        if success:
                            dep_info.message = cont_msg
                        dep_info.status = state_info['state']
            except Exception as ex:
                msg = Error(id="400", description=str(ex))
                return msg, 400
        else:
            msg = Error(id="404", description=f"Deployment {deployment_id} not found")
            return msg, 404
    else:
        msg = Error(id="503", description="Database connection failed")
        return msg, 503
    return dep_info, 200


def _list_deployments(from_: int = 0, limit: int = 100,
                      all_nodes: bool = False,
                      user_info: dict = None, request: Request = None) -> Response:
    deployments = []
    db = DataBase(DB_URL)
    if db.connect():
        _init_table(db)
        if db.db_type == DataBase.MONGO:
            res = db.find("deployments", filt={"owner": user_info['sub']},
                          projection={"data": True}, sort=[('created', -1)])
            for count, elem in enumerate(res):
                if from_ > count:
                    continue
                deployment_data = elem['data']
                try:
                    deployment_info = DeploymentInfo.model_validate(deployment_data)
                except Exception as ex:
                    awm.logger.error("Failed to parse deployment info from database: %s", str(ex))
                    continue
                deployments.append(deployment_info)
                if len(deployments) >= limit:
                    break
            count = len(res)
        else:
            sql = "SELECT data FROM deployments WHERE owner = %s order by created LIMIT %s OFFSET %s"
            res = db.select(sql, (user_info['sub'], limit, from_))
            for elem in res:
                deployment_data = elem[0]
                try:
                    deployment_info = DeploymentInfo.model_validate_json(deployment_data)
                except Exception as ex:
                    awm.logger.error("Failed to parse deployment info from database: %s", str(ex))
                    continue
                deployments.append(deployment_info)
            res = db.select("SELECT count(id) from deployments WHERE owner = %s", (user_info['sub'],))
            count = res[0][0] if res else 0
        db.close()
    else:
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
                   request: Request,
                   user_info=Depends(authenticate)):
    """Get information about an existing deployment"""
    deployment, status_code = _get_deployment(deployment_id, user_info, request)
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
                      request: Request,
                      user_info=Depends(authenticate)):
    """Tear down an existing deployment"""
    deployment, status_code = _get_deployment(deployment_id, user_info, request, get_state=False)
    if status_code != 200:
        return Response(content=deployment.model_dump_json(exclude_unset=True, by_alias=True),
                        status_code=status_code, media_type="application/json")

    # Get the allocation info from the Allocation
    allocation_info = awm.routers.allocations._get_allocation(deployment.deployment.allocation.id, user_info, request)
    if not allocation_info:
        return return_error("Invalid AllocationId.", status_code=400)
    allocation = allocation_info.allocation

    if allocation_info.allocation.root.kind == "EoscNodeEnvironment":
        raise NotImplementedError("EOSCNodeEnvironment support not implemented yet")
    else:
        auth_data = _get_im_auth_header(user_info['token'], allocation.root)
        client = IMClient.init_client(IM_URL, auth_data)
        success, msg = client.destroy(deployment_id)

        if not success:
            return return_error(msg, 400)

    db = DataBase(DB_URL)
    if db.connect():
        _init_table(db)
        if db.db_type == DataBase.MONGO:
            db.delete("deployments", {"id": deployment_id})
        else:
            db.execute("DELETE FROM deployments WHERE id = %s", (deployment_id,))
        db.close()
    else:
        return return_error("Database connection failed", 503)

    msg = Success(message="Deleting")
    return Response(content=msg.model_dump_json(exclude_unset=True), status_code=202, media_type="application/json")


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
    tool, status_code = awm.routers.tools.get_tool_from_repo(deployment.tool.id, deployment.tool.version, request)
    if status_code != 200:
        return Response(content=tool, status_code=400, media_type="application/json")

    # Get the allocation info from the Allocation
    allocation_info = awm.routers.allocations._get_allocation(deployment.allocation.id, user_info, request)
    if not allocation_info:
        return return_error("Invalid AllocationId.", status_code=400)
    allocation = allocation_info.allocation

    if allocation_info.allocation.root.kind == "EoscNodeEnvironment":
        raise NotImplementedError("EOSCNodeEnvironment support not implemented yet")
    else:
        auth_data = _get_im_auth_header(user_info['token'], allocation.root)

        # Create the infrastructure in the IM
        client = IMClient.init_client(IM_URL, auth_data)
        success, deployment_id = client.create(tool.blueprint, "yaml", True)
        if not success:
            return_error(deployment_id, 400)

    db = DataBase(DB_URL)
    if db.connect():
        _init_table(db)
        deployment_info = DeploymentInfo(id=deployment_id,
                                         deployment=deployment,
                                         status="pending",
                                         self_=str(request.url_for("get_deployment", deployment_id=deployment_id)))
        data = deployment_info.model_dump_json(exclude_unset=True)
        if db.db_type == DataBase.MONGO:
            res = db.replace("deployments", {"id": deployment_id}, {"id": deployment_id, "data": data,
                                                                    "owner": user_info['sub'],
                                                                    "created": time.time()})
        else:
            res = db.execute("replace into deployments (id, data, created, owner) values (%s, %s, %s, %s)",
                             (deployment_id, data, time.time(), user_info['sub']))
        db.close()
        if not res:
            return return_error("Failed to store deployment information in the database", 503)
    else:
        return return_error("Database connection failed", 503)

    dep_id = DeploymentId(id=deployment_id, kind="DeploymentId", infoLink=deployment_info.self_)
    return Response(content=dep_id.model_dump_json(exclude_unset=True, by_alias=True),
                    status_code=202, media_type="application/json")
