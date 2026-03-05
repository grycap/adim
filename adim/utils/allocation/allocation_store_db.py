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
from adim.utils.db import DataBase
from .allocation_store import AllocationStore
from adim.utils import DBConnectionException


class AllocationStoreDB(AllocationStore):

    DEFAULT_URL = "file:///tmp/adim.db"

    def __init__(self, db_url):
        self.db = DataBase(db_url)
        if self.db.connect():
            self._init_table(self.db)
            self.db.close()
        else:
            raise DBConnectionException()

    @staticmethod
    def _init_table(db: DataBase) -> bool:
        """Creates de database."""
        if not db.table_exists("allocations"):
            adim.logger.info("Creating allocations table")
            if db.db_type == DataBase.MYSQL:
                db.execute("CREATE TABLE IF NOT EXISTS allocations (id VARCHAR(255) PRIMARY KEY, data TEXT, "
                           "owner VARCHAR(255), created TIMESTAMP)")
            elif db.db_type == DataBase.SQLITE:
                db.execute("CREATE TABLE IF NOT EXISTS allocations (id TEXT PRIMARY KEY, data TEXT, "
                           "owner VARCHAR(255), created TIMESTAMP)")
            elif db.db_type == DataBase.MONGO:
                db.connection.create_collection("allocations")
                db.connection["allocations"].create_index([("id", 1), ("owner", 1)], unique=True)
            return True
        return False

    def list_allocations(self, user_info: dict, from_: int, limit: int) -> Tuple[int, List[dict]]:
        if self.db.connect():
            allocations = []
            if self.db.db_type == DataBase.MONGO:
                res = self.db.find("allocations", filt={"owner": user_info['sub']},
                                   projection={"data": True, "id": True}, sort=[('created', -1)])
                for count, elem in enumerate(res):
                    if from_ > count:
                        continue
                    allocations.append(elem)
                    if len(allocations) >= limit:
                        break
                count = len(res)
            else:
                sql = "SELECT id, data FROM allocations WHERE owner = %s order by created LIMIT %s OFFSET %s"
                res = self.db.select(sql, (user_info['sub'], limit, from_))
                for elem in res:
                    allocations.append({"id": elem[0], "data": json.loads(elem[1])})
                res = self.db.select("SELECT count(id) from allocations WHERE owner = %s", (user_info['sub'],))
                count = res[0][0] if res else 0
            self.db.close()
            return count, allocations

        raise DBConnectionException()

    def get_allocation(self, allocation_id: str, user_info: dict) -> dict:
        if self.db.connect():
            if self.db.db_type == DataBase.MONGO:
                res = self.db.find("allocations", {"id": allocation_id, "owner": user_info['sub']},
                                   {"id": True, "data": True})
            else:
                res = self.db.select("SELECT id, data FROM allocations WHERE id = %s and owner = %s",
                                     (allocation_id, user_info['sub']))
            self.db.close()
            if res:
                if self.db.db_type == DataBase.MONGO:
                    return res[0]["data"]
                else:
                    return json.loads(res[0][1])
            else:
                return None

        raise DBConnectionException()

    def delete_allocation(self, allocation_id: str, user_info: dict):
        if self.db.connect():
            if self.db.db_type == DataBase.MONGO:
                self.db.delete("allocations", {"id": allocation_id})
            else:
                self.db.execute("DELETE FROM allocations WHERE id = %s", (allocation_id,))
            self.db.close()
        else:
            raise DBConnectionException()

    def check_allocation_exists(self, data: dict, user_info: dict) -> str:
        if self.db.connect():
            if self.db.db_type == DataBase.MONGO:
                res = self.db.find("allocations", {"data": data, "owner": user_info['sub']}, {"id": True})
            else:
                res = self.db.select("SELECT id FROM allocations WHERE data = %s and owner = %s",
                                     (json.dumps(data, sort_keys=True), user_info['sub']))
            self.db.close()
            if res:
                if self.db.db_type == DataBase.MONGO:
                    return res[0]["id"]
                else:
                    return res[0][0]
            else:
                return ""

        raise DBConnectionException()

    def replace_allocation(self, data: dict, user_info: dict, allocation_id: str | None = None) -> str:
        if self.db.connect():
            if self.db.db_type == DataBase.MONGO:
                if allocation_id is None:  # new allocation
                    allocation_id = str(uuid.uuid4())
                    replace = {"id": allocation_id, "data": data,
                               "owner": user_info['sub'],
                               "created": time.time()}
                else:  # update existing allocation
                    replace = {"id": allocation_id, "data": data,
                               "owner": user_info['sub']}
                self.db.replace("allocations", {"id": allocation_id}, replace)
            else:
                if allocation_id is None:  # new allocation
                    allocation_id = str(uuid.uuid4())
                    sql = "replace into allocations (id, data, owner, created) values (%s, %s, %s, now())"
                    values = (allocation_id, json.dumps(data, sort_keys=True), user_info['sub'])
                else:  # update existing allocation
                    sql = "update allocations set data = %s where id = %s"
                    values = (json.dumps(data, sort_keys=True), allocation_id)
                self.db.execute(sql, values)
            self.db.close()
            return allocation_id

        raise DBConnectionException()
