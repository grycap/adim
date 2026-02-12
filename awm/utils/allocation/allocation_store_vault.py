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

import hvac
import json
import uuid
import requests
from typing import List
from cryptography.fernet import Fernet
from .allocation_store import AllocationStore
from awm.utils import VaultConnectionException


class AllocationStoreVault(AllocationStore):

    SECRETS_EGI = "https://secrets.egi.eu"
    DEFAULT_URL = SECRETS_EGI
    DEFAULT_KEY = "3JSvUdOsAlvSNVYvBwHWE-iKdWkhq4C_LmjRcpuycT0="

    def __init__(self, vault_url, mount_point=None, path=None, role=None, kv_ver=1, ssl_verify=False, key=None):
        self.url = vault_url
        self.ssl_verify = ssl_verify
        if kv_ver not in [1, 2]:
            raise Exception("Invalid KV version (1 or 2)")
        self.kv_ver = kv_ver
        self.role = role
        if vault_url == self.SECRETS_EGI:
            self.mount_point = "/secrets"
            self.path = "users/{sub}/allocations"
        else:
            self.mount_point = "allocations/"
            if mount_point:
                self.mount_point = mount_point
            self.path = path
        self.key = None
        if key:
            self.key = Fernet(key)

    def _encrypt(self, message):
        if self.key:
            return self.key.encrypt(message.encode()).decode()
        else:
            return message

    def _decrypt(self, message):
        if self.key:
            return self.key.decrypt(message).decode()
        else:
            return message

    def _login(self, user_info):
        login_url = self.url + '/v1/auth/jwt/login'
        token = user_info['token']

        if self.role:
            data = '{ "jwt": "' + token + '", "role": "' + self.role + '" }'
        else:
            data = '{ "jwt": "' + token + '" }'

        try:
            response = requests.post(login_url, data=data, verify=self.ssl_verify, timeout=5)
        except requests.exceptions.ConnectionError as ex:
            raise VaultConnectionException(str(ex))

        if not response.ok:
            raise Exception(f"Error getting Vault token: {response.status_code} - {response.text}")

        deserialized_response = response.json()

        vault_auth_token = deserialized_response["auth"]["client_token"]
        vault_entity_id = deserialized_response["auth"]["entity_id"]

        client = hvac.Client(url=self.url, token=vault_auth_token, verify=self.ssl_verify)
        if not client.is_authenticated():
            raise VaultConnectionException(f"Error authenticating against Vault with token: {vault_auth_token}")

        path = self.path
        if path is None:
            path = vault_entity_id
        else:
            path = self.path.format(sub=user_info['sub'])

        if self.kv_ver == 1:
            return client.secrets.kv.v1, path
        elif self.kv_ver == 2:
            return client.secrets.kv.v2, path
        raise VaultConnectionException("Invalid KV version (1 or 2)")

    def list_allocations(self, user_info: dict, from_: int, limit: int) -> List[dict]:
        client, path = self._login(user_info)

        try:
            creds = client.read_secret(path=path, mount_point=self.mount_point)
        except Exception:
            creds = {}

        data = []
        for count, elem in enumerate(creds["data"].items()):
            if from_ > count:
                continue
            allocation = {'id': elem[0], 'data': json.loads(self._decrypt(elem[1]))}
            data.append(allocation)
            if len(data) >= limit:
                break
        count = len(creds["data"].values())

        return count, data

    def get_allocation(self, allocation_id: str, user_info: dict) -> dict:
        client, path = self._login(user_info)
        creds = client.read_secret(path=path, mount_point=self.mount_point)
        if allocation_id in creds["data"]:
            return json.loads(self._decrypt(creds["data"][allocation_id]))
        else:
            return None

    def delete_allocation(self, allocation_id: str, user_info: dict = None):
        client, path = self._login(user_info)

        creds = client.read_secret(path=path, mount_point=self.mount_point)
        if allocation_id in creds["data"]:
            del creds["data"][allocation_id]
            if creds["data"]:
                response = client.create_or_update_secret(path,
                                                          creds["data"],
                                                          method="PUT",
                                                          mount_point=self.mount_point)
            else:
                if self.kv_ver == 1:
                    response = client.delete_secret(path,
                                                    mount_point=self.mount_point)
                else:
                    response = client.delete_metadata_and_all_versions(path,
                                                                       mount_point=self.mount_point)
            response.raise_for_status()

    def replace_allocation(self, data: dict, user_info: dict, allocation_id: str = None) -> str:
        client, path = self._login(user_info)
        try:
            creds = client.read_secret(path=path, mount_point=self.mount_point)
        except Exception:
            creds = None

        if allocation_id is None:
            allocation_id = str(uuid.uuid4())

        if creds:
            old_data = creds["data"]
            if allocation_id in creds["data"]:
                allocation_data = json.loads(self._decrypt(creds["data"][allocation_id]))
                allocation_data.update(data)
                creds["data"][allocation_id] = allocation_data
            else:
                old_data[allocation_id] = data
        else:
            old_data = {allocation_id: data}

        old_data[allocation_id] = self._encrypt(json.dumps(old_data[allocation_id]))
        response = client.create_or_update_secret(path,
                                                  old_data,
                                                  mount_point=self.mount_point)

        response.raise_for_status()
        return allocation_id
