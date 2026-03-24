# ADIM Testing with the Robot Framework

This directory provides an automated Robot Framework suite to validate a deployed ADIM service.

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

- `adim_endpoint`: Base URL of the ADIM instance (for example `https://adim.example.org`)
- `oidc_access_token`: OIDC access token used as `Authorization: Bearer <token>`

## Running Tests

Run the full suite:

```bash
robot -V .env.yaml -d results tests
```

Run only the ADIM API suite:

```bash
robot -V .env.yaml -d results tests/im-api.robot
```

## Covered Endpoints

The suite currently exercises these OpenAPI paths:

- `GET /version`
- `GET /allocations`
- `POST /allocations`
- `GET /allocation/{allocation_id}`
- `DELETE /allocation/{allocation_id}`
- `GET /applications`
- `GET /application/{application_id}` (only when applications are available)
- `GET /deployments`
- `POST /deployments` negative path with non-existing application (expects `400`)

## Test Reports and Logs

After running tests, Robot outputs:

- Report: `report.html`
- Log: `log.html`

## Documentation

- [Robot Framework User Guide](https://robotframework.org)

## License

This project is licensed under the Apache 2.0 License. See `LICENSE` for details.