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
import time
import yaml
from typing import Dict, Any
from fastapi import Request
from imclient import IMClient
from awm.models.deployment import DeploymentInfo, Deployment
from awm.models.tool import ToolInfo
from awm.models.error import Error
from awm.models.success import Success
from awm.models.allocation import Allocation, AllocationUnion, AllocationInfo
from typing import Tuple, Union
from awm.utils.db import DataBase
from awm.utils import ConnectionException, DBConnectionException


class DeploymentsManager:

    def __init__(self, db_url: str, im_url: str):
        self.im_url = im_url
        self.db = DataBase(db_url)
        if self.db.connect():
            self._init_table(self.db)
            self.db.close()
        else:
            raise DBConnectionException()

    @staticmethod
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

    @staticmethod
    def get_im_auth_header(token: str, allocation: AllocationUnion = None) -> dict:
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

    def list_deployments(self, from_: int = 0, limit: int = 100,
                         user_info: dict = None) -> Tuple[int, list[DeploymentInfo]]:
        deployments = []
        if self.db.connect():
            if self.db.db_type == DataBase.MONGO:
                res = self.db.find("deployments", filt={"owner": user_info['sub']},
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
                res = self.db.select(sql, (user_info['sub'], limit, from_))
                for elem in res:
                    deployment_data = elem[0]
                    try:
                        deployment_info = DeploymentInfo.model_validate_json(deployment_data)
                    except Exception as ex:
                        awm.logger.error("Failed to parse deployment info from database: %s", str(ex))
                        continue
                    deployments.append(deployment_info)
                res = self.db.select("SELECT count(id) from deployments WHERE owner = %s", (user_info['sub'],))
                count = res[0][0] if res else 0
            self.db.close()
        else:
            raise DBConnectionException()

        return count, deployments

    def get_allocation(self, deployment: Deployment, user_info: dict) -> Tuple[Union[Error, Allocation], int]:
        # Get the allocation info from the Allocation
        try:
            allocation_data = awm.allocation_store.get_allocation(deployment.allocation.id, user_info)
        except ConnectionException as ex:
            awm.logger.error(f"Error connecting to Allocation Store: {str(ex)}")
            msg = Error(id="503", description="Allocation Store connection failed: %s." % str(ex))
            return msg, 503

        allocation = Allocation.model_validate(allocation_data)

        if not allocation:
            msg = Error(id="400", description="Invalid AllocationId.")
            return msg, 400

        return allocation, 200

    def get_deployment(self, deployment_id: str, user_info: dict,
                       get_state: bool = True) -> Tuple[Union[Error, DeploymentInfo], int]:
        dep_info = None
        user_token = user_info['token']
        user_id = user_info['sub']
        if self.db.connect():
            if self.db.db_type == DataBase.MONGO:
                res = self.db.find("deployments", {"id": deployment_id, "owner": user_id}, {"data": True})
            else:
                res = self.db.select("SELECT data FROM deployments WHERE id = %s and owner = %s",
                                     (deployment_id, user_id))
            self.db.close()
            if res:
                if self.db.db_type == DataBase.MONGO:
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
                        allocation, status = self.get_allocation(dep_info.deployment, user_info)
                        if status != 200:
                            return allocation, status

                        if allocation.root.kind == "EoscNodeEnvironment":
                            raise NotImplementedError("EOSCNodeEnvironment support not implemented yet")

                        auth_data = self.get_im_auth_header(user_token, allocation.root)
                        client = IMClient.init_client(self.im_url, auth_data)
                        success, state_info = client.get_infra_property(deployment_id, "state")
                        if success:
                            dep_info.status = state_info.get('state')
                        else:
                            dep_info.status = "unknown"
                            awm.logger.error(f"Could not retrieve deployment status: {state_info}")
                            # Check if the infrastructure still exists
                            success, infras = client.list_infras()
                            if success:
                                if deployment_id not in infras:
                                    awm.logger.info(f"Deployment {deployment_id} not found in IM."
                                                    " Setting status to 'deleted'")
                                    dep_info.status = "deleted"
                            else:
                                awm.logger.error(f"Could not list infrastructures: {infras}")

                        success, outputs = client.get_infra_property(deployment_id, "outputs")
                        if success:
                            dep_info.outputs = outputs.get('outputs')

                        success, cont_msg = client.get_infra_property(deployment_id, "contmsg")
                        if success:
                            dep_info.details = cont_msg

                        # Update deployment info in DB
                        data = dep_info.model_dump_json(exclude_unset=True, exclude_none=True)
                        self.db.connect()
                        if self.db.db_type == DataBase.MONGO:
                            res = self.db.replace("deployments", {"id": deployment_id}, {"data": data})
                        else:
                            res = self.db.execute("update deployments set data = %s where id = %s",
                                                  (data, deployment_id))
                        self.db.close()
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

    def delete_deployment(self, deployment_id: str, user_info: dict) -> Tuple[Union[Error, Success], int]:
        dep_info, status_code = self.get_deployment(deployment_id, user_info, get_state=False)
        if status_code != 200:
            return dep_info, status_code

        # Get the allocation info from the Allocation
        allocation, status = self.get_allocation(dep_info.deployment, user_info)
        if status != 200:
            return allocation, status

        if allocation.root.kind == "EoscNodeEnvironment":
            raise NotImplementedError("EOSCNodeEnvironment support not implemented yet")
        else:
            auth_data = self.get_im_auth_header(user_info['token'], allocation.root)
            client = IMClient.init_client(self.im_url, auth_data)
            success, destroy_msg = client.destroy(deployment_id)

            if not success:
                msg = Error(id="400", description=destroy_msg)
                return msg, 400

        if self.db.connect():
            if self.db.db_type == DataBase.MONGO:
                self.db.delete("deployments", {"id": deployment_id})
            else:
                self.db.execute("DELETE FROM deployments WHERE id = %s", (deployment_id,))
            self.db.close()
        else:
            msg = Error(id="503", description="Database connection failed")
            return msg, 503

        msg = Success(message="Deleting")
        return msg, 202

    @staticmethod
    def _get_template(blueprint: str, inputs: Dict[str, Any]) -> str:
        if not inputs:
            return blueprint
        template = yaml.safe_load(blueprint)
        temp_inputs = template.get("topology_template", {}).get("inputs", {})
        for key in list(temp_inputs.keys()):
            if key in inputs:
                temp_inputs[key]["default"] = inputs[key]
        return yaml.safe_dump(template)

    def update_deployment(self, deployment: Deployment, tool: ToolInfo,
                          allocation: AllocationInfo, user_info: dict,
                          request: Request) -> DeploymentInfo:

        auth_data = self.get_im_auth_header(user_info['token'], allocation.root)

        # Create the infrastructure in the IM
        client = IMClient.init_client(self.im_url, auth_data)
        template = self._get_template(tool.blueprint, deployment.inputs)
        success, deployment_id = client.create(template, "yaml", True)
        if not success:
            raise Exception(deployment_id)

        if self.db.connect():
            deployment_info = DeploymentInfo(id=deployment_id,
                                             deployment=deployment,
                                             status="pending",
                                             self_=str(request.url_for("get_deployment", deployment_id=deployment_id)))
            data = deployment_info.model_dump_json(exclude_unset=True)
            awm.logger.debug(f"Storing deployment info: {data}")
            if self.db.db_type == DataBase.MONGO:
                res = self.db.replace("deployments", {"id": deployment_id},
                                      {"id": deployment_id, "data": data,
                                       "owner": user_info['sub'],
                                       "created": time.time()})
            else:
                res = self.db.execute("replace into deployments (id, data, created, owner) values (%s, %s, now(), %s)",
                                      (deployment_id, data, user_info['sub']))
            self.db.close()
            if not res:
                raise DBConnectionException("Failed to store deployment information in the database")
        else:
            raise DBConnectionException("Database connection failed")

        return deployment_info
