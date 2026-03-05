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
from adim.models.apps import ApplicationInfo
from adim.models.page import PageOfApplications
from adim.utils.node_registry import EOSCNodeRegistry
from adim.utils import ConnectionException
from . import return_error, STANDARD_RESPONSES, GET_RESPONSES


router = APIRouter()


# GET /applications
@router.get("/applications",
            summary="List all application blueprints",
            responses=STANDARD_RESPONSES(PageOfApplications))
def list_applications(
    request: Request,
    from_: int = Query(0, alias="from", ge=0,
                       description="Index of the first element to return"),
    limit: int = Query(100, alias="limit", ge=1,
                       description="Maximum number of elements to return"),
    all_nodes: bool = Query(False, alias="allNodes"),
    user_info=Depends(authenticate)
):
    try:
        adim.logger.debug(f"Listing applications from user '{user_info.get('sub')}'")
        total, count, applications = adim.application_store.list_applications(request, from_, limit, user_info)
    except ConnectionException as ex:
        return return_error("Repository connection failed: %s" % ex, 503)

    remote_count = 0
    if all_nodes:
        remote_count, remote_applications = EOSCNodeRegistry.list_applications(from_, limit, count, user_info)
        applications.extend(remote_applications)

    page = PageOfApplications(from_=from_, limit=limit, elements=applications, count=total + remote_count)
    page.set_next_and_prev_pages(request, all_nodes)
    return Response(content=page.model_dump_json(exclude_unset=True, by_alias=True), status_code=200,
                    media_type="application/json")


# GET /application/{application_id}
@router.get("/application/{application_id}",
            summary="Get information about an application blueprint",
            responses=GET_RESPONSES(ApplicationInfo))
def get_application(application_id: str,
             request: Request,
             version: str = Query("latest", description="If missing, the latest version will be returned"),
             user_info=Depends(authenticate)):
    """Get information about an existing application blueprint"""
    try:
        adim.logger.debug(f"Getting application {application_id} from user '{user_info.get('sub')}'")
        application_or_msg, status_code = adim.application_store.get_application(application_id, version, request)
    except ConnectionException as ex:
        return return_error("Repository connection failed: %s" % ex, 503)

    return Response(content=application_or_msg.model_dump_json(exclude_unset=True, by_alias=True),
                    status_code=status_code, media_type="application/json")
