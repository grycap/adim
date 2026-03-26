# ADM Testing with the Robot Framework

This directory provides an automated Robot Framework suite to validate a deployed service that fulfills the [EOSC Application Deployment Management API](https://github.com/EGI-Federation/eosc-application-deployment-manager)..

## Getting Started

### Prerequisites

Before running the tests, ensure you have the following tools installed:

- Python 3.8+
- Robot Framework
- Robot Framework RequestsLibrary

Install dependencies with:

```bash
pip install -r requirements.txt
```

### Setting Up the Configuration File

Create a `.env.yaml` file according to `env-template.yaml`.

Required values:

- `adm_endpoint`: Base URL of the ADM instance (for example `https://adm.example.org`)
- `oidc_access_token`: OIDC access token used as `Authorization: Bearer <token>`
- `allocation_to_create`: JSON payload used by tests to create an allocation. Default is `{"kind":"DummyEnvironment"}`. This kind of Allocation is not defined in the ADM standard
but is defined in the ADIM service for convenience to perform these tests. Replace with
any Allocation supported by the underlying service.

## Running Tests

Run the full suite:

```bash
robot -V .env.yaml -d results tests
```

Run only the ADM API suite:

```bash
robot -V .env.yaml -d results tests/im-api.robot
```

## Covered Endpoints

The suite currently exercises these OpenAPI paths:

- `GET /version`
- `GET /allocations`
- `POST /allocations`
- `GET /allocation/{allocation_id}`
- `PUT /allocation/{allocation_id}`
- `DELETE /allocation/{allocation_id}`
- `GET /applications`
- `GET /application/{application_id}` (only when applications are available)
- `GET /deployments`
- `POST /deployments`
- `GET /deployment/{deployment_id}`
- `DELETE /deployment/{deployment_id}`

## Test Reports and Logs

After running tests, Robot outputs:

- Report: `report.html`
- Log: `log.html`

## Documentation

- [Robot Framework User Guide](https://robotframework.org)

## License

This project is licensed under the Apache 2.0 License. See `LICENSE` for details.
