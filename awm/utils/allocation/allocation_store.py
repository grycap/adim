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
