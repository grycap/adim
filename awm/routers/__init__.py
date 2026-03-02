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

from typing import Any, Dict
from fastapi import Response
from pydantic import BaseModel
from awm.models.error import Error


def STANDARD_RESPONSES(return_type: Any = BaseModel) -> Dict[int | str, Dict[str, Any]]:
    """Standard HTTP error responses used across all routers"""
    return {
        200: {"model": return_type, "description": "Success"},
        400: {"model": Error, "description": "Invalid parameters or configuration"},
        401: {"model": Error, "description": "Authorization required"},
        403: {"model": Error, "description": "Forbidden"},
        419: {"model": Error, "description": "Re-delegate credentials"},
        503: {"model": Error, "description": "Try again later"},
    }


def GET_RESPONSES(return_type: Any = BaseModel) -> Dict[int | str, Dict[str, Any]]:
    """Standard HTTP error responses for GET operations"""
    responses = STANDARD_RESPONSES(return_type)
    responses[404] = {"model": Error, "description": "Not found"}
    return responses


def DELETE_RESPONSES(status_code: int = 204, msg: str = "Deleted") -> Dict[int | str, Dict[str, Any]]:
    """Standard HTTP error responses for DELETE operations"""
    responses = GET_RESPONSES(BaseModel)
    del responses[200]
    responses[status_code] = {"description": msg}
    return responses


def POST_RESPONSES(return_type: Any = BaseModel, status_code: int = 202,
                   msg: str = "Accepted") -> Dict[int | str, Dict[str, Any]]:
    """Standard HTTP error responses for POST operations"""
    responses = STANDARD_RESPONSES(return_type)
    del responses[200]
    responses[status_code] = {"model": return_type, "description": msg}
    return responses


def DEP_POST_RESPONSES(return_type: Any = BaseModel, return_type_2: Any = BaseModel) -> Dict[int | str, Dict[str, Any]]:
    """Standard HTTP error responses for POST operations"""
    responses = STANDARD_RESPONSES(return_type_2)
    responses[200] = {"description": "Success"}
    responses[202] = {"model": return_type, "description": "Deploying"}
    return responses


def return_error(message: str, status_code: int = 500) -> Response:
    err = Error(id=f"{status_code}", description=message)
    return Response(content=err.model_dump_json(exclude_unset=True),
                    status_code=status_code,
                    media_type="application/json")
