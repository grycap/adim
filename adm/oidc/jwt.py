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

import json
import base64
import re


class JWT(object):

    @staticmethod
    def b64d(b):
        """Decode some base64-encoded bytes.

        Raises Exception if the string contains invalid characters or padding.

        :param b: bytes
        """

        cb = b.rstrip(b"=")  # shouldn't but there you are

        # Python's base64 functions ignore invalid characters, so we need to
        # check for them explicitly.
        b64_re = re.compile(b"^[A-Za-z0-9_-]*$")
        if not b64_re.match(cb):
            raise Exception(cb, "base64-encoded data contains illegal characters")

        if cb == b:
            b = JWT.add_padding(b)

        return base64.urlsafe_b64decode(b)

    @staticmethod
    def add_padding(b):
        # add padding chars
        m = len(b) % 4
        if m == 1:
            # NOTE: for some reason b64decode raises *TypeError* if the
            # padding is incorrect.
            raise Exception(b, "incorrect padding")
        elif m == 2:
            b += b"=="
        elif m == 3:
            b += b"="
        return b

    @staticmethod
    def get_info(token):
        """
        Unpacks a JWT into its parts and base64 decodes the parts
        individually, returning the part 1 json decoded, where the
        token info is stored.

        :param token: The JWT token
        """
        part = tuple(token.encode("utf-8").split(b"."))
        part = [JWT.b64d(p) for p in part]
        return json.loads(part[1].decode("utf-8"))
