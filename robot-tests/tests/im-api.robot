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

ADIM API Create Allocation
    [Documentation]    Create one Dummy allocation.
    ${allocation_id}=    Create Dummy Allocation    ${ADIM_AUTH_HEADER}
    Set Suite Variable    ${ALLOCATION_ID}    ${allocation_id}
    Should Not Be Empty    ${ALLOCATION_ID}

ADIM API Get Allocation
    [Documentation]    Retrieve created allocation.
    ${response}=    GET    ${ADIM_ENDPOINT}/allocation/${ALLOCATION_ID}    expected_status=200    headers=${ADIM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Should Be Equal    ${payload}[id]    ${ALLOCATION_ID}
    Should Be Equal    ${payload}[kind]    DummyEnvironment

ADIM API List Applications
    [Documentation]    Check applications list endpoint and keep one id for follow-up get.
    ${response}=    GET    ${ADIM_ENDPOINT}/applications    expected_status=200    headers=${ADIM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Dictionary Should Contain Key    ${payload}    count
    Dictionary Should Contain Key    ${payload}    elements
    ${has_elements}=    Evaluate    len($payload["elements"]) > 0
    Run Keyword If    ${has_elements}    Set Suite Variable    ${APPLICATION_ID}    ${payload}[elements][0][id]
    Run Keyword If    not ${has_elements}    Set Suite Variable    ${APPLICATION_ID}    None

ADIM API Get Application
    [Documentation]    Get one application when list endpoint returns elements.
    Skip If    '${APPLICATION_ID}' == 'None'    No applications available in the configured backend.
    ${response}=    GET    ${ADIM_ENDPOINT}/application/${APPLICATION_ID}    expected_status=200    headers=${ADIM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Should Be Equal    ${payload}[id]    ${APPLICATION_ID}
    Dictionary Should Contain Key    ${payload}    blueprint
    Dictionary Should Contain Key    ${payload}    blueprintType

ADIM API List Deployments
    [Documentation]    Check deployments list endpoint.
    ${response}=    GET    ${ADIM_ENDPOINT}/deployments    expected_status=200    headers=${ADIM_AUTH_HEADER}
    ${payload}=    Set Variable    ${response.json()}
    Dictionary Should Contain Key    ${payload}    count
    Dictionary Should Contain Key    ${payload}    elements

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
    Dictionary Should Contain Key    ${error}    id

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
    Dictionary Should Contain Key    ${dep}    id
    Set Suite Variable    ${DEPLOYMENT_ID}    ${dep}[id]

ADIM API Delete In Use Allocation Returns 409
    [Documentation]    Check allocation cannot be deleted while used by a deployment.
    Skip If    '${DEPLOYMENT_ID}' == 'None'    Deployment was not created in previous test.
    ${response}=    DELETE    ${ADIM_ENDPOINT}/allocation/${ALLOCATION_ID}    expected_status=409    headers=${ADIM_AUTH_HEADER}
    ${error}=    Set Variable    ${response.json()}
    Should Be Equal    ${error}[id]    409

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