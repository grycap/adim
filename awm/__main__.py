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
from awm.routers import deployments, allocations, tools, service


def create_app():
    fapp = FastAPI(
        title="EOSC AWM API",
        description="EOSC Application Workflow Management API",
        version="0.1.49",
        docs_url="/",
        root_path=os.getenv("ROOT_PATH", "")
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
        tools.router,
        tags=["Tools"]
    )

    fapp.include_router(
        service.router,
        tags=["Service"]
    )

    return fapp


def main():
    import uvicorn
    uvicorn.run(create_app(), host="127.0.0.1", port=8080)


app = create_app()

# Generate OpenAPI spec if OPENAPI environment variable is set
if os.getenv("OPENAPI"):
    with open("awm-api.yaml", "w", encoding="utf-8") as f:
        yaml.dump(app.openapi(), f, sort_keys=False, allow_unicode=True)


if __name__ == '__main__':
    main()
