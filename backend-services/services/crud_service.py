"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

import logging
import uuid
from fastapi import Request
from models.response_model import ResponseModel
from utils.async_db import db_delete_one, db_find_list, db_find_one, db_insert_one, db_update_one
from utils.database_async import db as async_db
from ariadne import make_executable_schema, graphql, ObjectType, QueryType, MutationType
import json

logger = logging.getLogger('doorman.gateway')

class CrudService:
    @staticmethod
    def _resource_from_endpoint_uri(endpoint_uri: str | None):
        parts = [p for p in str(endpoint_uri or '').split('/') if p]
        return parts[0] if parts else ''

    @staticmethod
    def _resolve_binding(api: dict, endpoint_uri: str | None):
        resource = CrudService._resource_from_endpoint_uri(endpoint_uri)
        bindings = api.get('api_crud_bindings')
        if isinstance(bindings, list) and resource:
            for binding in bindings:
                if not isinstance(binding, dict):
                    continue
                if str(binding.get('resource_name') or '').strip() == resource:
                    return binding
        return None

    @staticmethod
    def _get_collection(api: dict, endpoint_uri: str | None = None):
        binding = CrudService._resolve_binding(api, endpoint_uri)
        collection_name = ''
        if isinstance(binding, dict):
            collection_name = str(binding.get('collection_name') or '').strip()
        if not collection_name:
            collection_name = api.get('api_crud_collection')
        if not collection_name:
            # Fallback to a default name if not specified
            api_id = api.get('api_id', 'default')
            collection_name = f'crud_data_{api_id.replace("-", "_")}'
        
        # Access collection dynamically. 
        # For Motor (MongoDB), it's db[name]. 
        # For InMemoryDB, we might need to ensure it exists.
        if hasattr(async_db, 'get_collection'):
            coll = async_db.get_collection(collection_name)
            return coll
        
        # Fallback for InMemoryDB/Motor
        try:
            return getattr(async_db, collection_name)
        except AttributeError:
            if hasattr(async_db, 'create_collection'):
                return async_db.create_collection(collection_name)
            # Motor database access
            return async_db[collection_name]

    @staticmethod
    def _get_schema(api: dict, endpoint_uri: str | None = None):
        binding = CrudService._resolve_binding(api, endpoint_uri)
        if isinstance(binding, dict):
            schema = binding.get('schema')
            if isinstance(schema, dict):
                return schema
        return api.get('api_crud_schema')

    @staticmethod
    def _get_field_mappings(api: dict, endpoint_uri: str | None = None) -> list[dict]:
        binding = CrudService._resolve_binding(api, endpoint_uri)
        if not isinstance(binding, dict):
            return []
        raw = binding.get('field_mappings')
        if not isinstance(raw, list):
            return []
        mappings: list[dict] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            field = str(entry.get('field') or '').strip()
            if not field:
                continue
            request_path = str(
                entry.get('request_path') or entry.get('json_path') or field
            ).strip()
            response_path = str(
                entry.get('response_path') or entry.get('json_path') or request_path or field
            ).strip()
            mappings.append(
                {
                    'field': field,
                    'request_path': request_path or field,
                    'response_path': response_path or field,
                }
            )
        return mappings

    @staticmethod
    def _read_path(payload: dict, path: str):
        if not isinstance(payload, dict) or not path:
            return False, None
        if path in payload:
            return True, payload.get(path)

        current = payload
        parts = [p for p in str(path).split('.') if p]
        for part in parts:
            if isinstance(current, dict):
                if part not in current:
                    return False, None
                current = current.get(part)
                continue
            if isinstance(current, list):
                try:
                    idx = int(part)
                except Exception:
                    return False, None
                if idx < 0 or idx >= len(current):
                    return False, None
                current = current[idx]
                continue
            return False, None
        return True, current

    @staticmethod
    def _write_path(payload: dict, path: str, value):
        if not path:
            return
        parts = [p for p in str(path).split('.') if p]
        if not parts:
            return
        current = payload
        for idx, part in enumerate(parts):
            is_last = idx == len(parts) - 1
            if is_last:
                if isinstance(current, dict):
                    current[part] = value
                return
            if isinstance(current, dict):
                nxt = current.get(part)
                if not isinstance(nxt, dict):
                    nxt = {}
                    current[part] = nxt
                current = nxt
                continue
            return

    @staticmethod
    def _transform_incoming_payload(payload: dict, mappings: list[dict]) -> dict:
        if not isinstance(payload, dict) or not mappings:
            return payload if isinstance(payload, dict) else {}

        transformed: dict = {}
        for mapping in mappings:
            field = mapping.get('field')
            request_path = mapping.get('request_path')
            if not field or not request_path:
                continue
            exists, value = CrudService._read_path(payload, request_path)
            if exists:
                transformed[field] = value

        if '_id' in payload and '_id' not in transformed:
            transformed['_id'] = payload['_id']
        return transformed

    @staticmethod
    def _transform_outgoing_payload(payload: dict, mappings: list[dict]) -> dict:
        if not isinstance(payload, dict) or not mappings:
            return payload if isinstance(payload, dict) else {}

        transformed: dict = {}
        if payload.get('_id') is not None:
            transformed['_id'] = payload.get('_id')
        for mapping in mappings:
            field = mapping.get('field')
            response_path = mapping.get('response_path')
            if not field or not response_path:
                continue
            if field not in payload:
                continue
            CrudService._write_path(transformed, response_path, payload.get(field))
        return transformed

    @staticmethod
    def _transform_outgoing_list(payloads: list[dict], mappings: list[dict]) -> list[dict]:
        if not mappings:
            return payloads
        return [CrudService._transform_outgoing_payload(p, mappings) for p in payloads]

    @staticmethod
    def _validate_schema(schema: dict, data: dict, partial: bool = False, path: str = ""):
        """
        Validate data against schema.
        partial=True allows missing required fields (for PATCH/updates).
        path is used for recursion to track error location.
        Returns list of errors (empty if valid).
        """
        errors = []
        import re

        for field, rules in schema.items():
            current_path = f"{path}.{field}" if path else field
            value = data.get(field)
            
            # 1. Required check
            if rules.get('required') and value is None:
                if not partial:
                    errors.append(f"Field '{current_path}' is required")
                continue
            
            # Skip validation if value is missing (unless required, handled above)
            if value is None:
                continue

            # 2. Type check
            expected_type = rules.get('type')
            if expected_type:
                valid_type = True
                if expected_type == 'string' and not isinstance(value, str):
                    valid_type = False
                elif expected_type == 'number' and not isinstance(value, (int, float)):
                    valid_type = False
                elif expected_type == 'integer' and not isinstance(value, int):
                    valid_type = False
                elif expected_type == 'boolean' and not isinstance(value, bool):
                     valid_type = False
                elif expected_type == 'array' and not isinstance(value, list):
                    valid_type = False
                elif expected_type == 'object' and not isinstance(value, dict):
                    valid_type = False
                
                if not valid_type:
                    errors.append(f"Field '{current_path}' must be of type {expected_type}")
                    continue

            # 3. Constraints
            # String constraints
            if isinstance(value, str):
                if 'min_length' in rules and len(value) < rules['min_length']:
                    errors.append(f"Field '{current_path}' must be at least {rules['min_length']} characters")
                if 'max_length' in rules and len(value) > rules['max_length']:
                    errors.append(f"Field '{current_path}' must be at most {rules['max_length']} characters")
                if 'pattern' in rules:
                    try:
                        if not re.match(rules['pattern'], value):
                             errors.append(f"Field '{current_path}' does not match pattern {rules['pattern']}")
                    except Exception:
                        pass # Ignore invalid regex in schema
                if 'enum' in rules and value not in rules['enum']:
                    errors.append(f"Field '{current_path}' must be one of: {', '.join(map(str, rules['enum']))}")

            # Number constraints
            if isinstance(value, (int, float)):
                if 'min_value' in rules and value < rules['min_value']:
                    errors.append(f"Field '{current_path}' must be >= {rules['min_value']}")
                if 'max_value' in rules and value > rules['max_value']:
                    errors.append(f"Field '{current_path}' must be <= {rules['max_value']}")

            # 4. Recursion (Nested Objects)
            if expected_type == 'object' and isinstance(value, dict) and 'properties' in rules:
                # Recursively validate. Note: partial=False because providing an object usually replaces it.
                sub_errors = CrudService._validate_schema(
                    rules['properties'], 
                    value, 
                    partial=False, 
                    path=current_path
                )
                errors.extend(sub_errors)

        return errors

    @staticmethod
    async def handle_rest(api: dict, request: Request, request_id: str, endpoint_uri: str):
        """
        Handle REST CRUD operations.
        """
        method = request.method.upper()
        collection = CrudService._get_collection(api, endpoint_uri)
        schema = CrudService._get_schema(api, endpoint_uri)
        field_mappings = CrudService._get_field_mappings(api, endpoint_uri)
        
        # Normalize endpoint_uri to see if it's a specific resource lookup
        # /items -> list all
        # /items/uuid -> get specific item
        parts = [p for p in endpoint_uri.split('/') if p]
        resource_id = None
        if len(parts) > 1:
            # More than one part means the last part is the resource ID
            resource_id = parts[-1]

        try:
            if method == 'GET':
                if resource_id:
                    # Attempt to find by ID
                    doc = await db_find_one(collection, {'_id': resource_id})
                    if not doc:
                        return ResponseModel(
                            status_code=404,
                            error_code='CRUD404',
                            error_message='Resource not found',
                        ).dict()
                    if '_id' in doc:
                        doc['_id'] = str(doc['_id'])
                    if field_mappings:
                        doc = CrudService._transform_outgoing_payload(doc, field_mappings)
                    return ResponseModel(status_code=200, response=doc).dict()
                else:
                    # List all
                    docs = await db_find_list(collection, {})
                    for doc in docs:
                        if '_id' in doc:
                            doc['_id'] = str(doc['_id'])
                    if field_mappings:
                        docs = CrudService._transform_outgoing_list(docs, field_mappings)
                    return ResponseModel(status_code=200, response={'items': docs}).dict()

            elif method == 'POST':
                try:
                    body = await request.json()
                except Exception:
                    body = {}

                body = CrudService._transform_incoming_payload(body, field_mappings)
                
                if '_id' not in body:
                    body['_id'] = str(uuid.uuid4())
                
                # Validation
                if schema:
                    errors = CrudService._validate_schema(schema, body, partial=False)
                    if errors:
                        return ResponseModel(
                            status_code=400,
                            error_code='CRUD400',
                            error_message='Validation failed',
                            response={'errors': errors}
                        ).dict()

                result = await db_insert_one(collection, body)
                if result and hasattr(result, 'acknowledged') and result.acknowledged:
                    # Motor returns inserted_id, use it if available, otherwise use the _id we set
                    if hasattr(result, 'inserted_id') and result.inserted_id:
                        body['_id'] = str(result.inserted_id)
                    response_body = (
                        CrudService._transform_outgoing_payload(body, field_mappings)
                        if field_mappings
                        else body
                    )
                    return ResponseModel(
                        status_code=201, 
                        message='Resource created successfully',
                        response=response_body
                    ).dict()
                return ResponseModel(
                    status_code=500,
                    error_code='CRUD500',
                    error_message='Failed to create resource',
                ).dict()

            elif method == 'PUT' or method == 'PATCH':
                if not resource_id:
                    return ResponseModel(
                        status_code=400,
                        error_code='CRUD400',
                        error_message='Resource ID required for update',
                    ).dict()
                
                try:
                    body = await request.json()
                except Exception:
                    body = {}
                body = CrudService._transform_incoming_payload(body, field_mappings)
                
                # Validation
                if schema:
                    errors = CrudService._validate_schema(schema, body, partial=True)
                    if errors:
                        return ResponseModel(
                            status_code=400,
                            error_code='CRUD400',
                            error_message='Validation failed',
                            response={'errors': errors}
                        ).dict()
                
                # Check if exists
                existing = await db_find_one(collection, {'_id': resource_id})
                if not existing:
                    return ResponseModel(
                        status_code=404,
                        error_code='CRUD404',
                        error_message='Resource not found',
                    ).dict()

                update_op = {'$set': body}
                result = await db_update_one(collection, {'_id': resource_id}, update_op)
                if result and hasattr(result, 'acknowledged') and result.acknowledged:
                    updated = await db_find_one(collection, {'_id': resource_id})
                    if updated:
                        if '_id' in updated:
                            updated['_id'] = str(updated['_id'])
                        if field_mappings:
                            updated = CrudService._transform_outgoing_payload(updated, field_mappings)
                        return ResponseModel(
                            status_code=200,
                            message='Resource updated successfully',
                            response=updated
                        ).dict()
                return ResponseModel(
                    status_code=500,
                    error_code='CRUD500',
                    error_message='Failed to update resource',
                ).dict()

            elif method == 'DELETE':
                if not resource_id:
                    return ResponseModel(
                        status_code=400,
                        error_code='CRUD400',
                        error_message='Resource ID required for deletion',
                    ).dict()
                
                result = await db_delete_one(collection, {'_id': resource_id})
                if result and hasattr(result, 'acknowledged') and result.acknowledged:
                    if hasattr(result, 'deleted_count') and result.deleted_count > 0:
                        return ResponseModel(status_code=200, message='Resource deleted successfully').dict()
                return ResponseModel(
                    status_code=404,
                    error_code='CRUD404',
                    error_message='Resource not found',
                ).dict()

            else:
                return ResponseModel(
                    status_code=405,
                    error_code='CRUD405',
                    error_message='Method not allowed',
                ).dict()

        except Exception as e:
            logger.error(f'{request_id} | CRUD error: {str(e)}', exc_info=True)
            return ResponseModel(
                status_code=500,
                error_code='CRUD999',
                error_message=f'Internal CRUD error: {str(e)}',
            ).dict()

    @staticmethod
    def _generate_sdl(api: dict):
        """
        Generate GraphQL SDL from API Schema.
        """
        schema = api.get('api_crud_schema') or {}
        
        # Base Types
        types_sdl = ""
        
        # Recursive helper to generate types
        # For now, we flatten the structure or just use scalar helpers
        # To truly support recursion, we need generated type names
        
        def build_fields(prefix, properties):
            fields_str = ""
            for name, rules in properties.items():
                g_type = "String"
                t = rules.get('type')
                if t == 'number': g_type = "Float"
                elif t == 'boolean': g_type = "Boolean"
                elif t == 'array': g_type = "[String]" # Simplify array for now
                elif t == 'object': 
                    # For nested objects, we'd need to generate a new Type
                    # Simpler approach for Proto/MVP: Use JSON scalar or flatten
                    # Let's use a "JSON" scalar for detailed objects in this version
                    g_type = "JSON"
                
                # Check required
                if rules.get('required'):
                    g_type += "!"
                
                fields_str += f"  {name}: {g_type}\n"
            return fields_str

        resource_fields = build_fields("Item", schema)
        
        # Add _id field
        resource_fields = f"  _id: ID\n{resource_fields}"
        
        sdl = f"""
        scalar JSON
        
        type Item {{
        {resource_fields}
        }}
        
        type Query {{
            listItems: [Item]
            getItem(id: ID!): Item
        }}
        
        type Mutation {{
            createItem(input: JSON!): Item
            updateItem(id: ID!, input: JSON!): Item
            deleteItem(id: ID!): Boolean
        }}
        """
        return sdl

    @staticmethod
    async def handle_graphql(api: dict, request: Request, request_id: str, body: dict):
        """
        Handle GraphQL CRUD operations.
        """
        try:
            query = body.get('query')
            variables = body.get('variables')
            
            collection = CrudService._get_collection(api)
            
            # 1. Generate Schema
            type_defs = CrudService._generate_sdl(api)
            
            # 2. logical Resolvers
            query_type = QueryType()
            mutation_type = MutationType()

            @query_type.field("listItems")
            async def resolve_list(*_):
                items = await db_find_list(collection, {})
                for i in items:
                    if '_id' in i: i['_id'] = str(i['_id'])
                return items

            @query_type.field("getItem")
            async def resolve_get(*_, id):
                item = await db_find_one(collection, {'_id': id})
                if item and '_id' in item: item['_id'] = str(item['_id'])
                return item

            @mutation_type.field("createItem")
            async def resolve_create(*_, input):
                # Validate
                schema = api.get('api_crud_schema')
                if schema:
                    errors = CrudService._validate_schema(schema, input, partial=False)
                    if errors:
                        raise Exception(f"Validation failed: {json.dumps(errors)}")
                
                doc = input
                if '_id' not in doc: doc['_id'] = str(uuid.uuid4())
                
                await db_insert_one(collection, doc)
                return doc

            @mutation_type.field("updateItem")
            async def resolve_update(*_, id, input):
                # Validate partial
                schema = api.get('api_crud_schema')
                if schema:
                    errors = CrudService._validate_schema(schema, input, partial=True)
                    if errors:
                         raise Exception(f"Validation failed: {json.dumps(errors)}")
                
                await db_update_one(collection, {'_id': id}, {'$set': input})
                updated = await db_find_one(collection, {'_id': id})
                if updated and '_id' in updated: updated['_id'] = str(updated['_id'])
                return updated
            
            @mutation_type.field("deleteItem")
            async def resolve_delete(*_, id):
                res = await db_delete_one(collection, {'_id': id})
                return res.deleted_count > 0

            # 3. bind
            schema = make_executable_schema(type_defs, query_type, mutation_type)
            
            # 4. Execute
            success, result = await graphql(
                schema,
                data=body,
                context_value={"request": request, "api": api}
            )
            
            return ResponseModel(
                status_code=200,
                response=result
            ).dict()

        except Exception as e:
            logger.error(f'{request_id} | GraphQL CRUD error: {e}', exc_info=True)
            return ResponseModel(
                status_code=500,
                error_code='CRUD999',
                error_message=str(e)
            ).dict()

    @staticmethod
    def _generate_wsdl(api: dict):
        """
        Generate WSDL 1.1 + XSD from API Schema.
        """
        api_name = api.get('api_name')
        tns = f"http://doorman.dev/{api_name}"
        
        # Simple WSDL Template
        wsdl = f"""<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://schemas.xmlsoap.org/wsdl/"
             xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
             xmlns:tns="{tns}"
             xmlns:xs="http://www.w3.org/2001/XMLSchema"
             name="{api_name}Service"
             targetNamespace="{tns}">
             
    <types>
        <xs:schema targetNamespace="{tns}" elementFormDefault="qualified">
            <xs:element name="createItem">
                <xs:complexType>
                    <xs:sequence>
                        <xs:element name="input" type="xs:string"/> <!-- Simplified: Pass JSON string for now or generate fields -->
                    </xs:sequence>
                </xs:complexType>
            </xs:element>
            <xs:element name="createItemResponse">
                <xs:complexType>
                    <xs:sequence>
                       <xs:element name="result" type="xs:string"/>
                    </xs:sequence>
                </xs:complexType>
            </xs:element>
             <xs:element name="listItems">
                <xs:complexType/>
            </xs:element>
            <xs:element name="listItemsResponse">
                <xs:complexType>
                     <xs:sequence>
                        <xs:element name="items" type="xs:string"/>
                     </xs:sequence>
                </xs:complexType>
            </xs:element>
        </xs:schema>
    </types>

    <message name="createItemRequest">
        <part name="parameters" element="tns:createItem"/>
    </message>
    <message name="createItemResponse">
        <part name="parameters" element="tns:createItemResponse"/>
    </message>
    <message name="listItemsRequest">
        <part name="parameters" element="tns:listItems"/>
    </message>
    <message name="listItemsResponse">
        <part name="parameters" element="tns:listItemsResponse"/>
    </message>

    <portType name="{api_name}PortType">
        <operation name="createItem">
            <input message="tns:createItemRequest"/>
            <output message="tns:createItemResponse"/>
        </operation>
        <operation name="listItems">
             <input message="tns:listItemsRequest"/>
             <output message="tns:listItemsResponse"/>
        </operation>
    </portType>

    <binding name="{api_name}Binding" type="tns:{api_name}PortType">
        <soap:binding style="document" transport="http://schemas.xmlsoap.org/soap/http"/>
        <operation name="createItem">
            <soap:operation soapAction="{tns}/createItem"/>
            <input><soap:body use="literal"/></input>
            <output><soap:body use="literal"/></output>
        </operation>
        <operation name="listItems">
            <soap:operation soapAction="{tns}/listItems"/>
            <input><soap:body use="literal"/></input>
            <output><soap:body use="literal"/></output>
        </operation>
    </binding>

    <service name="{api_name}Service">
        <port name="{api_name}Port" binding="tns:{api_name}Binding">
            <soap:address location="http://localhost:8080/api/soap/{api_name}"/>
        </port>
    </service>
</definitions>
        """
        return wsdl

    @staticmethod
    async def handle_soap(api: dict, request: Request, request_id: str, body: bytes):
        """
        Handle SOAP CRUD operations.
        """
        try:
            # Check for WSDL request
            if request.method == 'GET' and 'wsdl' in request.query_params:
                wsdl_content = CrudService._generate_wsdl(api)
                return ResponseModel(
                    status_code=200,
                    response=wsdl_content,
                    response_headers={'Content-Type': 'text/xml'}
                ).dict()

            # Parse Envelope
            from utils.wsdl_util import _safe_parse_xml
            try:
                envelope = _safe_parse_xml(body)
            except Exception as e:
                raise Exception(f"Invalid XML: {e}")

            # Namespace handling
            ns_map = {
                'soap11': 'http://schemas.xmlsoap.org/soap/envelope/',
                'soap12': 'http://www.w3.org/2003/05/soap-envelope',
            }
            body_elem = envelope.find('.//soap11:Body', ns_map) 
            if body_elem is None:
                body_elem = envelope.find('.//soap12:Body', ns_map)
            
            if body_elem is None:
                # Fallback: finding 'Body' ignoring namespace
                for child in envelope:
                    if 'Body' in child.tag:
                        body_elem = child
                        break
            
            if body_elem is None:
                raise Exception("SOAP Body not found")

            # Get Operation
            if len(body_elem) == 0:
                 raise Exception("Empty SOAP Body")
            
            op_elem = body_elem[0]
            op_name = op_elem.tag.split('}')[-1] if '}' in op_elem.tag else op_elem.tag
            
            logger.info(f"{request_id} | SOAP Operation: {op_name}")
            
            collection = CrudService._get_collection(api)
            result_xml = ""

            if op_name == 'createItem':
                # Parse Input (Expects <input>JSON</input>)
                input_elem = None
                for child in op_elem:
                    if 'input' in child.tag:
                        input_elem = child
                        break
                
                if input_elem is None or not input_elem.text:
                    raise Exception("Missing input element or empty")
                
                try:
                    payload = json.loads(input_elem.text)
                except json.JSONDecodeError:
                     raise Exception("Input must be valid JSON string")
                
                # Validation
                schema = api.get('api_crud_schema')
                if schema:
                    errors = CrudService._validate_schema(schema, payload, partial=False)
                    if errors:
                        raise Exception(f"Validation failed: {json.dumps(errors)}")

                if '_id' not in payload:
                    payload['_id'] = str(uuid.uuid4())
                
                await db_insert_one(collection, payload)
                
                result_xml = f"<tns:result>{json.dumps(payload)}</tns:result>"
                resp_tag = "createItemResponse"

            elif op_name == 'listItems':
                items = await db_find_list(collection, {})
                for i in items:
                    if '_id' in i: i['_id'] = str(i['_id'])
                
                result_xml = f"<tns:items>{json.dumps(items)}</tns:items>"
                resp_tag = "listItemsResponse"

            elif op_name == 'getItem':
                 # Not implemented in WSDL yet, skipping
                 raise Exception(f"Operation {op_name} not supported yet")

            else:
                raise Exception(f"Unknown operation: {op_name}")

            # Construct Response
            api_name = api.get('api_name')
            tns = f"http://doorman.dev/{api_name}"
            
            response_envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="{tns}">
    <soap:Body>
        <tns:{resp_tag}>
            {result_xml}
        </tns:{resp_tag}>
    </soap:Body>
