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

    def replace_allocation(self, data: dict, user_info: dict, allocation_id: str | None = None,
                           scope: str = "private") -> str:
        raise NotImplementedError()

    def check_allocation_exists(self, data: dict, user_info: dict, scope: str = "private") -> str:
        raise NotImplementedError()

    @staticmethod
    def get_allocation_store() -> 'AllocationStore':
        store_type = os.getenv("ALLOCATION_STORE", "db")
        db_key = os.getenv("DB_ENCRYPT_KEY")
        from adim.utils.allocation.allocation_store_db import AllocationStoreDB
        if store_type == "db":
            db_url = os.getenv("DB_URL", AllocationStoreDB.DEFAULT_URL)
            private_store = AllocationStoreDB(db_url, key=db_key)
            adim.logger.info(f"Using AllocationStoreDB with URL: {db_url}")
        elif store_type == "vault":
            from adim.utils.allocation.allocation_store_vault import AllocationStoreVault
            vault_url = os.getenv("VAULT_URL", AllocationStoreVault.DEFAULT_URL)
            private_store = AllocationStoreVault(vault_url, key=os.getenv("VAULT_ENCRYPT_KEY"))
            adim.logger.info(f"Using AllocationStoreVault with URL: {vault_url}")
        else:
            raise ValueError(f"Allocation store '{store_type}' is not supported")
        # Public allocations always use a separate DB table/collection.
        public_store = AllocationStoreDB(
            os.getenv("DB_URL", AllocationStoreDB.DEFAULT_URL),
            key=db_key,
            table_name="public_allocations",
        )
        return CompositeAllocationStore(private_store, public_store)


class CompositeAllocationStore(AllocationStore):
    """Routes private allocations to their configured backend and public ones to DB."""

    PUBLIC_OWNER = "__adim_public_allocations__"

    def __init__(self, private_store: AllocationStore, public_store: AllocationStore):
        self.private_store = private_store
        self.public_store = public_store

    @classmethod
    def is_public_admin(cls, user_info: dict) -> bool:
        return bool(user_info.get("admin", False))

    @classmethod
    def _is_admin(cls, user_info: dict) -> bool:
        return cls.is_public_admin(user_info)

    @classmethod
    def _public_user(cls):
        return {"sub": cls.PUBLIC_OWNER}

    def list_allocations(self, user_info, from_, limit):
        _, private = self.private_store.list_allocations(user_info, 0, 1000000)
        _, public = self.public_store.list_allocations(self._public_user(), 0, 1000000)
        combined = ([{**item, "scope": "private"} for item in private]
                    + [{**item, "scope": "public"} for item in public])
        return len(combined), combined[from_:from_ + limit]

    def get_allocation(self, allocation_id, user_info):
        private = self.private_store.get_allocation(allocation_id, user_info)
        if private is not None:
            return private
        return self.public_store.get_allocation(allocation_id, self._public_user())

    def is_public_allocation(self, allocation_id, user_info):
        return self.public_store.get_allocation(allocation_id, self._public_user()) is not None

    def delete_allocation(self, allocation_id, user_info):
        if self.private_store.get_allocation(allocation_id, user_info) is not None:
            return self.private_store.delete_allocation(allocation_id, user_info)
        if not self._is_admin(user_info):
            raise PermissionError("Only configured public allocation administrators may delete public allocations")
        return self.public_store.delete_allocation(allocation_id, self._public_user())

    def replace_allocation(self, data, user_info, allocation_id=None, scope="private"):
        if allocation_id is None:
            if scope == "public":
                if not self._is_admin(user_info):
                    raise PermissionError("Only configured public allocation administrators may publish allocations")
                return self.public_store.replace_allocation(data, self._public_user())
            return self.private_store.replace_allocation(data, user_info)

        private = self.private_store.get_allocation(allocation_id, user_info)
        if private is not None:
            return self.private_store.replace_allocation(data, user_info, allocation_id)
        public = self.public_store.get_allocation(allocation_id, self._public_user())
        if public is None:
            raise KeyError("Allocation not found")
        if not self._is_admin(user_info):
            raise PermissionError("Only configured public allocation administrators may update public allocations")
        return self.public_store.replace_allocation(data, self._public_user(), allocation_id)

    def check_allocation_exists(self, data, user_info, scope="private"):
        if scope == "public":
            if not self._is_admin(user_info):
                raise PermissionError("Only configured public allocation administrators may publish allocations")
            return self.public_store.check_allocation_exists(data, self._public_user())
        return self.private_store.check_allocation_exists(data, user_info)
