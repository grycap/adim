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
from awm.utils.tool.tool_store import ToolStore
from awm.utils.allocation.allocation_store import AllocationStore

__version__ = "0.4.0"

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
allocation_store = AllocationStore.get_allocation_store()

# Initialize deployments manager
deployments_manager = DeploymentsManager.get_deployments_manager()

# Initialize tool store
tool_store = ToolStore.get_tool_store()
