# ADIM

[![Test ADIM](https://github.com/grycap/adim/actions/workflows/main.yaml/badge.svg)](https://github.com/grycap/adim/actions/workflows/main.yaml)
[![SQAaaS badge shields.io](https://github.com/EOSC-synergy/adim.assess.sqaaas/raw/v0.4.0/.badge/status_shields.svg)](https://sqaaas.eosc-synergy.eu/#/full-assessment/report/https://raw.githubusercontent.com/eosc-synergy/adim.assess.sqaaas/v0.4.0/.report/assessment_output.json)

## Overview

Implements EOSC Application Deployment Management API.

## Requirements

Python 3.5.2+

## Configuration

Set this environment variables to configure the ADIM service:

```bash
LOG_LEVEL=info
IM_URL=http://localhost:8800
DB_URL=file:///tmp/adim.db
# db or vault
ALLOCATION_STORE=db
VAULT_URL=https://secrets.egi.eu
ENCRYPT_KEY=3JSvUdOsAlvSNVYvBwHWE-iKdWkhq4C_LmjRcpuycT0=
#ROOT_PATH=/adim
# git or rc
TOOL_STORE=git
# In case of git, the repository where to store the tools
TOOLS_REPO="https://github.com/grycap/tosca/blob/eosc_lot1/templates/"
# In case of RC, the URL of the Resource Catalog API
RESOURCE_CATALOG="https://providers.sandbox.eosc-beyond.eu/api"
# Comma separated list of OIDC issuers to accept tokens from
OIDC_ISSUERS="https://aai.egi.eu/auth/realms/egi,https://aai-demo.egi.eu/auth/realms/egi,https://proxy.aai.open-science-cloud.ec.europa.eu"
# Audience to check in the token, if not specified, no audience check will be performed
#OIDC_AUDIENCE=adim
# Comma separated list of groups to check in the token, if not specified, no group check will be performed
#OIDC_GROUPS="eos-beyond.eu"
```

Or you can set an `.env` file as the `.env.example` provided.

## Usage

To run the server, please execute the following from the root directory:

```bash
pip3 install -r requirements.txt
python3 -m adim
```

and open your browser to here:

```bash
http://localhost:8080/
```

## Running with Docker

To run the server on a Docker container, please execute the following from the
root directory:

```bash
# building the image
docker build -t adim .

# starting up a container
docker run -p 8080:8080 adim

# starting up a setting the IM_URL variable
docker run -p 8080:8080 -e IM_URL=https://im.egi.eu/im ghcr.io/grycap/adim

```
