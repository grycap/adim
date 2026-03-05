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
import os
from typing import List, Tuple, Union
from fastapi import Request
from adim.models.apps import ApplicationInfo
from adim.models.error import Error
from adim.utils import ConnectionException


class ApplicationStore:

    def __init__(self, url: str):
        self.url = url

    @staticmethod
    def get_application_type(tosca: dict) -> str:
        try:
            node_templates = tosca.get('topology_template', {}).get('node_templates', {})
            for _, node in node_templates.items():
                if node.get('type', '') == 'tosca.nodes.Container.Application.Docker':
                    return "container"
        except Exception:
            adim.logger.exception("Error getting application type using default 'vm'")
        return "vm"

    def _list(self, request: Request, from_: int, limit: int, user_info: dict) -> List[ApplicationInfo]:
        raise NotImplementedError()

    def list_applications(self, request: Request, from_: int = 0, limit: int = 100,
                          user_info: dict = None) -> Tuple[int, int, List[ApplicationInfo]]:
        applications = []
        try:
            applications_list = self._list(request, from_, limit, user_info)
        except Exception as e:
            raise ConnectionException(f"Failed to get list of Applications: {e}") from e

        count = 0
        total = len(applications_list)
        for application in applications_list:
            count += 1
            if from_ > count - 1:
                continue
            try:
                applications.append(application)
                if len(applications) >= limit:
                    break
            except Exception as ex:
                adim.logger.error("Failed to get application info: %s", ex)

        return total, count, applications

    @staticmethod
    def get_application_info(elem: dict, request: Request) -> ApplicationInfo:
        raise NotImplementedError()

    def get_application(self, application_id: str, version: str, request: Request,
                        user_info: dict = None) -> Tuple[Union[ApplicationInfo, Error], int]:
        raise NotImplementedError()

    @staticmethod
    def get_application_store() -> 'ApplicationStore':
        """Factory method to get the ApplicationStore instance based on the configuration"""
        app_type = os.getenv("APPLICATIONS_STORE", "git")
        if app_type == "git":
            app_repo = os.getenv("APPLICATIONS_REPO", "https://github.com/grycap/tosca/blob/eosc_lot1/templates/")
            from adim.utils.application.git_app_store import ApplicationStoreGit
            application_store = ApplicationStoreGit(app_repo)
        elif app_type == "rc":
            resource_catalog = os.getenv("RESOURCE_CATALOG", "https://providers.sandbox.eosc-beyond.eu/api")
            from adim.utils.application.rc_app_store import ApplicationStoreRC
            application_store = ApplicationStoreRC(resource_catalog)
        else:
            raise ValueError(f"Application store '{app_type}' is not supported")
        return application_store
