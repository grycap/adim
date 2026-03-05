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

import base64
import yaml
import adim
from typing import Tuple, Union, List
from fastapi import Request
from adim.models.apps import ApplicationInfo
from adim.models.error import Error
from adim.utils.application.repository import Repository
from adim.utils import ConnectionException
from .app_store import ApplicationStore


class ApplicationStoreGit(ApplicationStore):

    def __init__(self, url: str):
        super().__init__(url)

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

    @staticmethod
    def get_application_info(elem: dict, request: Request) -> ApplicationInfo:
        tosca = yaml.safe_load(elem["template"])
        metadata = tosca.get("metadata", {})
        app_id = elem['path'].replace("/", "%2F")
        url = str(request.url_for("get_application", application_id=app_id))
        version = elem.get("version", "latest")
        if version != "latest":
            url += "?version=%s" % version
        app = ApplicationInfo(
            id=elem['path'],
            self_=url,
            version='latest',
            type=ApplicationStore.get_application_type(tosca),
            name=metadata.get("template_name", ""),
            description=tosca.get("description", ""),
            blueprint=elem["template"],
            blueprintType="tosca"
        )
        if metadata.get("template_author"):
            app.authorName = metadata.get("template_author")
        if version:
            app.version = version
        return app

    def get_application(self, application_id: str, version: str, request: Request,
                        user_info: dict = None) -> Tuple[Union[ApplicationInfo, Error], int]:
        # application_id was provided with underscores; convert back path
        repo_application_id = application_id.replace("%2F", "/")
        try:
            repo = Repository.create(self.url)
            response = repo.get(repo_application_id, version, details=True)
        except Exception as e:
            adim.logger.error("Failed to get application info: %s", e)
            raise ConnectionException("Failed to get application info: %s" % e)

        if response.status_code == 404:
            msg = Error(id="404", description="Application not found")
            return msg, 404
        if response.status_code != 200:
            adim.logger.error("Failed to fetch application: %s", response.text)
            msg = Error(id="503", description="Failed to fetch application")
            return msg, 503

        template = base64.b64decode(response.json().get("content").encode()).decode()
        if not version or version == "latest":
            version = response.json().get("sha")

        app = self.get_application_info({"path": repo_application_id, "version": version,
                                           "template": template}, request)
        return app, 200

    def _list(self, request: Request, from_: int, limit: int, user_info: dict) -> List[ApplicationInfo]:
        repo = Repository.create(self.url)
        res = []
        for _, elem in repo.list().items():
            app = self.get_application_info({"path": elem['path'], "version": elem['sha'],
                                               "template": repo.get(elem['path']).text}, request)
            res.append(app)
        return res
