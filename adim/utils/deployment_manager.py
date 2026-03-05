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
import time
import yaml
from typing import Dict, Any, List
from fastapi import Request
from imclient import IMClient
from adim.models.deployment import DeploymentInfo, Deployment, CloudQuota
from adim.models.apps import ApplicationInfo
from adim.models.error import Error
from adim.models.success import Success
from adim.models.allocation import Allocation, AllocationInfo
from typing import Tuple, Union
from adim.utils.db import DataBase
from adim.utils import ConnectionException, DBConnectionException


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
            adim.logger.info("Creating deployments table")
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
    def get_im_auth_header(token: str, allocation_info: AllocationInfo | None = None) -> List[Dict[str, str]]:
        auth_data = [{"type": "InfrastructureManager", "token": token}]
        if allocation_info:
            allocation = allocation_info.allocation.root
            cloud_auth_data = {"id": allocation_info.id}
            if allocation.kind in ["OpenStackEnvironment", "EGIComputeEnvironment"]:
                cloud_auth_data["type"] = "OpenStack"
                cloud_auth_data["auth_version"] = "3.x_password"
                if allocation.authVersion == '3.x-oidc':
                    cloud_auth_data["auth_version"] = "3.x_oidc_access_token"
                cloud_auth_data["username"] = allocation.userName
                cloud_auth_data["password"] = token
                cloud_auth_data["tenant"] = allocation.tenant
                cloud_auth_data["host"] = str(allocation.host)
                cloud_auth_data["domain"] = allocation.domain
                if allocation.region:
                    cloud_auth_data["service_region"] = allocation.region
                if allocation.domainId:
                    cloud_auth_data["tenant_domain_id"] = allocation.domainId
                if allocation.tenantId:
                    cloud_auth_data["tenant_id"] = allocation.tenantId
                if allocation.apiVersion:
                    cloud_auth_data["api_version"] = allocation.apiVersion
            elif allocation.kind == "KubernetesEnvironment":
                cloud_auth_data["type"] = "Kubernetes"
                cloud_auth_data["host"] = str(allocation.host)
                cloud_auth_data["token"] = token
            else:
                raise ValueError("Allocation kind not supported")
            auth_data.append(cloud_auth_data)
        return auth_data

    def list_deployments(self, user_info: dict, from_: int = 0, limit: int = 100) -> Tuple[int, list[DeploymentInfo]]:
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
                        adim.logger.error("Failed to parse deployment info from database: %s", str(ex))
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
                        adim.logger.error("Failed to parse deployment info from database: %s", str(ex))
                        continue
                    deployments.append(deployment_info)
                res = self.db.select("SELECT count(id) from deployments WHERE owner = %s", (user_info['sub'],))
                count = res[0][0] if res else 0
            self.db.close()
        else:
            raise DBConnectionException()

        return count, deployments

    def get_allocation(self, deployment: Deployment, user_info: dict) -> Tuple[Union[Error, AllocationInfo], int]:
        # Get the allocation info from the Allocation
        try:
            allocation_data = adim.allocation_store.get_allocation(deployment.allocation.id, user_info)
        except ConnectionException as ex:
            adim.logger.error(f"Error connecting to Allocation Store: {str(ex)}")
            msg = Error(id="503", description="Allocation Store connection failed: %s." % str(ex))
            return msg, 503

        if not allocation_data:
            msg = Error(id="400", description="Invalid AllocationId.")
            return msg, 400

        allocation = Allocation.model_validate(allocation_data)
        return AllocationInfo(id=deployment.allocation.id, allocation=allocation), 200

    def _get_state(self, dep_info: DeploymentInfo, user_info: dict) -> DeploymentInfo:
        try:
            # Get the allocation info from the Allocation
            allocation_info, status = self.get_allocation(dep_info.deployment, user_info)
            if status != 200:
                return allocation_info, status

            if allocation_info.allocation.root.kind == "EoscNodeEnvironment":
                raise NotImplementedError("EOSCNodeEnvironment support not implemented yet")

            auth_data = self.get_im_auth_header(user_info['token'], allocation_info)
            client = IMClient.init_client(self.im_url, auth_data)
            success, state_info = client.get_infra_property(dep_info.id, "state")
            if success:
                dep_info.status = state_info.get('state')
            else:
                dep_info.status = "unknown"
                adim.logger.error(f"Could not retrieve deployment status: {state_info}")
                # Check if the infrastructure still exists
                success, infras = client.list_infras()
                if success:
                    if dep_info.id not in infras:
                        adim.logger.info(f"Deployment {dep_info.id} not found in IM."
                                         " Setting status to 'deleted'")
                        dep_info.status = "deleted"
                else:
                    adim.logger.error(f"Could not list infrastructures: {infras}")

            success, outputs = client.get_infra_property(dep_info.id, "outputs")
            if success:
                dep_info.outputs = outputs
            else:
                adim.logger.error(f"Could not get deployment outputs: {outputs}")

            success, cont_msg = client.get_infra_property(dep_info.id, "contmsg")
            if success:
                dep_info.details = cont_msg
            else:
                adim.logger.error(f"Could not get deployment contmsg: {cont_msg}")
        except Exception as ex:
            adim.logger.error(f"Error retrieving deployment state: {str(ex)}")

        return dep_info

    def get_deployment(self, deployment_id: str, user_info: dict,
                       get_state: bool = True) -> Tuple[Union[Error, DeploymentInfo], int]:
        dep_info = None
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
                    adim.logger.error(f"Failed to parse deployment info from database: {str(ex)}")
                    msg = Error(id="500", description="Internal server error: corrupted deployment data")
                    return msg, 500

                if get_state:
                    # Get the deployment state from the IM and update the deployment info
                    dep_info = self._get_state(dep_info, user_info)
                    # Update deployment info in DB
                    data = dep_info.model_dump_json(exclude_unset=True, exclude_none=True)
                    self.db.connect()
                    if self.db.db_type == DataBase.MONGO:
                        res = self.db.replace("deployments", {"id": deployment_id}, {"data": data})
                    else:
                        res = self.db.execute("update deployments set data = %s where id = %s",
                                              (data, deployment_id))
                    self.db.close()
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
        allocation_info, status = self.get_allocation(dep_info.deployment, user_info)
        if status != 200:
            return allocation_info, status

        if allocation_info.allocation.root.kind == "EoscNodeEnvironment":
            raise NotImplementedError("EOSCNodeEnvironment support not implemented yet")
        else:
            auth_data = self.get_im_auth_header(user_info['token'], allocation_info)
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
        adim.logger.debug(f"Input values: {inputs}")
        template = yaml.safe_load(blueprint)
        temp_inputs = template.get("topology_template", {}).get("inputs", {})
        for key in list(temp_inputs.keys()):
            if key in inputs:
                temp_inputs[key]["default"] = inputs[key]
        return yaml.safe_dump(template)

    @staticmethod
    def _compute_resources_to_use(resources: dict, quotas: dict) -> CloudQuota:
        """Compute the resources to use based on the deployment resources and the current quotas."""
        # Initialize totals
        totals = {
            "cores": 0,
            "ram": 0.0,
            "instances": 0,
            "floating_ips": 0,
            "volumes": 0,
            "volume_storage": 0,
            "security_groups": 2  # default IM value per infrastructure
        }

        # Compute totals for VMs
        for vm in resources.get("compute", []):
            totals["instances"] += 1
            totals["cores"] += vm.get("cpuCores", 0)
            totals["ram"] += vm.get("memoryInMegabytes", 0)
            totals["floating_ips"] += vm.get("publicIP", 0)

        # Compute totals for storage
        for disk in resources.get("storage", []):
            totals["volumes"] += 1
            totals["volume_storage"] += disk.get("sizeInGigabytes", 0)

        # Update quotas with computed totals
        for key, value in totals.items():
            if key not in quotas:
                quotas[key] = {}
            quotas[key]["to_use"] = value

        # Validate the CloudQuota model
        return CloudQuota.model_validate(quotas)

    def update_deployment(self, deployment: Deployment, application: ApplicationInfo,
                          allocation_info: AllocationInfo, user_info: dict,
                          request: Request, dry_run: bool = False) -> DeploymentInfo | CloudQuota:

        auth_data = self.get_im_auth_header(user_info['token'], allocation_info)

        # Create the infrastructure in the IM
        client = IMClient.init_client(self.im_url, auth_data)
        template = self._get_template(application.blueprint, deployment.inputs)
        success, deployment_id = client.create(template, "yaml", True, dry_run)
        if not success:
            raise Exception(deployment_id)

        if dry_run:
            success, quotas = client.get_cloud_quotas(allocation_info.id)
            if not success:
                adim.logger.error("Could not get cloud quotas: %s", quotas)
                quotas = {}
            return self._compute_resources_to_use(list(deployment_id.values())[0], quotas)
        else:
            if self.db.connect():
                deployment_info = DeploymentInfo(id=deployment_id,
                                                 deployment=deployment,
                                                 status="pending",
                                                 self_=str(request.url_for("get_deployment",
                                                                           deployment_id=deployment_id)))
                data = deployment_info.model_dump_json(exclude_unset=True)
                adim.logger.debug(f"Storing deployment info: {data}")
                if self.db.db_type == DataBase.MONGO:
                    res = self.db.replace("deployments", {"id": deployment_id},
                                          {"id": deployment_id, "data": data,
                                           "owner": user_info['sub'],
                                           "created": time.time()})
                else:
                    res = self.db.execute("replace into deployments (id, data, created, owner)"
                                          " values (%s, %s, now(), %s)",
                                          (deployment_id, data, user_info['sub']))
                self.db.close()
                if not res:
                    raise DBConnectionException("Failed to store deployment information in the database")
            else:
                raise DBConnectionException("Database connection failed")

            return deployment_info

    @staticmethod
    def get_deployments_manager():
        im_url = os.getenv("IM_URL", "http://localhost:8800")
        db_url = os.getenv("DB_URL", "file:///tmp/adim.db")
        return DeploymentsManager(db_url, im_url)
