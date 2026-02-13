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
import awm
from typing import List


class AllocationStore():

    def list_allocations(self, user_info: dict, from_: int, limit: int) -> List[dict]:
        raise NotImplementedError()

    def get_allocation(self, allocation_id: str, user_info: dict) -> dict:
        raise NotImplementedError()

    def delete_allocation(self, allocation_id: str, user_info: dict = None):
        raise NotImplementedError()

    def replace_allocation(self, data: dict, user_info: dict, allocation_id: str = None) -> str:
        raise NotImplementedError()

    @staticmethod
    def get_allocation_store() -> 'AllocationStore':
        ALLOCATION_STORE = os.getenv("ALLOCATION_STORE", "db")
        if ALLOCATION_STORE == "db":
            from awm.utils.allocation.allocation_store_db import AllocationStoreDB
            DB_URL = os.getenv("DB_URL", AllocationStoreDB.DEFAULT_URL)
            allocation_store = AllocationStoreDB(DB_URL)
            awm.logger.info(f"Using AllocationStoreDB with URL: {DB_URL}")
        elif ALLOCATION_STORE == "vault":
            from awm.utils.allocation.allocation_store_vault import AllocationStoreVault
            VAULT_URL = os.getenv("VAULT_URL", AllocationStoreVault.DEFAULT_URL)
            ENCRYPT_KEY = os.getenv("ENCRYPT_KEY", AllocationStoreVault.DEFAULT_KEY)
            allocation_store = AllocationStoreVault(VAULT_URL, key=ENCRYPT_KEY)
            awm.logger.info(f"Using AllocationStoreVault with URL: {VAULT_URL}")
        else:
            raise Exception(f"Allocation store '{ALLOCATION_STORE}' is not supported")
        return allocation_store