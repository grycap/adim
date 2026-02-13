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
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from awm.oidc.client import OpenIDClient

# Middleware de seguridad HTTP para Bearer Token
security = HTTPBearer(
    scheme_name="OIDC",
    description="OpenID Connect access token for authentication",
    bearerFormat="JWT"
)
logger = logging.getLogger(__name__)


OIDC_ISSUERS = os.getenv("OIDC_ISSUERS", "")
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE", None)
OIDC_GROUPS = os.getenv("OIDC_GROUPS", "")


def authenticate(
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    token = credentials.credentials
    user_info = check_OIDC(token)
    if user_info is None:
        raise HTTPException(status_code=401, detail="Authorization required")
    return user_info


def check_OIDC(token):
    try:
        expired, _ = OpenIDClient.is_access_token_expired(token)
        if expired:
            raise HTTPException(status_code=401, detail="Token expired")

        # Check issuer if specified
        if OIDC_ISSUERS:
            issuer = OpenIDClient.get_token_claim(token, "iss")
            if issuer not in OIDC_ISSUERS.split(","):
                raise HTTPException(status_code=401, detail="Invalid token issuer")

        # Check audience if specified
        if OIDC_AUDIENCE:
            found = False
            audience = OpenIDClient.get_token_claim(token, "aud")
            if audience:
                for aud in audience.split(","):
                    if aud == OIDC_AUDIENCE:
                        found = True
                        logger.debug("Audience %s successfully checked." % OIDC_AUDIENCE)
                        break
            if not found:
                logger.error("Audience %s not found in access token." % OIDC_AUDIENCE)
                raise HTTPException(status_code=401, detail="Invalid token audience")

        success, user_info = OpenIDClient.get_user_info_request(token)
        if not success:
            return None

        if OIDC_GROUPS:
            user_groups = user_info.get('groups',
                                        user_info.get('entitlement',
                                                      user_info.get('eduperson_entitlement', [])))
            if not set(OIDC_GROUPS.split(",")).issubset(user_groups):
                logger.debug("No match on group membership. User group membership: %s", user_groups)
                raise HTTPException(status_code=401, detail="Invalid token groups")

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error checking OIDC token")
        return None

    user_info["token"] = token
    return user_info
