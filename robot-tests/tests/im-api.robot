*** Comments *** 

Tests for the ADM API of a deployed ADM instance.


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
${ADM_AUTH_HEADER}    None
${APPLICATION_ID}    None
${DEPLOYMENT_ID}    None

*** Keywords ***

Delete Test Allocation
    [Documentation]    Delete allocation created during tests.
    [Arguments]    ${allocation_id}
    ${headers}=    Generate ADM Auth Header
    Delete Allocation If Present    ${headers}    ${allocation_id}

Delete Test Deployment
    [Documentation]    Delete deployment created during tests.
    [Arguments]    ${deployment_id}
    Return From Keyword If    '${deployment_id}' == 'None'
    ${headers}=    Generate ADM Auth Header
    ${response}=    DELETE    ${ADM_ENDPOINT}/deployment/${deployment_id}    headers=${headers}    expected_status=anything
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
    ${headers}=    Generate ADM Auth Header
    Set Suite Variable    ${ADM_AUTH_HEADER}    ${headers}

ADM API Request Without Auth Returns 401
    [Documentation]    Check that requests without Authorization header return 401.
    ${response}=    GET    ${ADM_ENDPOINT}/allocations    expected_status=401
    Should Be Equal As Integers    ${response.status_code}    401

ADM API Get Allocation Without Auth Returns 401
    [Documentation]    Check that GET allocation without Authorization header returns 401.
    ${response}=    GET    ${ADM_ENDPOINT}/allocation/__robot_nonexistent_allocation__    expected_status=401
    Assert Unauthorized Response    ${response}

ADM API Create Allocation Without Auth Returns 401
    [Documentation]    Check that POST allocations without Authorization header returns 401.
    ${payload}=    Get Configured Allocation Payload
    ${response}=    POST    ${ADM_ENDPOINT}/allocations    json=${payload}    expected_status=401
    Assert Unauthorized Response    ${response}

ADM API Update Allocation Without Auth Returns 401
    [Documentation]    Check that PUT allocation without Authorization header returns 401.
    ${payload}=    Get Configured Allocation Payload
    ${response}=    PUT    ${ADM_ENDPOINT}/allocation/__robot_nonexistent_allocation__    json=${payload}    expected_status=401
    Assert Unauthorized Response    ${response}

ADM API Delete Allocation Without Auth Returns 401
    [Documentation]    Check that DELETE allocation without Authorization header returns 401.
    ${response}=    DELETE    ${ADM_ENDPOINT}/allocation/__robot_nonexistent_allocation__    expected_status=401
    Assert Unauthorized Response    ${response}

ADM API List Applications Without Auth Returns 401
    [Documentation]    Check that GET applications without Authorization header returns 401.
    ${response}=    GET    ${ADM_ENDPOINT}/applications    expected_status=401
    Assert Unauthorized Response    ${response}

ADM API Get Application Without Auth Returns 401
    [Documentation]    Check that GET application without Authorization header returns 401.
    ${response}=    GET    ${ADM_ENDPOINT}/application/__robot_nonexistent_application__    expected_status=401
    Assert Unauthorized Response    ${response}

ADM API List Deployments Without Auth Returns 401
    [Documentation]    Check that GET deployments without Authorization header returns 401.
    ${response}=    GET    ${ADM_ENDPOINT}/deployments    expected_status=401
    Assert Unauthorized Response    ${response}

ADM API Create Deployment Without Auth Returns 401
    [Documentation]    Check that POST deployments without Authorization header returns 401.
    ${allocation}=    Create Dictionary
    ...    kind=AllocationId
    ...    id=__robot_non_existing_allocation__
    ...    infoLink=${ADM_ENDPOINT}/allocation/__robot_non_existing_allocation__
    ${application}=    Create Dictionary
    ...    kind=ApplicationId
    ...    id=__robot_non_existing_application__
    ...    version=latest
    ...    infoLink=${ADM_ENDPOINT}/application/__robot_non_existing_application__
    ${payload}=    Create Dictionary
    ...    allocation=${allocation}
    ...    application=${application}
    ${response}=    POST    ${ADM_ENDPOINT}/deployments    json=${payload}    expected_status=401
    Assert Unauthorized Response    ${response}

