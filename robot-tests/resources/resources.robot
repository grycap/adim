*** Settings ***

Library    Collections
Library    DateTime
Library    RequestsLibrary
Library    String

*** Variables *** 

${ADIM_ENDPOINT}=       %{adim_endpoint}
${OIDC_ACCESS_TOKEN}=   %{oidc_access_token}
${ALLOCATION_TO_CREATE_RAW}=   %{allocation_to_create={"kind":"DummyEnvironment"}}

*** Keywords ***

Decode JWT Token
    [Documentation]    Decode a JWT token and returns its payload.
    [Arguments]    ${token}
    ${parts}=    Split String    ${token}    .
    ${payload_b64}=    Get From List    ${parts}    1
    ${decoded}=    Evaluate    __import__("json").loads(__import__("base64").urlsafe_b64decode("${payload_b64}" + "=" * (-len("${payload_b64}") % 4)).decode("utf-8"))
    RETURN    ${decoded}

Check JWT Expiration
    [Documentation]    Check if a JWT token includes an exp claim and is not expired.
    [Arguments]    ${token}
    ${status}    ${decoded_token}=    Run Keyword And Ignore Error    Decode JWT Token    ${token}
    Run Keyword If    '${status}' == 'FAIL'    Log    Token is not a JWT or could not be decoded; skipping expiration check.    WARN
    Return From Keyword If    '${status}' == 'FAIL'
    ${has_exp}=    Run Keyword And Return Status    Dictionary Should Contain Key    ${decoded_token}    exp
    Run Keyword If    not ${has_exp}    Log    JWT does not include exp claim; skipping expiration check.    WARN
    Return From Keyword If    not ${has_exp}
    ${expiry_time}=    Get From Dictionary    ${decoded_token}    exp
    ${current_time}=    Get Current Date    result_format=epoch
    Should Be True    ${expiry_time} > ${current_time}    Token is expired

Generate ADIM Auth Header
    [Documentation]    Build Authorization header for ADIM OpenID Connect Bearer auth.
    ${headers}=    Create Dictionary
    ...    Authorization=Bearer ${OIDC_ACCESS_TOKEN}
    ...    Content-Type=application/json
    RETURN    ${headers}

Get Configured Allocation Payload
    [Documentation]    Parse allocation payload from environment variable allocation_to_create.
    ${payload}=    Evaluate    __import__("json").loads(r'''${ALLOCATION_TO_CREATE_RAW}''')
    RETURN    ${payload}

Get Configured Allocation Kind
    [Documentation]    Return the expected kind from the configured allocation payload.
    ${payload}=    Get Configured Allocation Payload
    ${kind}=    Get From Dictionary    ${payload}    kind
    RETURN    ${kind}

Create Configured Allocation
    [Documentation]    Create an allocation using allocation_to_create payload and return the allocation id.
    [Arguments]    ${headers}
    ${payload}=    Get Configured Allocation Payload
    ${response}=    POST    ${ADIM_ENDPOINT}/allocations    headers=${headers}    json=${payload}    expected_status=anything
    Should Be True    ${response.status_code} == 201 or ${response.status_code} == 303

    IF    ${response.status_code} == 201
        ${json_payload}=    Set Variable    ${response.json()}
        ${allocation_id}=    Set Variable    ${json_payload}[id]
    ELSE
        ${location}=    Get From Dictionary    ${response.headers}    Location
        ${parts}=    Split String    ${location}    /
        ${allocation_id}=    Get From List    ${parts}    -1
    END

    RETURN    ${allocation_id}

Delete Allocation If Present
    [Documentation]    Delete an allocation id if present and ignore 404 in cleanup.
    [Arguments]    ${headers}    ${allocation_id}
    Return From Keyword If    '${allocation_id}' == 'None'
    ${response}=    DELETE    ${ADIM_ENDPOINT}/allocation/${allocation_id}    headers=${headers}    expected_status=anything
    Should Be True    ${response.status_code} == 200 or ${response.status_code} == 404

Assert Error Payload
    [Documentation]    Validate a standard ADIM error payload.
    [Arguments]    ${error}
    Dictionary Should Contain Key    ${error}    id
    Dictionary Should Contain Key    ${error}    description
    ${has_details}=    Run Keyword And Return Status    Dictionary Should Contain Key    ${error}    details
    IF    ${has_details}
        ${details_are_dict}=    Evaluate    isinstance($error["details"], dict)
        Should Be True    ${details_are_dict}
    END

Assert Reference Payload
    [Documentation]    Validate a reference object returned by the ADIM API.
    [Arguments]    ${reference}
    Dictionary Should Contain Key    ${reference}    id
    Dictionary Should Contain Key    ${reference}    infoLink
    Should Not Be Empty    ${reference}[id]
    Should Not Be Empty    ${reference}[infoLink]

Get One TOSCA Input For Deployment
    [Documentation]    Extract one input from topology_template.inputs and return a safe sample value.
    [Arguments]    ${blueprint}
    ${blueprint_dict}=    Evaluate    __import__("yaml").safe_load($blueprint) if isinstance($blueprint, str) else {}
    ${inputs_dict}=    Evaluate    $blueprint_dict.get("topology_template", {}).get("inputs", {}) if isinstance($blueprint_dict, dict) else {}
    ${has_inputs}=    Evaluate    isinstance($inputs_dict, dict) and len($inputs_dict) > 0
    IF    not ${has_inputs}
        RETURN    ${None}    ${None}
    END
    ${input_name}=    Evaluate    next(iter($inputs_dict.keys()))
    ${input_schema}=    Get From Dictionary    ${inputs_dict}    ${input_name}
    ${input_value}=    Evaluate    str(($input_schema.get("default") if isinstance($input_schema, dict) else None) if (($input_schema.get("default") if isinstance($input_schema, dict) else None) is not None) else ("true" if (isinstance($input_schema, dict) and $input_schema.get("type") == "boolean") else ("1" if (isinstance($input_schema, dict) and $input_schema.get("type") in ["integer", "float", "number"]) else "robot-ci")))
    RETURN    ${input_name}    ${input_value}
