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

class ConnectionException(Exception):
    def __init__(self, msg="Connection failed"):
        Exception.__init__(self, msg)
        self.message = msg


class DBConnectionException(ConnectionException):
    def __init__(self, msg="Database connection failed"):
        ConnectionException.__init__(self, msg)
        self.message = msg


class RepositoryConnectionException(ConnectionException):
    def __init__(self, msg="Repository connection failed"):
        ConnectionException.__init__(self, msg)
        self.message = msg


class VaultConnectionException(ConnectionException):
    def __init__(self, msg="Vault Connection failed"):
        ConnectionException.__init__(self, msg)
        self.message = msg