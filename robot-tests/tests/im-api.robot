*** Comments *** 

Tests for the ADIM API of a deployed ADIM instance.


*** Settings ***

Library    BuiltIn
Library    RequestsLibrary
Library    OperatingSystem
Library    Collections
Library    DateTime
Library    String
Resource    ../resources/resources.robot


*** Variables ***

${ALLOCATION_ID}    None
${ALLOCATION_KIND}    None
${ADIM_AUTH_HEADER}    None
${APPLICATION_ID}    None
${DEPLOYMENT_ID}    None

*** Keywords ***

Delete Test Allocation
    [Documentation]    Delete allocation created during tests.
    [Arguments]    ${allocation_id}
    ${headers}=    Generate ADIM Auth Header
    Delete Allocation If Present    ${headers}    ${allocation_id}

Delete Test Deployment
    [Documentation]    Delete deployment created during tests.
    [Arguments]    ${deployment_id}
    Return From Keyword If    '${deployment_id}' == 'None'
    ${headers}=    Generate ADIM Auth Header
    ${response}=    DELETE    ${ADIM_ENDPOINT}/deployment/${deployment_id}    headers=${headers}    expected_status=anything
    Should Be True    ${response.status_code} == 202 or ${response.status_code} == 404

Suite Cleanup
    [Documentation]    Clean up the suite
    Run Keyword If    '${DEPLOYMENT_ID}'!='None'    Delete Test Deployment    ${DEPLOYMENT_ID}
    Run Keyword If    '${ALLOCATION_ID}'!='None'    Delete Test Allocation    ${ALLOCATION_ID}

*** Settings ***
Suite Teardown    Suite Cleanup


*** Test Cases ***

Check Valid OIDC Token
    Check JWT Expiration    ${OIDC_ACCESS_TOKEN}
    ${headers}=    Generate ADIM Auth Header
    Set Suite Variable    ${ADIM_AUTH_HEADER}    ${headers}

ADIM API Request Without Auth Returns 401
    [Documentation]    Check that requests without Authorization header return 401.
    ${response}=    GET    ${ADIM_ENDPOINT}/allocations    expected_status=401
    Should Be Equal As Integers    ${response.status_code}    401

ADIM API Version
    [Documentation]    Check API version endpoint.
    ${response}=    GET  ${ADIM_ENDPOINT}/version  expected_status=200
    ${version}=     Decode Bytes To String  ${response.content}   UTF-8
    Should Match Regexp   ${version}   ^"\\d+\\.\\d+\\.\\d+"$

