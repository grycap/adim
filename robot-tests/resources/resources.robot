*** Settings ***

Library    Collections
Library    DateTime
Library    RequestsLibrary
Library    String

*** Variables *** 

${ADM_ENDPOINT}=       %{adm_endpoint}
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

Generate ADM Auth Header
    [Documentation]    Build Authorization header for ADM OpenID Connect Bearer auth.
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

Assert Allocation Id Payload
    [Documentation]    Validate AllocationId payload returned on successful allocation creation.
    [Arguments]    ${payload}
    Dictionary Should Contain Key    ${payload}    id
    Dictionary Should Contain Key    ${payload}    infoLink
    Should Not Be Empty    ${payload}[id]
    Should Not Be Empty    ${payload}[infoLink]
    ${id_is_string}=    Evaluate    isinstance($payload["id"], str)
    Should Be True    ${id_is_string}
    ${link_is_string}=    Evaluate    isinstance($payload["infoLink"], str)
    Should Be True    ${link_is_string}
    ${has_kind}=    Run Keyword And Return Status    Dictionary Should Contain Key    ${payload}    kind
    IF    ${has_kind}
        Should Be Equal As Strings    ${payload}[kind]    AllocationId
    END
    Should Match Regexp    ${payload}[infoLink]    ^https?://.+
    Should Contain    ${payload}[infoLink]    /allocation/
    Should Contain    ${payload}[infoLink]    ${payload}[id]

Create Configured Allocation
    [Documentation]    Create an allocation using allocation_to_create payload and return the allocation id.
    [Arguments]    ${headers}
    ${payload}=    Get Configured Allocation Payload
    ${response}=    POST    ${ADM_ENDPOINT}/allocations    headers=${headers}    json=${payload}    expected_status=anything
    Should Be True    ${response.status_code} == 201 or ${response.status_code} == 303

    IF    ${response.status_code} == 201
        ${json_payload}=    Set Variable    ${response.json()}
        Assert Allocation Id Payload    ${json_payload}
        Assert Link Returns Object    ${headers}    ${json_payload}[infoLink]    ${json_payload}[id]
        ${allocation_id}=    Set Variable    ${json_payload}[id]
    ELSE
        ${location}=    Get From Dictionary    ${response.headers}    Location
        Should Not Be Empty    ${location}
        Should Contain    ${location}    /allocation/
        ${parts}=    Split String    ${location}    /
        ${allocation_id}=    Get From List    ${parts}    -1
    END

    RETURN    ${allocation_id}

Delete Allocation If Present
    [Documentation]    Delete an allocation id if present and ignore 404 in cleanup.
    [Arguments]    ${headers}    ${allocation_id}
    Return From Keyword If    '${allocation_id}' == 'None'
    ${response}=    DELETE    ${ADM_ENDPOINT}/allocation/${allocation_id}    headers=${headers}    expected_status=anything
    Should Be True    ${response.status_code} == 200 or ${response.status_code} == 404

Assert Error Payload
    [Documentation]    Validate a standard ADM error payload.
    [Arguments]    ${error}
    Dictionary Should Contain Key    ${error}    id
    Dictionary Should Contain Key    ${error}    description
    ${has_details}=    Run Keyword And Return Status    Dictionary Should Contain Key    ${error}    details
    IF    ${has_details}
        ${details_are_dict}=    Evaluate    isinstance($error["details"], dict)
        Should Be True    ${details_are_dict}
    END

Assert Unauthorized Response
    [Documentation]    Validate a 401 response accepting ADM Error or FastAPI detail payload.
    [Arguments]    ${response}
    Should Be Equal As Integers    ${response.status_code}    401
    ${payload}=    Set Variable    ${response.json()}
    ${has_id}=    Run Keyword And Return Status    Dictionary Should Contain Key    ${payload}    id
    IF    ${has_id}
        Should Be Equal As Strings    ${payload}[id]    401
    ELSE
        Dictionary Should Contain Key    ${payload}    detail
        Should Not Be Empty    ${payload}[detail]
    END

Assert Link Returns Object
    [Documentation]    Validate that a hyperlink returns an object with the expected id.
    [Arguments]    ${headers}    ${link}    ${expected_id}
    ${response}=    GET    ${link}    headers=${headers}    expected_status=200
    ${payload}=    Set Variable    ${response.json()}
    Dictionary Should Contain Key    ${payload}    id
    Should Be Equal    ${payload}[id]    ${expected_id}

Assert Self Link Returns Object
    [Documentation]    Validate that payload self link returns the same object.
    [Arguments]    ${headers}    ${payload}
    Dictionary Should Contain Key    ${payload}    id
    Dictionary Should Contain Key    ${payload}    self
    Should Not Be Empty    ${payload}[self]
    Assert Link Returns Object    ${headers}    ${payload}[self]    ${payload}[id]

Assert Reference Payload
    [Documentation]    Validate a reference object returned by the ADM API.
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
