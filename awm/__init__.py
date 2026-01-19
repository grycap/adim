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
import logging
from dotenv import load_dotenv
from awm.utils.deployment_manager import DeploymentsManager
from awm.utils.tool_store import ToolStore

__version__ = "1.0.0"

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "info")

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL.upper())
logger.propagate = False

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    handler.setLevel(LOG_LEVEL.upper())
    logger.addHandler(handler)

# Initialize allocation store
ALLOCATION_STORE = os.getenv("ALLOCATION_STORE", "db")

if ALLOCATION_STORE == "db":
    from awm.utils.allocation_store_db import AllocationStoreDB
    DB_URL = os.getenv("DB_URL", AllocationStoreDB.DEFAULT_URL)
    allocation_store = AllocationStoreDB(DB_URL)
    logger.info(f"Using AllocationStoreDB with URL: {DB_URL}")
elif ALLOCATION_STORE == "vault":
    from awm.utils.allocation_store_vault import AllocationStoreVault
    VAULT_URL = os.getenv("VAULT_URL", AllocationStoreVault.DEFAULT_URL)
    ENCRYPT_KEY = os.getenv("ENCRYPT_KEY", AllocationStoreVault.DEFAULT_KEY)
    allocation_store = AllocationStoreVault(VAULT_URL, key=ENCRYPT_KEY)
    logger.info(f"Using AllocationStoreVault with URL: {VAULT_URL}")
else:
    raise Exception(f"Allocation store '{ALLOCATION_STORE}' is not supported")

# Initialize deployments manager

IM_URL = os.getenv("IM_URL", "http://localhost:8800")
DB_URL = os.getenv("DB_URL", "file:///tmp/awm.db")

deployments_manager = DeploymentsManager(DB_URL, IM_URL)

# Initialize tool store

AWM_TOOLS_REPO = os.getenv("AWM_TOOLS_REPO", "https://github.com/grycap/tosca/blob/eosc_lot1/templates/")

tool_store = ToolStore(AWM_TOOLS_REPO)