</soap:Envelope>"""

            return ResponseModel(
                status_code=200,
                response=response_envelope,
                response_headers={'Content-Type': 'text/xml'}
            ).dict()

        except Exception as e:
             logger.error(f'{request_id} | SOAP CRUD error: {e}', exc_info=True)
             # SOAP Fault
             fault_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <soap:Fault>
            <faultcode>soap:Server</faultcode>
            <faultstring>{str(e)}</faultstring>
        </soap:Fault>
    </soap:Body>
</soap:Envelope>"""
             return ResponseModel(
                status_code=500,
                response=fault_xml,
                response_headers={'Content-Type': 'text/xml'}
            ).dict()

    @staticmethod
    def _generate_proto(api: dict):
        """
        Generate Protobuf v3 definition from API Schema.
        """
        api_name = api.get('api_name').replace('-', '_') # Proto packages no dashes
        schema = api.get('api_crud_schema') or {}
        
        # Type Mapping
        type_map = {
            'string': 'string',
            'number': 'double',
            'integer': 'int32',
            'boolean': 'bool',
            'object': 'string', # Simplification: JSON string for nested objects
            'array': 'repeated string' # Simplification
        }
        
        fields = []
        i = 1
        for field, rules in schema.items():
            ftype = rules.get('type', 'string')
            ptype = type_map.get(ftype, 'string')
            fields.append(f"  {ptype} {field} = {i};")
            i += 1
            
        fields_str = "\n".join(fields)
        
        proto = f"""syntax = "proto3";

package {api_name};

service {api_name.capitalize()}Service {{
  rpc CreateItem (CreateItemRequest) returns (CreateItemResponse);
  rpc ListItems (ListItemsRequest) returns (ListItemsResponse);
}}

message CreateItemRequest {{
{fields_str}
}}

message CreateItemResponse {{
  string result = 1; // JSON string of created object
}}

message ListItemsRequest {{}}

message ListItemsResponse {{
  string items = 1; // JSON string of list
}}
"""
        return proto

    @staticmethod
    async def handle_grpc(api: dict, request: Request, request_id: str):
        """
        Handle gRPC requests (Proto generation and Execution).
        """
        try:
             # Check for Proto request
            if request.method == 'GET' and 'proto' in request.query_params:
                proto_content = CrudService._generate_proto(api)
                return ResponseModel(
                    status_code=200,
                    response=proto_content,
                    response_headers={'Content-Type': 'text/plain'}
                ).dict()
            
            # Execution (Not Implemented - requires gRPC server or transcoding)
            return ResponseModel(
                status_code=501,
                error_code='CRUD999',
                error_message='gRPC Execution Not Implemented Yet (Requires HTTP/2 Server)'
            ).dict()

        except Exception as e:
             logger.error(f'{request_id} | gRPC CRUD error: {e}', exc_info=True)
             return ResponseModel(
                status_code=500,
                error_code='CRUD999',
                error_message=str(e)
            ).dict()
