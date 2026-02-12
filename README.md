# AWM

## Overview

Implements EOSC Application Workflow Management API.

## Requirements

Python 3.5.2+

## Configuration

Set this environment variables to configure the AWM service:

```bash
LOG_LEVEL=info
IM_URL=http://localhost:8800
DB_URL=file:///tmp/awm.db
# db or vault
ALLOCATION_STORE=db
VAULT_URL=https://secrets.egi.eu
ENCRYPT_KEY=3JSvUdOsAlvSNVYvBwHWE-iKdWkhq4C_LmjRcpuycT0=
#ROOT_PATH=/awm
# git or rc
TOOL_STORE=git
# In case of git, the repository where to store the tools
AWM_TOOLS_REPO="https://github.com/grycap/tosca/blob/eosc_lot1/templates/"
# In case of RC, the URL of the Resource Catalog API
RESOURCE_CATALOG="https://providers.sandbox.eosc-beyond.eu/api"
```

Or you can set an `.env` file as the `.env.example` provided.

## Usage

To run the server, please execute the following from the root directory:

```bash
pip3 install -r requirements.txt
python3 -m awm
```

and open your browser to here:

```bash
http://localhost:8080/
```

## Running with Docker

To run the server on a Docker container, please execute the following from the root directory:

```bash
# building the image
docker build -t awm .

# starting up a container
docker run -p 8080:8080 awm

# starting up a setting the IM_URL variable
docker run -p 8080:8080 -e IM_URL=https://appsgrycap.i3m.upv.es/im-dev/ ghcr.io/grycap/awm

```
