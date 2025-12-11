import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_soap_structural_validation_passes_without_wsdl():
    from utils.database import endpoint_validation_collection
    from utils.validation_util import validation_util

    endpoint_id = 'soap-ep-struct-1'
    endpoint_validation_collection.delete_one({'endpoint_id': endpoint_id})
    endpoint_validation_collection.insert_one(
        {
            'endpoint_id': endpoint_id,
            'validation_enabled': True,
            'validation_schema': {
                'username': {'required': True, 'type': 'string', 'min': 3, 'max': 50},
                'email': {'required': True, 'type': 'string', 'format': 'email'},
            },
        }
    )

    envelope = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<soap:Envelope xmlns:soap='http://schemas.xmlsoap.org/soap/envelope/'>"
        '  <soap:Body>'
        '    <CreateUser>'
        '      <username>alice</username>'
        '      <email>alice@example.com</email>'
        '    </CreateUser>'
        '  </soap:Body>'
        '</soap:Envelope>'
    )

    await validation_util.validate_soap_request(endpoint_id, envelope)


@pytest.mark.asyncio
async def test_soap_structural_validation_fails_without_wsdl():
    from utils.database import endpoint_validation_collection
    from utils.validation_util import validation_util

    endpoint_id = 'soap-ep-struct-2'
    endpoint_validation_collection.delete_one({'endpoint_id': endpoint_id})
    endpoint_validation_collection.insert_one(
        {
            'endpoint_id': endpoint_id,
            'validation_enabled': True,
            'validation_schema': {'username': {'required': True, 'type': 'string', 'min': 3}},
        }
    )

    bad_envelope = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<soap:Envelope xmlns:soap='http://schemas.xmlsoap.org/soap/envelope/'>"
        '  <soap:Body>'
        '    <CreateUser>'
        '      <email>no-user@example.com</email>'
        '    </CreateUser>'
        '  </soap:Body>'
        '</soap:Envelope>'
    )

    with pytest.raises(HTTPException) as ex:
        await validation_util.validate_soap_request(endpoint_id, bad_envelope)
    assert ex.value.status_code == 400
