#!/usr/bin/env python3
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

import yaml
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi

from adim.routers import allocations
from adim.routers import applications
from adim.routers import deployments
from adim.routers import service


def create_app():
    fapp = FastAPI(
        title="ADIM API",
        description=("Application Deployment with Infrastructure Manager "
                     "implements EOSC Application Deployment Management API"),
        version="1.0.51",
        docs_url="/",
        root_path=os.getenv("ROOT_PATH", ""),
        separate_input_output_schemas=False,
    )

    fapp.include_router(
        deployments.router,
        tags=["Deployments"]
    )

    fapp.include_router(
        allocations.router,
        tags=["Allocations"]
    )

    fapp.include_router(
        applications.router,
        tags=["Applications"]
    )

    fapp.include_router(
        service.router,
        tags=["Service"]
    )

    # Custom exception handler for FastAPI validation errors to return 400 instead of 422
    @fapp.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request, exc):
        details = {}
        for error in exc.errors():
            loc = ".".join(str(part) for part in error.get("loc", []))
            details[loc] = error.get("msg", "")
        return JSONResponse(
            status_code=400,
            content={
                "id": "400",
                "description": "Invalid parameters or configuration",
                "details": details,
            },
        )

    # Override the OpenAPI schema generation to remove the default 422 response from all endpoints
    def custom_openapi():
        if not fapp.openapi_schema:
            schema = get_openapi(
                title=fapp.title,
                version=fapp.version,
                description=fapp.description,
                routes=fapp.routes,
            )
            for path in schema.get("paths", {}).values():
                for operation in path.values():
                    if isinstance(operation, dict):
                        operation.get("responses", {}).pop("422", None)
            fapp.openapi_schema = schema
        return fapp.openapi_schema

    fapp.openapi = custom_openapi

    return fapp


def main():
    import uvicorn
    uvicorn.run(create_app(), host="127.0.0.1", port=8080)


app = create_app()

# Generate OpenAPI spec if OPENAPI environment variable is set
if os.getenv("OPENAPI"):
    with open("adim-api.yaml", "w", encoding="utf-8") as f:
        yaml.dump(app.openapi(), f, sort_keys=False, allow_unicode=True)


if __name__ == '__main__':
    main()
