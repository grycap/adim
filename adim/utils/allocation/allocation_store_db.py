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
import json
import time
import uuid
from typing import List, Tuple
from cryptography.fernet import Fernet
from adim.utils.db import DataBase
from .allocation_store import AllocationStore
from adim.utils import DBConnectionException


class AllocationStoreDB(AllocationStore):

    DEFAULT_URL = "file:///tmp/adim.db"

    def __init__(self, db_url, key: str | None = None, table_name: str = "allocations"):
        if table_name not in {"allocations", "public_allocations"}:
            raise ValueError("Invalid allocations table name")
        self.table_name = table_name
        self.key = None
        if key:
            self.key = Fernet(key)
        self.db = DataBase(db_url)
        if self.db.connect():
            self._init_table(self.db, table_name)
            self.db.close()
        else:
            raise DBConnectionException()

    def _encrypt(self, message):
        if self.key:
            return self.key.encrypt(message.encode()).decode()
        else:
            return message

    def _decrypt(self, message):
        if self.key:
            if isinstance(message, str):
                message = message.encode()
            return self.key.decrypt(message).decode()
        else:
            return message

    def _encode_data(self, data):
        """Keep Mongo documents as dictionaries unless encryption is enabled."""
        if self.key:
            return self._encrypt(json.dumps(data, sort_keys=True))
        return data

    def _decode_data(self, data):
        """Decode either a legacy Mongo dictionary or encrypted JSON."""
        if isinstance(data, dict):
            return data
        return json.loads(self._decrypt(data))

    @staticmethod
    def _init_table(db: DataBase, table_name: str = "allocations") -> bool:
        """Creates de database."""
        if not db.table_exists(table_name):
            adim.logger.info(f"Creating {table_name} table")
            if db.db_type == DataBase.MYSQL:
                db.execute(f"CREATE TABLE IF NOT EXISTS {table_name} (id VARCHAR(255) PRIMARY KEY, data TEXT, "
                           "owner VARCHAR(255), created TIMESTAMP)")
            elif db.db_type == DataBase.SQLITE:
                db.execute(f"CREATE TABLE IF NOT EXISTS {table_name} (id TEXT PRIMARY KEY, data TEXT, "
                           "owner VARCHAR(255), created TIMESTAMP)")
            elif db.db_type == DataBase.MONGO:
                db.connection.create_collection(table_name)
                db.connection[table_name].create_index([("id", 1), ("owner", 1)], unique=True)
            return True
        return False

    def list_allocations(self, user_info: dict, from_: int, limit: int) -> Tuple[int, List[dict]]:
        if self.db.connect():
            allocations = []
            if self.db.db_type == DataBase.MONGO:
                res = self.db.find(self.table_name, filt={"owner": user_info['sub']},
                                   projection={"data": True, "id": True}, sort=[('created', -1)])
                for count, elem in enumerate(res):
                    if from_ > count:
                        continue
                    allocations.append({"id": elem["id"], "data": self._decode_data(elem["data"])})
                    if len(allocations) >= limit:
                        break
                count = len(res)
            else:
                sql = f"SELECT id, data FROM {self.table_name} WHERE owner = %s order by created LIMIT %s OFFSET %s"
                res = self.db.select(sql, (user_info['sub'], limit, from_))
                for elem in res:
                    allocations.append({"id": elem[0], "data": json.loads(self._decrypt(elem[1]))})
                res = self.db.select(f"SELECT count(id) from {self.table_name} WHERE owner = %s", (user_info['sub'],))
                count = res[0][0] if res else 0
            self.db.close()
            return count, allocations

        raise DBConnectionException()

    def get_allocation(self, allocation_id: str, user_info: dict) -> dict:
        if self.db.connect():
            if self.db.db_type == DataBase.MONGO:
                res = self.db.find(self.table_name, {"id": allocation_id, "owner": user_info['sub']},
                                   {"id": True, "data": True})
            else:
                res = self.db.select(f"SELECT id, data FROM {self.table_name} WHERE id = %s and owner = %s",
                                     (allocation_id, user_info['sub']))
            self.db.close()
            if res:
                if self.db.db_type == DataBase.MONGO:
                    return self._decode_data(res[0]["data"])
                else:
                    return json.loads(self._decrypt(res[0][1]))
            else:
                return None

        raise DBConnectionException()

    def delete_allocation(self, allocation_id: str, user_info: dict):
        if self.db.connect():
            if self.db.db_type == DataBase.MONGO:
                self.db.delete(self.table_name, {"id": allocation_id, "owner": user_info['sub']})
            else:
                self.db.execute(f"DELETE FROM {self.table_name} WHERE id = %s and owner = %s",
                                (allocation_id, user_info['sub']))
            self.db.close()
        else:
            raise DBConnectionException()

    def check_allocation_exists(self, data: dict, user_info: dict) -> str:
        if self.db.connect():
            if self.db.db_type == DataBase.MONGO:
                res = self.db.find(self.table_name, {"owner": user_info['sub']}, {"id": True, "data": True})
                matches = [elem for elem in res if self._decode_data(elem["data"]) == data]
            else:
                res = self.db.select(f"SELECT id, data FROM {self.table_name} WHERE owner = %s", (user_info['sub'],))
                matches = [elem for elem in res if json.loads(self._decrypt(elem[1])) == data]
            self.db.close()
            if matches:
                return matches[0]["id"] if self.db.db_type == DataBase.MONGO else matches[0][0]
            else:
                return ""

        raise DBConnectionException()

    def replace_allocation(self, data: dict, user_info: dict, allocation_id: str | None = None) -> str:
        table_name = getattr(self, "table_name", "allocations")
        if self.db.connect():
            if self.db.db_type == DataBase.MONGO:
                if allocation_id is None:  # new allocation
                    allocation_id = str(uuid.uuid4())
                    replace = {"id": allocation_id, "data": self._encode_data(data),
                               "owner": user_info['sub'],
                               "created": time.time()}
                else:  # update existing allocation
                    replace = {"id": allocation_id, "data": self._encode_data(data),
                               "owner": user_info['sub']}
                self.db.replace(table_name, {"id": allocation_id, "owner": user_info['sub']}, replace)
            else:
                if allocation_id is None:  # new allocation
                    allocation_id = str(uuid.uuid4())
                    sql = f"replace into {table_name} (id, data, owner, created) values (%s, %s, %s, now())"
                    values = (allocation_id, self._encrypt(json.dumps(data, sort_keys=True)), user_info['sub'])
                else:  # update existing allocation
                    sql = f"update {table_name} set data = %s where id = %s and owner = %s"
                    values = (self._encrypt(json.dumps(data, sort_keys=True)), allocation_id, user_info['sub'])
                self.db.execute(sql, values)
            self.db.close()
            return allocation_id

        raise DBConnectionException()