ADM API Get Deployment Without Auth Returns 401
    [Documentation]    Check that GET deployment without Authorization header returns 401.
    ${response}=    GET    ${ADM_ENDPOINT}/deployment/__robot_nonexistent_deployment__    expected_status=401
    Assert Unauthorized Response    ${response}

ADM API Delete Deployment Without Auth Returns 401
    [Documentation]    Check that DELETE deployment without Authorization header returns 401.
    ${response}=    DELETE    ${ADM_ENDPOINT}/deployment/__robot_nonexistent_deployment__    expected_status=401
    Assert Unauthorized Response    ${response}

ADM API Version
    [Documentation]    Check API version endpoint.
    ${response}=    GET  ${ADM_ENDPOINT}/version  expected_status=200
    ${version}=     Decode Bytes To String  ${response.content}   UTF-8
    Should Match Regexp   ${version}   ^"\\d+\\.\\d+\\.\\d+"$

ADM API List Allocations
    [Documentation]    Check allocations list endpoint.
    ${response}=    GET    ${ADM_ENDPOINT}/allocations    expected_status=200    headers=${ADM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Dictionary Should Contain Key    ${payload}    count
    Dictionary Should Contain Key    ${payload}    elements
    Dictionary Should Contain Key    ${payload}    from
    Dictionary Should Contain Key    ${payload}    limit

ADM API List Allocations Pagination
    [Documentation]    Check allocations list pagination parameters from and limit.
    ${params}=    Create Dictionary    from=0    limit=1
    ${response}=    GET    ${ADM_ENDPOINT}/allocations    params=${params}    expected_status=200    headers=${ADM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Should Be Equal As Integers    ${payload}[from]    0
    Should Be Equal As Integers    ${payload}[limit]    1
    Dictionary Should Contain Key    ${payload}    count
    Dictionary Should Contain Key    ${payload}    elements
    ${page_size}=    Get Length    ${payload}[elements]
    Should Be True    ${page_size} <= 1

ADM API List Allocations All Nodes
    [Documentation]    Check allocations list supports allNodes query parameter.
    ${params}=    Create Dictionary    allNodes=true    from=0    limit=10
    ${response}=    GET    ${ADM_ENDPOINT}/allocations    params=${params}    expected_status=200    headers=${ADM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Dictionary Should Contain Key    ${payload}    count
    Dictionary Should Contain Key    ${payload}    elements
    Dictionary Should Contain Key    ${payload}    from
    Dictionary Should Contain Key    ${payload}    limit

ADM API List Allocations Invalid Limit Returns 400
    [Documentation]    Check allocations list rejects invalid limit values.
    ${params}=    Create Dictionary    limit=0
    ${response}=    GET    ${ADM_ENDPOINT}/allocations    params=${params}    expected_status=400    headers=${ADM_AUTH_HEADER}
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    400

ADM API Get Nonexistent Allocation Returns 404
    [Documentation]    Check that GET request for nonexistent allocation returns 404.
    ${response}=    GET    ${ADM_ENDPOINT}/allocation/__robot_nonexistent_allocation__    expected_status=404    headers=${ADM_AUTH_HEADER}
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    404

ADM API Create Invalid Allocation Returns 400
    [Documentation]    Check allocation creation rejects a payload missing required fields.
    ${invalid_payload}=    Create Dictionary
    ${response}=    POST    ${ADM_ENDPOINT}/allocations    headers=${ADM_AUTH_HEADER}    json=${invalid_payload}    expected_status=400
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    400

ADM API Create Allocation
    [Documentation]    Create one configured allocation.
    ${allocation_id}=    Create Configured Allocation    ${ADM_AUTH_HEADER}
    ${allocation_kind}=    Get Configured Allocation Kind
    Set Suite Variable    ${ALLOCATION_ID}    ${allocation_id}
    Set Suite Variable    ${ALLOCATION_KIND}    ${allocation_kind}
    Should Not Be Empty    ${ALLOCATION_ID}

ADM API Get Allocation
    [Documentation]    Retrieve created allocation.
    ${response}=    GET    ${ADM_ENDPOINT}/allocation/${ALLOCATION_ID}    expected_status=200    headers=${ADM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Should Be Equal    ${payload}[id]    ${ALLOCATION_ID}
    Should Be Equal    ${payload}[kind]    ${ALLOCATION_KIND}
    Dictionary Should Contain Key    ${payload}    self
    Should Not Be Empty    ${payload}[self]
    Assert Self Link Returns Object    ${ADM_AUTH_HEADER}    ${payload}

ADM API Update Allocation
    [Documentation]    Update created allocation using the configured payload.
    ${update_payload}=    Get Configured Allocation Payload
    ${response}=    PUT    ${ADM_ENDPOINT}/allocation/${ALLOCATION_ID}    headers=${ADM_AUTH_HEADER}    json=${update_payload}    expected_status=200
    ${payload}=    Set Variable    ${response.json()}
    Should Be Equal    ${payload}[id]    ${ALLOCATION_ID}
    Should Be Equal    ${payload}[kind]    ${ALLOCATION_KIND}
    Dictionary Should Contain Key    ${payload}    self
    Assert Self Link Returns Object    ${ADM_AUTH_HEADER}    ${payload}

ADM API Update Nonexistent Allocation Returns 404
    [Documentation]    Check allocation update returns 404 for a nonexistent id.
    ${update_payload}=    Get Configured Allocation Payload
    ${response}=    PUT    ${ADM_ENDPOINT}/allocation/__robot_nonexistent_allocation__    headers=${ADM_AUTH_HEADER}    json=${update_payload}    expected_status=404
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    404

ADM API List Applications
    [Documentation]    Check applications list endpoint and keep one id for follow-up get.
    ${response}=    GET    ${ADM_ENDPOINT}/applications    expected_status=200    headers=${ADM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Dictionary Should Contain Key    ${payload}    count
    Dictionary Should Contain Key    ${payload}    elements
    ${has_elements}=    Evaluate    len($payload["elements"]) > 0
    Run Keyword If    ${has_elements}    Set Suite Variable    ${APPLICATION_ID}    ${payload}[elements][0][id]
    Run Keyword If    not ${has_elements}    Set Suite Variable    ${APPLICATION_ID}    None

ADM API List Applications IncludePublished
    [Documentation]    Check applications list supports includePublished query parameter.
    ${params}=    Create Dictionary    includePublished=true    includePersonal=false    from=0    limit=10
    ${response}=    GET    ${ADM_ENDPOINT}/applications    params=${params}    expected_status=200    headers=${ADM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Dictionary Should Contain Key    ${payload}    count
    Dictionary Should Contain Key    ${payload}    elements
    Dictionary Should Contain Key    ${payload}    from
    Dictionary Should Contain Key    ${payload}    limit

ADM API List Applications IncludePersonal
    [Documentation]    Check applications list supports includePersonal query parameter.
    ${params}=    Create Dictionary    includePersonal=true    includePublished=true    from=0    limit=10
    ${response}=    GET    ${ADM_ENDPOINT}/applications    params=${params}    expected_status=200    headers=${ADM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Dictionary Should Contain Key    ${payload}    count
    Dictionary Should Contain Key    ${payload}    elements
    Dictionary Should Contain Key    ${payload}    from
    Dictionary Should Contain Key    ${payload}    limit

ADM API List Applications OnlyFavorites
    [Documentation]    Check applications list supports onlyFavorites query parameter.
    ${params}=    Create Dictionary    onlyFavorites=true    from=0    limit=10
    ${response}=    GET    ${ADM_ENDPOINT}/applications    params=${params}    expected_status=200    headers=${ADM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Dictionary Should Contain Key    ${payload}    count
    Dictionary Should Contain Key    ${payload}    elements
    Dictionary Should Contain Key    ${payload}    from
    Dictionary Should Contain Key    ${payload}    limit

ADM API List Applications All Nodes
    [Documentation]    Check applications list supports allNodes query parameter.
    ${params}=    Create Dictionary    allNodes=true    from=0    limit=10
    ${response}=    GET    ${ADM_ENDPOINT}/applications    params=${params}    expected_status=200    headers=${ADM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Dictionary Should Contain Key    ${payload}    count
    Dictionary Should Contain Key    ${payload}    elements
    Dictionary Should Contain Key    ${payload}    from
    Dictionary Should Contain Key    ${payload}    limit

ADM API List Applications Pagination
    [Documentation]    Check applications list pagination parameters from and limit.
    ${params}=    Create Dictionary    from=0    limit=1
    ${response}=    GET    ${ADM_ENDPOINT}/applications    params=${params}    expected_status=200    headers=${ADM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Should Be Equal As Integers    ${payload}[from]    0
    Should Be Equal As Integers    ${payload}[limit]    1
    Dictionary Should Contain Key    ${payload}    count
    Dictionary Should Contain Key    ${payload}    elements
    ${page_size}=    Get Length    ${payload}[elements]
    Should Be True    ${page_size} <= 1

ADM API List Applications Invalid From Returns 400
    [Documentation]    Check applications list rejects invalid from values.
    ${params}=    Create Dictionary    from=-1
    ${response}=    GET    ${ADM_ENDPOINT}/applications    params=${params}    expected_status=400    headers=${ADM_AUTH_HEADER}
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    400

ADM API Get Nonexistent Application Returns 404
    [Documentation]    Check that GET request for nonexistent application returns 404.
    ${response}=    GET    ${ADM_ENDPOINT}/application/__robot_nonexistent_application__    expected_status=404    headers=${ADM_AUTH_HEADER}
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    404

ADM API Get Application
    [Documentation]    Get one application when list endpoint returns elements.
    Skip If    '${APPLICATION_ID}' == 'None'    No applications available in the configured backend.
    ${response}=    GET    ${ADM_ENDPOINT}/application/${APPLICATION_ID}    expected_status=200    headers=${ADM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Should Be Equal    ${payload}[id]    ${APPLICATION_ID}
    Dictionary Should Contain Key    ${payload}    type
    Dictionary Should Contain Key    ${payload}    blueprint
    Dictionary Should Contain Key    ${payload}    blueprintType
    Should Be True    $payload["type"] in ["vm", "container"]
    Should Be True    $payload["blueprintType"] in ["tosca", "ansible", "helm"]

ADM API Get Application Version Query Param
    [Documentation]    Check get application supports version query parameter.
    Skip If    '${APPLICATION_ID}' == 'None'    No applications available in the configured backend.
    ${params}=    Create Dictionary    version=latest
    ${response}=    GET    ${ADM_ENDPOINT}/application/${APPLICATION_ID}    params=${params}    expected_status=200    headers=${ADM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Should Be Equal    ${payload}[id]    ${APPLICATION_ID}
    Dictionary Should Contain Key    ${payload}    blueprint
    Dictionary Should Contain Key    ${payload}    blueprintType

ADM API List Deployments
    [Documentation]    Check deployments list endpoint.
    ${response}=    GET    ${ADM_ENDPOINT}/deployments    expected_status=200    headers=${ADM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Dictionary Should Contain Key    ${payload}    count
    Dictionary Should Contain Key    ${payload}    elements

ADM API List Deployments Pagination
    [Documentation]    Check deployments list pagination parameters from and limit.
    ${params}=    Create Dictionary    from=0    limit=1
    ${response}=    GET    ${ADM_ENDPOINT}/deployments    params=${params}    expected_status=200    headers=${ADM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Should Be Equal As Integers    ${payload}[from]    0
    Should Be Equal As Integers    ${payload}[limit]    1
    Dictionary Should Contain Key    ${payload}    count
    Dictionary Should Contain Key    ${payload}    elements
    ${page_size}=    Get Length    ${payload}[elements]
    Should Be True    ${page_size} <= 1

ADM API List Deployments All Nodes
    [Documentation]    Check deployments list supports allNodes query parameter.
    ${params}=    Create Dictionary    allNodes=true    from=0    limit=10
    ${response}=    GET    ${ADM_ENDPOINT}/deployments    params=${params}    expected_status=200    headers=${ADM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Dictionary Should Contain Key    ${payload}    count
    Dictionary Should Contain Key    ${payload}    elements
    Dictionary Should Contain Key    ${payload}    from
    Dictionary Should Contain Key    ${payload}    limit

ADM API List Deployments Invalid Limit Returns 400
    [Documentation]    Check deployments list rejects invalid limit values.
    ${params}=    Create Dictionary    limit=0
    ${response}=    GET    ${ADM_ENDPOINT}/deployments    params=${params}    expected_status=400    headers=${ADM_AUTH_HEADER}
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    400

ADM API Get Nonexistent Deployment Returns 404
    [Documentation]    Check that GET request for nonexistent deployment returns 404.
    ${response}=    GET    ${ADM_ENDPOINT}/deployment/__robot_nonexistent_deployment__    expected_status=404    headers=${ADM_AUTH_HEADER}
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    404

ADM API Delete Nonexistent Deployment Returns 404
    [Documentation]    Check that DELETE request for nonexistent deployment returns 404.
    ${response}=    DELETE    ${ADM_ENDPOINT}/deployment/__robot_nonexistent_deployment__    expected_status=404    headers=${ADM_AUTH_HEADER}
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    404

ADM API Deploy Invalid Payload Returns 400
    [Documentation]    Deploy with a payload missing required fields and expect 400.
    ${payload}=    Create Dictionary
    ${response}=    POST    ${ADM_ENDPOINT}/deployments    headers=${ADM_AUTH_HEADER}    json=${payload}    expected_status=400
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    400

ADM API Deploy Invalid Application Returns Error
    [Documentation]    Deploy with a non-existing application id and expect 400.
    Skip If    '${APPLICATION_ID}' == 'None'    No applications available in the configured backend.
    ${allocation}=    Create Dictionary
    ...    kind=AllocationId
    ...    id=__robot_non_existing_allocation__
    ...    infoLink=${ADM_ENDPOINT}/allocation/__robot_non_existing_allocation__
    ${application}=    Create Dictionary
    ...    kind=ApplicationId
    ...    id=${APPLICATION_ID}
    ...    version=latest
    ...    infoLink=${ADM_ENDPOINT}/application/${APPLICATION_ID}
    ${payload}=    Create Dictionary
    ...    allocation=${allocation}
    ...    application=${application}
    ${response}=    POST    ${ADM_ENDPOINT}/deployments    headers=${ADM_AUTH_HEADER}    json=${payload}    expected_status=400
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    400

ADM API Create Deployment
    [Documentation]    Create deployment using current allocation and one available application.
    Skip If    '${APPLICATION_ID}' == 'None'    No applications available in the configured backend.
    ${application_response}=    GET    ${ADM_ENDPOINT}/application/${APPLICATION_ID}    expected_status=200    headers=${ADM_AUTH_HEADER}
    ${application_payload}=    Set Variable    ${application_response.json()}
    Dictionary Should Contain Key    ${application_payload}    blueprint
    ${input_name}    ${input_value}=    Get One TOSCA Input For Deployment    ${application_payload}[blueprint]
    Skip If    '${input_name}' == 'None'    Application blueprint does not expose topology_template.inputs.
    ${deployment_input}=    Create Dictionary    name=${input_name}    value=${input_value}
    ${deployment_inputs}=    Create List    ${deployment_input}
    ${allocation}=    Create Dictionary
    ...    kind=AllocationId
    ...    id=${ALLOCATION_ID}
    ...    infoLink=${ADM_ENDPOINT}/allocation/${ALLOCATION_ID}
    ${application}=    Create Dictionary
    ...    kind=ApplicationId
    ...    id=${APPLICATION_ID}
    ...    version=latest
    ...    infoLink=${ADM_ENDPOINT}/application/${APPLICATION_ID}
    ${payload}=    Create Dictionary
    ...    allocation=${allocation}
    ...    application=${application}
    ...    inputs=${deployment_inputs}
    ${response}=    POST    ${ADM_ENDPOINT}/deployments    headers=${ADM_AUTH_HEADER}    json=${payload}    expected_status=202
    ${dep}=    Set Variable    ${response.json()}
    Assert Reference Payload    ${dep}
    Assert Link Returns Object    ${ADM_AUTH_HEADER}    ${dep}[infoLink]    ${dep}[id]
    Set Suite Variable    ${DEPLOYMENT_ID}    ${dep}[id]

ADM API Get Deployment
    [Documentation]    Retrieve the created deployment.
    Skip If    '${DEPLOYMENT_ID}' == 'None'    Deployment was not created in previous test.
    ${response}=    GET    ${ADM_ENDPOINT}/deployment/${DEPLOYMENT_ID}    expected_status=200    headers=${ADM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    ${application_ref}=    Set Variable    ${payload}[application]
    ${allocation_ref}=    Set Variable    ${payload}[allocation]
    Should Be Equal    ${payload}[id]    ${DEPLOYMENT_ID}
    Assert Reference Payload    ${application_ref}
    Assert Reference Payload    ${allocation_ref}
    Assert Link Returns Object    ${ADM_AUTH_HEADER}    ${application_ref}[infoLink]    ${application_ref}[id]
    Assert Link Returns Object    ${ADM_AUTH_HEADER}    ${allocation_ref}[infoLink]    ${allocation_ref}[id]
    Should Be Equal    ${application_ref}[id]    ${APPLICATION_ID}
    Should Be Equal    ${allocation_ref}[id]    ${ALLOCATION_ID}
    Dictionary Should Contain Key    ${payload}    status
    Dictionary Should Contain Key    ${payload}    self
    Assert Self Link Returns Object    ${ADM_AUTH_HEADER}    ${payload}
    Should Be True    $payload["status"] in ["unknown", "pending", "running", "stopped", "off", "failed", "configured", "unconfigured", "deleting", "deleted"]
    Dictionary Should Contain Key    ${payload}    outputs
    ${outputs_are_list}=    Evaluate    isinstance($payload["outputs"], list)
    Should Be True    ${outputs_are_list}
    ${outputs_count}=    Get Length    ${payload}[outputs]
    Should Be True    ${outputs_count} > 0    Deployment did not expose outputs.
    ${first_output}=    Get From List    ${payload}[outputs]    0
    Dictionary Should Contain Key    ${first_output}    name
    Dictionary Should Contain Key    ${first_output}    value
    Should Not Be Empty    ${first_output}[name]
    ${has_details}=    Run Keyword And Return Status    Dictionary Should Contain Key    ${payload}    details
    IF    ${has_details}
        ${details_are_string}=    Evaluate    isinstance($payload["details"], str)
        Should Be True    ${details_are_string}
    END

ADM API Update In Use Allocation Returns 409
    [Documentation]    Check allocation cannot be updated while used by a deployment.
    Skip If    '${DEPLOYMENT_ID}' == 'None'    Deployment was not created in previous test.
    ${update_payload}=    Get Configured Allocation Payload
    ${response}=    PUT    ${ADM_ENDPOINT}/allocation/${ALLOCATION_ID}    headers=${ADM_AUTH_HEADER}    json=${update_payload}    expected_status=409
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    409

ADM API Delete In Use Allocation Returns 409
    [Documentation]    Check allocation cannot be deleted while used by a deployment.
    Skip If    '${DEPLOYMENT_ID}' == 'None'    Deployment was not created in previous test.
    ${response}=    DELETE    ${ADM_ENDPOINT}/allocation/${ALLOCATION_ID}    expected_status=409    headers=${ADM_AUTH_HEADER}
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    409

ADM API Delete Deployment
    [Documentation]    Delete deployment so allocation can be cleaned up.
    Skip If    '${DEPLOYMENT_ID}' == 'None'    Deployment was not created in previous test.
    ${response}=    DELETE    ${ADM_ENDPOINT}/deployment/${DEPLOYMENT_ID}    expected_status=202    headers=${ADM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Should Be Equal    ${payload}[message]    Deleting
    Set Suite Variable    ${DEPLOYMENT_ID}    None

ADM API Delete Allocation
    [Documentation]    Delete created allocation and verify cleanup.
    ${response}=    DELETE    ${ADM_ENDPOINT}/allocation/${ALLOCATION_ID}    expected_status=200    headers=${ADM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Should Be Equal    ${payload}[message]    Deleted
    Set Suite Variable    ${ALLOCATION_ID}    None

ADM API Delete Nonexistent Allocation Returns 404
    [Documentation]    Check allocation deletion returns 404 for a nonexistent id.
    ${response}=    DELETE    ${ADM_ENDPOINT}/allocation/__robot_nonexistent_allocation__    expected_status=404    headers=${ADM_AUTH_HEADER}
    ${error}=    Set Variable    ${response.json()}
    Assert Error Payload    ${error}
    Should Be Equal As Strings    ${error}[id]    404