"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from typing import Dict, Any, Optional, Callable
from fastapi import HTTPException
from models.field_validation_model import FieldValidation
from models.validation_schema_model import ValidationSchema
from utils.cache_manager_util import cache_manager
import json
import re
from datetime import datetime
import uuid
import xml.etree.ElementTree as ET
from graphql import parse, GraphQLError
import grpc
from zeep import Client, Settings
from zeep.exceptions import Fault, ValidationError as ZeepValidationError

class ValidationError(Exception):
    def __init__(self, message: str, field_path: str):
        self.message = message
        self.field_path = field_path
        super().__init__(self.message)

class ValidationUtil:
    def __init__(self):
        self.type_validators = {
            "string": self._validate_string,
            "number": self._validate_number,
            "boolean": self._validate_boolean,
            "array": self._validate_array,
            "object": self._validate_object
        }
        self.format_validators = {
            "email": self._validate_email,
            "url": self._validate_url,
            "date": self._validate_date,
            "datetime": self._validate_datetime,
            "uuid": self._validate_uuid
        }
        self.custom_validators: Dict[str, Callable] = {}
        self.wsdl_clients: Dict[str, Client] = {}

    def register_custom_validator(self, name: str, validator: Callable[[Any, FieldValidation], None]) -> None:
        self.custom_validators[name] = validator

    async def get_validation_schema(self, endpoint_id: str) -> Optional[ValidationSchema]:
        schema_data = await cache_manager.get(f"validation_schema:{endpoint_id}")
        if not schema_data:
            return None
        schema = ValidationSchema(validation_schema=json.loads(schema_data))
        self._validate_schema_paths(schema.validation_schema)
        return schema

    def _validate_schema_paths(self, schema: Dict[str, FieldValidation], parent_path: str = "") -> None:
        for field_path, validation in schema.items():
            full_path = f"{parent_path}.{field_path}" if parent_path else field_path
            if not self._is_valid_field_path(full_path):
                raise ValidationError(f"Invalid field path: {full_path}", full_path)
            if validation.nested_schema:
                self._validate_schema_paths(validation.nested_schema, full_path)

    def _is_valid_field_path(self, path: str) -> bool:
        parts = path.split('.')
        for part in parts:
            if '[' in part:
                field, index = part.split('[')
                if not field and not index.rstrip(']').isdigit():
                    return False
            if not part or part.startswith('.') or part.endswith('.'):
                return False
        return True

    def _validate_string(self, value: Any, validation: FieldValidation) -> None:
        if not isinstance(value, str):
            raise ValidationError(f"Expected string, got {type(value).__name__}", validation.field_path)
        if validation.min is not None and len(value) < validation.min:
            raise ValidationError(f"String length must be at least {validation.min}", validation.field_path)
        if validation.max is not None and len(value) > validation.max:
            raise ValidationError(f"String length must be at most {validation.max}", validation.field_path)
        if validation.pattern and not re.match(validation.pattern, value):
            raise ValidationError(f"String does not match pattern {validation.pattern}", validation.field_path)
        if validation.format and validation.format in self.format_validators:
            self.format_validators[validation.format](value, validation)

    def _validate_number(self, value: Any, validation: FieldValidation) -> None:
        if not isinstance(value, (int, float)):
            raise ValidationError(f"Expected number, got {type(value).__name__}", validation.field_path)
        if validation.min is not None and value < validation.min:
            raise ValidationError(f"Value must be at least {validation.min}", validation.field_path)
        if validation.max is not None and value > validation.max:
            raise ValidationError(f"Value must be at most {validation.max}", validation.field_path)

    def _validate_boolean(self, value: Any, validation: FieldValidation) -> None:
        if not isinstance(value, bool):
            raise ValidationError(f"Expected boolean, got {type(value).__name__}", validation.field_path)

    def _validate_array(self, value: Any, validation: FieldValidation) -> None:
        if not isinstance(value, list):
            raise ValidationError(f"Expected array, got {type(value).__name__}", validation.field_path)
        if validation.min is not None and len(value) < validation.min:
            raise ValidationError(f"Array must have at least {validation.min} items", validation.field_path)
        if validation.max is not None and len(value) > validation.max:
            raise ValidationError(f"Array must have at most {validation.max} items", validation.field_path)
        if validation.array_items:
            for i, item in enumerate(value):
                try:
                    self._validate_value(item, validation.array_items, f"{validation.field_path}[{i}]")
                except ValidationError as e:
                    raise ValidationError(e.message, e.field_path)

    def _validate_object(self, value: Any, validation: FieldValidation) -> None:
        if not isinstance(value, dict):
            raise ValidationError(f"Expected object, got {type(value).__name__}", validation.field_path)
        if validation.nested_schema:
            for field_path, field_validation in validation.nested_schema.items():
                if field_validation.required and field_path not in value:
                    raise ValidationError(f"Required field {field_path} is missing", validation.field_path)
                if field_path in value:
                    try:
                        self._validate_value(value[field_path], field_validation, f"{validation.field_path}.{field_path}")
                    except ValidationError as e:
                        raise ValidationError(e.message, e.field_path)

    def _validate_value(self, value: Any, validation: FieldValidation, field_path: str) -> None:
        validation.field_path = field_path
        if validation.required and value is None:
            raise ValidationError("Field is required", field_path)
        if value is None:
            return
        if validation.type in self.type_validators:
            self.type_validators[validation.type](value, validation)
        if validation.enum and value not in validation.enum:
            raise ValidationError(f"Value must be one of {validation.enum}", field_path)
        if validation.custom_validator and validation.custom_validator in self.custom_validators:
            self.custom_validators[validation.custom_validator](value, validation)

    def _validate_email(self, value: str, validation: FieldValidation) -> None:
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, value):
            raise ValidationError("Invalid email format", validation.field_path)

    def _validate_url(self, value: str, validation: FieldValidation) -> None:
        url_pattern = r'^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$'
        if not re.match(url_pattern, value):
            raise ValidationError("Invalid URL format", validation.field_path)

    def _validate_date(self, value: str, validation: FieldValidation) -> None:
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            raise ValidationError("Invalid date format (YYYY-MM-DD)", validation.field_path)

    def _validate_datetime(self, value: str, validation: FieldValidation) -> None:
        try:
            datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            raise ValidationError("Invalid datetime format (ISO 8601)", validation.field_path)

    def _validate_uuid(self, value: str, validation: FieldValidation) -> None:
        try:
            uuid.UUID(value)
        except ValueError:
            raise ValidationError("Invalid UUID format", validation.field_path)

    async def validate_rest_request(self, endpoint_id: str, request_data: Dict[str, Any]) -> None:
        schema = await self.get_validation_schema(endpoint_id)
        if not schema:
            return
        for field_path, validation in schema.validation_schema.items():
            try:
                value = self._get_nested_value(request_data, field_path)
                self._validate_value(value, validation, field_path)
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=str(e))

    async def validate_soap_request(self, endpoint_id: str, soap_envelope: str) -> None:
        schema = await self.get_validation_schema(endpoint_id)
        if not schema:
            return
        try:
            root = ET.fromstring(soap_envelope)
            body = root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Body")
            if body is None:
                raise ValidationError("SOAP Body not found", "Body")
            wsdl_client = await self._get_wsdl_client(endpoint_id)
            if wsdl_client:
                try:
                    operation = self._get_soap_operation(body[0].tag)
                    if operation:
                        wsdl_client.service.validate(operation, body[0])
                except (Fault, ZeepValidationError) as e:
                    raise ValidationError(f"WSDL validation failed: {str(e)}", "Body")
            request_data = self._xml_to_dict(body[0])
            for field_path, validation in schema.validation_schema.items():
                try:
                    value = self._get_nested_value(request_data, field_path)
                    self._validate_value(value, validation, field_path)
                except ValidationError as e:
                    raise HTTPException(status_code=400, detail=str(e))
        except ET.ParseError:
            raise HTTPException(status_code=400, detail="Invalid SOAP envelope")
    async def validate_grpc_request(self, endpoint_id: str, request: Any) -> None:
        schema = await self.get_validation_schema(endpoint_id)
        if not schema:
            return
        request_data = self._protobuf_to_dict(request)
        for field_path, validation in schema.validation_schema.items():
            try:
                value = self._get_nested_value(request_data, field_path)
                self._validate_value(value, validation, field_path)
            except ValidationError as e:
                raise grpc.RpcError(grpc.StatusCode.INVALID_ARGUMENT, str(e))

    async def validate_graphql_request(self, endpoint_id: str, query: str, variables: Dict[str, Any]) -> None:
        schema = await self.get_validation_schema(endpoint_id)
        if not schema:
            return
        try:
            parse(query)
            operation_name = self._extract_operation_name(query)
            if operation_name:
                for field_path, validation in schema.validation_schema.items():
                    if field_path.startswith(operation_name):
                        try:
                            value = self._get_nested_value(variables, field_path[len(operation_name)+1:])
                            self._validate_value(value, validation, field_path)
                        except ValidationError as e:
                            raise HTTPException(status_code=400, detail=str(e))
        except GraphQLError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    def _extract_operation_name(self, query: str) -> Optional[str]:
        match = re.search(r'(?:query|mutation)\s+(\w+)', query)
        return match.group(1) if match else None

    def _get_nested_value(self, data: Dict[str, Any], field_path: str) -> Any:
        parts = field_path.split('.')
        current = data
        for part in parts:
            if '[' in part:
                field, index = part.split('[')
                index = int(index.rstrip(']'))
                if field:
                    current = current.get(field, [])
                if not isinstance(current, list) or index >= len(current):
                    return None
                current = current[index]
            else:
                if not isinstance(current, dict):
                    return None
                current = current.get(part)
                if current is None:
                    return None
        return current

    def _xml_to_dict(self, element: ET.Element) -> Dict[str, Any]:
        result = {}
        for child in element:
            if len(child) > 0:
                result[child.tag] = self._xml_to_dict(child)
            else:
                result[child.tag] = child.text
        return result

    def _protobuf_to_dict(self, message: Any) -> Dict[str, Any]:
        result = {}
        for field in message.DESCRIPTOR.fields:
            value = getattr(message, field.name)
            if field.type == field.TYPE_MESSAGE:
                if field.label == field.LABEL_REPEATED:
                    result[field.name] = [self._protobuf_to_dict(item) for item in value]
                else:
                    result[field.name] = self._protobuf_to_dict(value)
            else:
                result[field.name] = value
        return result

    async def _get_wsdl_client(self, endpoint_id: str) -> Optional[Client]:
        if endpoint_id in self.wsdl_clients:
            return self.wsdl_clients[endpoint_id]
        wsdl_url = await cache_manager.get(f"wsdl_url:{endpoint_id}")
        if not wsdl_url:
            return None

        try:
            settings = Settings(strict=True)
            client = Client(wsdl_url, settings=settings)
            self.wsdl_clients[endpoint_id] = client
            return client
        except Exception as e:
            return None

    def _get_soap_operation(self, element_tag: str) -> Optional[str]:
        match = re.search(r'\{[^}]+\}([^}]+)$', element_tag)
        return match.group(1) if match else None

validation_util = ValidationUtil() 