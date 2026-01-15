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
from awm.models.tool import ToolInfo
from awm.models.page import PageOfTools
from awm.models.error import Error
from awm.utils.node_registry import EOSCNodeRegistry
from awm.utils.tool_store import ToolStore
from awm.utils import RepositoryConnectionException
from . import return_error


AWM_TOOLS_REPO = os.getenv("AWM_TOOLS_REPO", "https://github.com/grycap/tosca/blob/eosc_lot1/templates/")
router = APIRouter()

tool_store = ToolStore(AWM_TOOLS_REPO)


# GET /tools
@router.get("/tools",
            summary="List all tool blueprints",
            responses={200: {"model": PageOfTools,
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
def list_tools(
    request: Request,
    from_: int = Query(0, alias="from", ge=0,
                       description="Index of the first element to return"),
    limit: int = Query(100, alias="limit", ge=1,
                       description="Maximum number of elements to return"),
    all_nodes: bool = Query(False, alias="allNodes"),
    user_info=Depends(authenticate)
):
    try:
        total, count, tools = tool_store.list_tools(request, from_, limit)
    except RepositoryConnectionException as ex:
        return return_error("Repository connection failed: %s" % ex, 503)

    remote_count = 0
    if all_nodes:
        remote_count, remote_tools = EOSCNodeRegistry.list_tools(from_, limit, count, user_info)
        tools.extend(remote_tools)

    page = PageOfTools(from_=from_, limit=limit, elements=tools, count=total + remote_count)
    page.set_next_and_prev_pages(request, all_nodes)
    return Response(content=page.model_dump_json(exclude_unset=True, by_alias=True), status_code=200,
                    media_type="application/json")


# GET /tool/{tool_id}
@router.get("/tool/{tool_id}",
            summary="Get information about a tool blueprint",
            responses={200: {"model": ToolInfo,
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
def get_tool(tool_id: str,
             request: Request,
             version: str = Query("latest", description="If missing, the latest version will be returned"),
             user_info=Depends(authenticate)):
    """Get information about an existing tool blueprint"""
    try:
        tool_or_msg, status_code = tool_store.get_tool_from_repo(tool_id, version, request)
    except RepositoryConnectionException as ex:
        return return_error("Repository connection failed: %s" % ex, 503)

    return Response(content=tool_or_msg.model_dump_json(exclude_unset=True, by_alias=True),
                    status_code=status_code, media_type="application/json")