ADIM API List Allocations
    [Documentation]    Check allocations list endpoint.
    ${response}=    GET    ${ADIM_ENDPOINT}/allocations    expected_status=200    headers=${ADIM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Dictionary Should Contain Key    ${payload}    count
    Dictionary Should Contain Key    ${payload}    elements
    Dictionary Should Contain Key    ${payload}    from
    Dictionary Should Contain Key    ${payload}    limit

ADIM API List Allocations Pagination
    [Documentation]    Check allocations list pagination parameters from and limit.
    ${params}=    Create Dictionary    from=0    limit=1
    ${response}=    GET    ${ADIM_ENDPOINT}/allocations    params=${params}    expected_status=200    headers=${ADIM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Should Be Equal As Integers    ${payload}[from]    0
    Should Be Equal As Integers    ${payload}[limit]    1
    Dictionary Should Contain Key    ${payload}    count
    Dictionary Should Contain Key    ${payload}    elements
    ${page_size}=    Get Length    ${payload}[elements]
    Should Be True    ${page_size} <= 1

ADIM API List Allocations Invalid Limit Returns 400
    [Documentation]    Check allocations list rejects invalid limit values.
    ${params}=    Create Dictionary    limit=0
    ${response}=    GET    ${ADIM_ENDPOINT}/allocations    params=${params}    expected_status=400    headers=${ADIM_AUTH_HEADER}
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    400

ADIM API Get Nonexistent Allocation Returns 404
    [Documentation]    Check that GET request for nonexistent allocation returns 404.
    ${response}=    GET    ${ADIM_ENDPOINT}/allocation/__robot_nonexistent_allocation__    expected_status=404    headers=${ADIM_AUTH_HEADER}
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    404

ADIM API Create Invalid Allocation Returns 400
    [Documentation]    Check allocation creation rejects a payload missing required fields.
    ${invalid_payload}=    Create Dictionary
    ${response}=    POST    ${ADIM_ENDPOINT}/allocations    headers=${ADIM_AUTH_HEADER}    json=${invalid_payload}    expected_status=400
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    400

ADIM API Create Allocation
    [Documentation]    Create one configured allocation.
    ${allocation_id}=    Create Configured Allocation    ${ADIM_AUTH_HEADER}
    ${allocation_kind}=    Get Configured Allocation Kind
    Set Suite Variable    ${ALLOCATION_ID}    ${allocation_id}
    Set Suite Variable    ${ALLOCATION_KIND}    ${allocation_kind}
    Should Not Be Empty    ${ALLOCATION_ID}

ADIM API Get Allocation
    [Documentation]    Retrieve created allocation.
    ${response}=    GET    ${ADIM_ENDPOINT}/allocation/${ALLOCATION_ID}    expected_status=200    headers=${ADIM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Should Be Equal    ${payload}[id]    ${ALLOCATION_ID}
    Should Be Equal    ${payload}[kind]    ${ALLOCATION_KIND}
    Dictionary Should Contain Key    ${payload}    self
    Should Not Be Empty    ${payload}[self]

ADIM API Update Allocation
    [Documentation]    Update created allocation using the configured payload.
    ${update_payload}=    Get Configured Allocation Payload
    ${response}=    PUT    ${ADIM_ENDPOINT}/allocation/${ALLOCATION_ID}    headers=${ADIM_AUTH_HEADER}    json=${update_payload}    expected_status=200
    ${payload}=    Set Variable    ${response.json()}
    Should Be Equal    ${payload}[id]    ${ALLOCATION_ID}
    Should Be Equal    ${payload}[kind]    ${ALLOCATION_KIND}
    Dictionary Should Contain Key    ${payload}    self

ADIM API Update Nonexistent Allocation Returns 404
    [Documentation]    Check allocation update returns 404 for a nonexistent id.
    ${update_payload}=    Get Configured Allocation Payload
    ${response}=    PUT    ${ADIM_ENDPOINT}/allocation/__robot_nonexistent_allocation__    headers=${ADIM_AUTH_HEADER}    json=${update_payload}    expected_status=404
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    404

ADIM API List Applications
    [Documentation]    Check applications list endpoint and keep one id for follow-up get.
    ${response}=    GET    ${ADIM_ENDPOINT}/applications    expected_status=200    headers=${ADIM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Dictionary Should Contain Key    ${payload}    count
    Dictionary Should Contain Key    ${payload}    elements
    ${has_elements}=    Evaluate    len($payload["elements"]) > 0
    Run Keyword If    ${has_elements}    Set Suite Variable    ${APPLICATION_ID}    ${payload}[elements][0][id]
    Run Keyword If    not ${has_elements}    Set Suite Variable    ${APPLICATION_ID}    None

ADIM API List Applications Pagination
    [Documentation]    Check applications list pagination parameters from and limit.
    ${params}=    Create Dictionary    from=0    limit=1
    ${response}=    GET    ${ADIM_ENDPOINT}/applications    params=${params}    expected_status=200    headers=${ADIM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Should Be Equal As Integers    ${payload}[from]    0
    Should Be Equal As Integers    ${payload}[limit]    1
    Dictionary Should Contain Key    ${payload}    count
    Dictionary Should Contain Key    ${payload}    elements
    ${page_size}=    Get Length    ${payload}[elements]
    Should Be True    ${page_size} <= 1

ADIM API List Applications Invalid From Returns 400
    [Documentation]    Check applications list rejects invalid from values.
    ${params}=    Create Dictionary    from=-1
    ${response}=    GET    ${ADIM_ENDPOINT}/applications    params=${params}    expected_status=400    headers=${ADIM_AUTH_HEADER}
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    400

ADIM API Get Nonexistent Application Returns 404
    [Documentation]    Check that GET request for nonexistent application returns 404.
    ${response}=    GET    ${ADIM_ENDPOINT}/application/__robot_nonexistent_application__    expected_status=404    headers=${ADIM_AUTH_HEADER}
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    404

ADIM API Get Application
    [Documentation]    Get one application when list endpoint returns elements.
    Skip If    '${APPLICATION_ID}' == 'None'    No applications available in the configured backend.
    ${response}=    GET    ${ADIM_ENDPOINT}/application/${APPLICATION_ID}    expected_status=200    headers=${ADIM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Should Be Equal    ${payload}[id]    ${APPLICATION_ID}
    Dictionary Should Contain Key    ${payload}    type
    Dictionary Should Contain Key    ${payload}    blueprint
    Dictionary Should Contain Key    ${payload}    blueprintType
    Should Be True    $payload["type"] in ["vm", "container"]
    Should Be True    $payload["blueprintType"] in ["tosca", "ansible", "helm"]

ADIM API List Deployments
    [Documentation]    Check deployments list endpoint.
    ${response}=    GET    ${ADIM_ENDPOINT}/deployments    expected_status=200    headers=${ADIM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Dictionary Should Contain Key    ${payload}    count
    Dictionary Should Contain Key    ${payload}    elements

ADIM API List Deployments Pagination
    [Documentation]    Check deployments list pagination parameters from and limit.
    ${params}=    Create Dictionary    from=0    limit=1
    ${response}=    GET    ${ADIM_ENDPOINT}/deployments    params=${params}    expected_status=200    headers=${ADIM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Should Be Equal As Integers    ${payload}[from]    0
    Should Be Equal As Integers    ${payload}[limit]    1
    Dictionary Should Contain Key    ${payload}    count
    Dictionary Should Contain Key    ${payload}    elements
    ${page_size}=    Get Length    ${payload}[elements]
    Should Be True    ${page_size} <= 1

ADIM API List Deployments Invalid Limit Returns 400
    [Documentation]    Check deployments list rejects invalid limit values.
    ${params}=    Create Dictionary    limit=0
    ${response}=    GET    ${ADIM_ENDPOINT}/deployments    params=${params}    expected_status=400    headers=${ADIM_AUTH_HEADER}
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    400

ADIM API Get Nonexistent Deployment Returns 404
    [Documentation]    Check that GET request for nonexistent deployment returns 404.
    ${response}=    GET    ${ADIM_ENDPOINT}/deployment/__robot_nonexistent_deployment__    expected_status=404    headers=${ADIM_AUTH_HEADER}
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    404

ADIM API Delete Nonexistent Deployment Returns 404
    [Documentation]    Check that DELETE request for nonexistent deployment returns 404.
    ${response}=    DELETE    ${ADIM_ENDPOINT}/deployment/__robot_nonexistent_deployment__    expected_status=404    headers=${ADIM_AUTH_HEADER}
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    404

ADIM API Deploy Invalid Payload Returns 400
    [Documentation]    Deploy with a payload missing required fields and expect 400.
    ${payload}=    Create Dictionary
    ${response}=    POST    ${ADIM_ENDPOINT}/deployments    headers=${ADIM_AUTH_HEADER}    json=${payload}    expected_status=400
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    400

ADIM API Deploy Invalid Application Returns Error
    [Documentation]    Deploy with a non-existing application id and expect 400.
    Skip If    '${APPLICATION_ID}' == 'None'    No applications available in the configured backend.
    ${allocation}=    Create Dictionary
    ...    kind=AllocationId
    ...    id=__robot_non_existing_allocation__
    ...    infoLink=${ADIM_ENDPOINT}/allocation/__robot_non_existing_allocation__
    ${application}=    Create Dictionary
    ...    kind=ApplicationId
    ...    id=${APPLICATION_ID}
    ...    version=latest
    ...    infoLink=${ADIM_ENDPOINT}/application/${APPLICATION_ID}
    ${payload}=    Create Dictionary
    ...    allocation=${allocation}
    ...    application=${application}
    ${response}=    POST    ${ADIM_ENDPOINT}/deployments    headers=${ADIM_AUTH_HEADER}    json=${payload}    expected_status=400
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    400

ADIM API Create Deployment
    [Documentation]    Create deployment using current allocation and one available application.
    Skip If    '${APPLICATION_ID}' == 'None'    No applications available in the configured backend.
    ${allocation}=    Create Dictionary
    ...    kind=AllocationId
    ...    id=${ALLOCATION_ID}
    ...    infoLink=${ADIM_ENDPOINT}/allocation/${ALLOCATION_ID}
    ${application}=    Create Dictionary
    ...    kind=ApplicationId
    ...    id=${APPLICATION_ID}
    ...    version=latest
    ...    infoLink=${ADIM_ENDPOINT}/application/${APPLICATION_ID}
    ${payload}=    Create Dictionary
    ...    allocation=${allocation}
    ...    application=${application}
    ${response}=    POST    ${ADIM_ENDPOINT}/deployments    headers=${ADIM_AUTH_HEADER}    json=${payload}    expected_status=202
    ${dep}=    Set Variable    ${response.json()}
    Assert Reference Payload    ${dep}
    Set Suite Variable    ${DEPLOYMENT_ID}    ${dep}[id]

ADIM API Get Deployment
    [Documentation]    Retrieve the created deployment.
    Skip If    '${DEPLOYMENT_ID}' == 'None'    Deployment was not created in previous test.
    ${response}=    GET    ${ADIM_ENDPOINT}/deployment/${DEPLOYMENT_ID}    expected_status=200    headers=${ADIM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    ${application_ref}=    Set Variable    ${payload}[application]
    ${allocation_ref}=    Set Variable    ${payload}[allocation]
    Should Be Equal    ${payload}[id]    ${DEPLOYMENT_ID}
    Assert Reference Payload    ${application_ref}
    Assert Reference Payload    ${allocation_ref}
    Should Be Equal    ${application_ref}[id]    ${APPLICATION_ID}
    Should Be Equal    ${allocation_ref}[id]    ${ALLOCATION_ID}
    Dictionary Should Contain Key    ${payload}    status
    Dictionary Should Contain Key    ${payload}    self
    Should Be True    $payload["status"] in ["unknown", "pending", "running", "stopped", "off", "failed", "configured", "unconfigured", "deleting", "deleted"]
    ${has_outputs}=    Run Keyword And Return Status    Dictionary Should Contain Key    ${payload}    outputs
    IF    ${has_outputs}
        ${outputs_are_list}=    Evaluate    isinstance($payload["outputs"], list)
        Should Be True    ${outputs_are_list}
    END
    ${has_details}=    Run Keyword And Return Status    Dictionary Should Contain Key    ${payload}    details
    IF    ${has_details}
        ${details_are_string}=    Evaluate    isinstance($payload["details"], str)
        Should Be True    ${details_are_string}
    END

ADIM API Update In Use Allocation Returns 409
    [Documentation]    Check allocation cannot be updated while used by a deployment.
    Skip If    '${DEPLOYMENT_ID}' == 'None'    Deployment was not created in previous test.
    ${update_payload}=    Get Configured Allocation Payload
    ${response}=    PUT    ${ADIM_ENDPOINT}/allocation/${ALLOCATION_ID}    headers=${ADIM_AUTH_HEADER}    json=${update_payload}    expected_status=409
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    409

ADIM API Delete In Use Allocation Returns 409
    [Documentation]    Check allocation cannot be deleted while used by a deployment.
    Skip If    '${DEPLOYMENT_ID}' == 'None'    Deployment was not created in previous test.
    ${response}=    DELETE    ${ADIM_ENDPOINT}/allocation/${ALLOCATION_ID}    expected_status=409    headers=${ADIM_AUTH_HEADER}
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    409

ADIM API Delete Deployment
    [Documentation]    Delete deployment so allocation can be cleaned up.
    Skip If    '${DEPLOYMENT_ID}' == 'None'    Deployment was not created in previous test.
    ${response}=    DELETE    ${ADIM_ENDPOINT}/deployment/${DEPLOYMENT_ID}    expected_status=202    headers=${ADIM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Should Be Equal    ${payload}[message]    Deleting
    Set Suite Variable    ${DEPLOYMENT_ID}    None

ADIM API Delete Allocation
    [Documentation]    Delete created allocation and verify cleanup.
    ${response}=    DELETE    ${ADIM_ENDPOINT}/allocation/${ALLOCATION_ID}    expected_status=200    headers=${ADIM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Should Be Equal    ${payload}[message]    Deleted
    Set Suite Variable    ${ALLOCATION_ID}    None

ADIM API Delete Nonexistent Allocation Returns 404
    [Documentation]    Check allocation deletion returns 404 for a nonexistent id.
    ${response}=    DELETE    ${ADIM_ENDPOINT}/allocation/__robot_nonexistent_allocation__    expected_status=404    headers=${ADIM_AUTH_HEADER}
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    404