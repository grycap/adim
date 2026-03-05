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
from typing import List, Tuple


class AllocationStore():

    def list_allocations(self, user_info: dict, from_: int, limit: int) -> Tuple[int, List[dict]]:
        raise NotImplementedError()

    def get_allocation(self, allocation_id: str, user_info: dict) -> dict:
        raise NotImplementedError()

    def delete_allocation(self, allocation_id: str, user_info: dict):
        raise NotImplementedError()

    def replace_allocation(self, data: dict, user_info: dict, allocation_id: str | None = None) -> str:
        raise NotImplementedError()

    def check_allocation_exists(self, data: dict, user_info: dict) -> str:
        raise NotImplementedError()

    @staticmethod
    def get_allocation_store() -> 'AllocationStore':
        store_type = os.getenv("ALLOCATION_STORE", "db")
        if store_type == "db":
            from adim.utils.allocation.allocation_store_db import AllocationStoreDB
            db_url = os.getenv("DB_URL", AllocationStoreDB.DEFAULT_URL)
            allocation_store = AllocationStoreDB(db_url)
            adim.logger.info(f"Using AllocationStoreDB with URL: {db_url}")
        elif store_type == "vault":
            from adim.utils.allocation.allocation_store_vault import AllocationStoreVault
            vault_url = os.getenv("VAULT_URL", AllocationStoreVault.DEFAULT_URL)
            encrypt_key = os.getenv("ENCRYPT_KEY", None)
            allocation_store = AllocationStoreVault(vault_url, key=encrypt_key)
            adim.logger.info(f"Using AllocationStoreVault with URL: {vault_url}")
        else:
            raise ValueError(f"Allocation store '{store_type}' is not supported")
        return allocation_store
