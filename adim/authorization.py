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

import logging
import os
from typing import List
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from adim.oidc.client import OpenIDClient

# Middleware de seguridad HTTP para Bearer Token
security = HTTPBearer(
    scheme_name="OIDC",
    description="OpenID Connect access token for authentication",
    bearerFormat="JWT"
)
logger = logging.getLogger(__name__)


OIDC_ISSUERS = os.getenv("OIDC_ISSUERS", "").split(",")
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE", None)
OIDC_GROUPS = os.getenv("OIDC_GROUPS", "")
OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID", None)
OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", None)


def authenticate(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> dict:
    token = credentials.credentials
    user_info = check_OIDC(token)
    if user_info is None:
        raise HTTPException(status_code=401, detail="Authorization required")
    return user_info


def get_user_groups(token: str | dict, user_info: dict) -> List[str]:
    user_groups = []
    for claim in ["groups", "entitlement", "eduperson_entitlement"]:
        user_groups = OpenIDClient.get_token_claim(token, claim)
        if user_groups:
            break
    if not user_groups and user_info:
        for claim in ["groups", "entitlement", "eduperson_entitlement"]:
            user_groups = user_info.get(claim, [])
            if user_groups:
                break
    return extract_groups_from_entitlements(user_groups)


def check_OIDC(token: str) -> dict | None:
    try:
        user_info = {}
        decoded_token = None
        expired, _ = OpenIDClient.is_access_token_expired(token)
        if expired:
            raise HTTPException(status_code=401, detail="Token expired")

        if OIDC_CLIENT_ID and OIDC_CLIENT_SECRET and len(OIDC_ISSUERS) == 1:
            success, decoded_token = OpenIDClient.get_token_introspection(token,
                                                                          OIDC_ISSUERS[0],
                                                                          OIDC_CLIENT_ID,
                                                                          OIDC_CLIENT_SECRET)
            user_info["sub"] = OpenIDClient.get_token_claim(token, "sub")
            if not success or not decoded_token.get("active", False):
                raise HTTPException(status_code=401, detail="Invalid token")
        else:
            # Check issuer if specified
            issuer = OpenIDClient.get_token_claim(token, "iss")
            if issuer not in OIDC_ISSUERS:
                raise HTTPException(status_code=401, detail="Invalid token issuer")

            success, user_info = OpenIDClient.get_user_info_request(token)
            if not success:
                raise HTTPException(status_code=401, detail=f"Error validating token: {user_info}")

        # Check audience if specified
        if OIDC_AUDIENCE:
            found = False
            audience = OpenIDClient.get_token_claim(token, "aud")
            if audience:
                for aud in audience.split(","):
                    if aud == OIDC_AUDIENCE:
                        found = True
                        logger.debug("Audience %s successfully checked.", OIDC_AUDIENCE)
                        break
            if not found:
                logger.error("Audience %s not found in access token.", OIDC_AUDIENCE)
                raise HTTPException(status_code=401, detail="Invalid token audience")

        if OIDC_GROUPS:
            user_groups = get_user_groups(decoded_token, user_info)
            if not any(group in user_groups for group in OIDC_GROUPS.split(',')):
                logger.debug("No match on group membership. User group membership: %s", user_groups)
                raise HTTPException(status_code=401, detail="Invalid token groups")

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error checking OIDC token")
        return None

    user_info["token"] = token
    return user_info


def extract_groups_from_entitlements(entitlements: List[str], vo_roles: List[str] = None) -> List[str]:
    groups = []
    for elem in entitlements:
        # format: urn:mace:egi.eu:group:eosc-synergy.eu:role=vm_operator#aai.egi.eu
        # or      urn:mace:egi.eu:group:demo.fedcloud.egi.eu:vm_operator:role=member#aai.egi.eu
        if elem.startswith('urn:mace:egi.eu:group:'):
            vo = elem[22:22 + elem[22:].find(':')]
            if vo and vo not in groups:
                if not vo_roles:
                    groups.append(vo)
                else:
                    for vo_role in vo_roles:
                        if f":role={vo_role}#" in elem or f":{vo_role}:" in elem:
                            groups.append(vo)
        elif elem.startswith('urn:egi.eu:group:'):
            vo = elem[17:]
            groups.append(vo)
        else:
            groups.append(elem)
    groups.sort()
    return groups
