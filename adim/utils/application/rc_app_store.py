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

import yaml
import adim
import requests
from typing import Tuple, Union, List
from fastapi import Request
from urllib.parse import urlparse
from adim.models.apps import ApplicationInfo
from adim.models.error import Error
from adim.utils import ConnectionException
from .app_store import ApplicationStore


class ApplicationStoreRC(ApplicationStore):

    def __init__(self, url: str = "https://providers.sandbox.eosc-beyond.eu/api"):
        super().__init__(url)

    @staticmethod
    def _convert_url_to_raw(url: str) -> str:
        parsed = urlparse(url)
        # Only convert well-formed GitHub blob URLs with the expected host.
        if parsed.scheme == "https" and parsed.hostname == "github.com":
            # Expected path format: /{owner}/{repo}/blob/{path/to/file}
            path_parts = parsed.path.lstrip("/").split("/", 4)
            if len(path_parts) >= 4 and path_parts[2] == "blob":
                owner = path_parts[0]
                repo = path_parts[1]
                file_path = path_parts[3] if len(path_parts) == 4 else path_parts[3] + "/" + path_parts[4]
                return f"https://raw.githubusercontent.com/{owner}/{repo}/{file_path}"
        return url

    @staticmethod
    def get_application_info(elem: dict, request: Request) -> ApplicationInfo:
        tosca = yaml.safe_load(requests.get(ApplicationStoreRC._convert_url_to_raw(elem['url']), timeout=10).text)
        metadata = tosca.get("metadata", {})
        application_id = elem['id'].replace("/", "%2F")
        url = str(request.url_for("get_application", application_id=application_id))
        url += f"?version={elem['version']}"
        app = ApplicationInfo(
            id=elem['id'],
            self_=url,
            version='latest',
            type=ApplicationStore.get_application_type(tosca),
            name=elem.get("name", metadata.get("template_name", "")),
            description=elem.get("description", tosca.get("description", "")),
            blueprint=yaml.safe_dump(tosca),
            blueprintType="tosca"
        )
        if elem.get("creators"):
            creator = elem["creators"][0].get("creatorNameTypeInfo", {}).get("creatorName")
            if creator:
                app.authorName = creator
            if elem["creators"][0].get("creatorAffiliationInfo"):
                app.organisation = elem["creators"][0].get("creatorAffiliationInfo").get("affiliation")
        elif metadata.get("template_author"):
            app.authorName = metadata.get("template_author")

        if elem.get("node"):
            app.nodeId = elem["node"]
        if elem.get('version'):
            app.version = elem['version']
        if elem.get('softwareLicense'):
            app.license = elem['softwareLicense']
        return app

    def get_application(self, application_id: str, version: str, request: Request,
                        user_info: dict = None) -> Tuple[Union[ApplicationInfo, Error], int]:
        # application_id was provided with underscores; convert back path
        repo_application_id = application_id.replace("%2F", "/")
        try:
            response = requests.get(f"{self.url}/deployableService/{repo_application_id}", timeout=10)
        except Exception as e:
            adim.logger.error("Failed to get application info: %s", e)
            raise ConnectionException(f"Failed to get application info: {e}")

        if response.status_code == 404:
            msg = Error(id="404", description="Application not found")
            return msg, 404
        if response.status_code != 200:
            adim.logger.error("Failed to fetch application: %s", response.text)
            msg = Error(id="503", description="Failed to fetch application")
            return msg, 503

        app = self.get_application_info(response.json(), request)
        return app, 200

    def _list(self, request: Request, from_: int, limit: int, user_info: dict) -> List[ApplicationInfo]:
        response = requests.get(f"{self.url}/deployableService/all", timeout=10)
        response.raise_for_status()
        res = []
        for elem in response.json().get("results", []):
            app = self.get_application_info(elem, request)
            res.append(app)
        return res
