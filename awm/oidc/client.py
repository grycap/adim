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

import requests
import time
from typing import Tuple
from awm.oidc.jwt import JWT


class OpenIDClient(object):

    ISSUER_CONFIG_CACHE = {}

    @staticmethod
    def get_openid_configuration(iss: str, verify_ssl: bool = False) -> dict:
        try:
            if iss in OpenIDClient.ISSUER_CONFIG_CACHE:
                return OpenIDClient.ISSUER_CONFIG_CACHE[iss]
            url = "%s/.well-known/openid-configuration" % iss
            resp = requests.request("GET", url, verify=verify_ssl)
            if resp.status_code != 200:
                return {"error": "Code: %d. Message: %s." % (resp.status_code, resp.text)}
            # Only store currently needed data
            OpenIDClient.ISSUER_CONFIG_CACHE[iss] = {"userinfo_endpoint": resp.json()["userinfo_endpoint"],
                                                     "introspection_endpoint": resp.json()["introspection_endpoint"]}
            return resp.json()
        except Exception as ex:
            return {"error": str(ex)}

    @staticmethod
    def get_user_info_request(token: str, verify_ssl: bool = False) -> Tuple[bool, dict | str]:
        """
        Get a the user info from a token
        """
        try:
            decoded_token = JWT().get_info(token)
            headers = {'Authorization': 'Bearer %s' % token}
            conf = OpenIDClient.get_openid_configuration(decoded_token['iss'], verify_ssl=False)
            resp = requests.request("GET", conf["userinfo_endpoint"], verify=verify_ssl, headers=headers)
            if resp.status_code != 200:
                return False, "Code: %d. Message: %s." % (resp.status_code, resp.text)
            return True, resp.json()
        except Exception as ex:
            return False, str(ex)

    @staticmethod
    def get_token_introspection(token: str, issuer: str, client_id: str, client_secret: str,
                                verify_ssl: bool = False) -> Tuple[bool, dict | str]:
        """
        Get token introspection
        """
        try:
            decoded_token = JWT().get_info(token)
            if not issuer:
                issuer = decoded_token['iss']
            conf = OpenIDClient.get_openid_configuration(issuer, verify_ssl=verify_ssl)
            url = "%s?token=%s&token_type_hint=access_token" % (conf["introspection_endpoint"], token)
            resp = requests.request("GET", url, verify=verify_ssl,
                                    auth=requests.auth.HTTPBasicAuth(client_id, client_secret))
            if resp.status_code != 200:
                return False, "Code: %d. Message: %s." % (resp.status_code, resp.text)
            return True, resp.json()
        except Exception as ex:
            return False, str(ex)

    @staticmethod
    def is_access_token_expired(token: str) -> Tuple[bool, str]:
        """
        Check if the current access token is expired
        """
        if token:
            try:
                decoded_token = JWT().get_info(token)
                now = int(time.time())
                expires = int(decoded_token['exp'])
                validity = expires - now
                if validity < 0:
                    return True, "Token expired"
                else:
                    return False, "Valid Token for %d seconds" % validity
            except Exception:
                return True, "Error getting token info"
        else:
            return True, "No token specified"

    @staticmethod
    def get_token_claim(token: str | dict, claim_name: str) -> str | None:
        """Get a specific claim from the token"""
        try:
            if isinstance(token, dict):
                return token.get(claim_name, None)
            else:
                return JWT().get_info(token).get(claim_name, None)
        except Exception:
            return None
