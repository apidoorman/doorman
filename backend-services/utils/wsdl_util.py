"""
WSDL and SOAP Utilities

Provides:
- WSDL fetching and parsing
- SOAP version detection (1.1 vs 1.2)
- WS-Security header injection
"""

import hashlib
import logging
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from xml.etree import ElementTree as ET

# Strict requirement for XXE protection
import defusedxml.ElementTree as SafeET

import httpx

logger = logging.getLogger('doorman.gateway')

# SOAP namespaces
SOAP_11_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
SOAP_12_NS = 'http://www.w3.org/2003/05/soap-envelope'
WSDL_NS = 'http://schemas.xmlsoap.org/wsdl/'
WSSE_NS = 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd'
WSU_NS = 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd'


def _safe_parse_xml(xml_string: str | bytes) -> ET.Element:
    """
    Safely parse XML with XXE protection.
    
    Args:
        xml_string: XML content as string or bytes
        
    Returns:
        Parsed ElementTree Element
        
    Raises:
        ValueError: If parsing fails
    """
    if isinstance(xml_string, str):
        xml_string = xml_string.encode('utf-8')
    
    try:
        return SafeET.fromstring(xml_string)
    except ET.ParseError as e:
        raise ValueError(f'Invalid XML: {e}')


def detect_soap_version(envelope: str | bytes) -> str:
    """
    Detect SOAP version from envelope namespace.
    
    Args:
        envelope: SOAP envelope XML
        
    Returns:
        "1.1" or "1.2"
    """
    try:
        root = _safe_parse_xml(envelope)
        ns = root.tag.split('}')[0].strip('{') if '}' in root.tag else ''
        
        if ns == SOAP_12_NS or 'soap-envelope' in ns.lower():
            return '1.2'
        return '1.1'
    except Exception:
        # Default to 1.1 if detection fails
        return '1.1'


def get_content_type_for_version(version: str, action: str | None = None) -> str:
    """
    Get appropriate Content-Type header for SOAP version.
    
    Args:
        version: "1.1" or "1.2"
        action: Optional SOAPAction for 1.2
        
    Returns:
        Content-Type header value
    """
    if version == '1.2':
        if action:
            return f'application/soap+xml; charset=utf-8; action="{action}"'
        return 'application/soap+xml; charset=utf-8'
    else:
        return 'text/xml; charset=utf-8'


async def fetch_wsdl(url: str, timeout: float = 30.0) -> str | None:
    """
    Fetch WSDL document from URL.
    
    Args:
        url: WSDL URL
        timeout: Request timeout
        
    Returns:
        WSDL content or None if failed
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return response.text
            logger.warning(f'Failed to fetch WSDL from {url}: {response.status_code}')
            return None
    except Exception as e:
        logger.error(f'Error fetching WSDL: {e}')
        return None


def parse_wsdl(wsdl_content: str) -> dict:
    """
    Parse WSDL and extract service information.
    
    Args:
        wsdl_content: WSDL XML content
        
    Returns:
        Dictionary with parsed WSDL info:
        {
            'service_name': str,
            'target_namespace': str,
            'operations': [
                {
                    'name': str,
                    'soap_action': str,
                    'input_message': str,
                    'output_message': str,
                }
            ],
            'endpoints': [
                {'uri': str, 'method': 'POST'}
            ]
        }
    """
    result = {
        'service_name': '',
        'target_namespace': '',
        'operations': [],
        'endpoints': [],
    }
    
    try:
        root = _safe_parse_xml(wsdl_content)
        
        # Get target namespace
        result['target_namespace'] = root.get('targetNamespace', '')
        
        # Define namespace map for WSDL parsing
        ns = {
            'wsdl': WSDL_NS,
            'soap11': 'http://schemas.xmlsoap.org/wsdl/soap/',
            'soap12': 'http://schemas.xmlsoap.org/wsdl/soap12/',
        }
        
        # Find service name
        service = root.find('.//wsdl:service', ns) or root.find('.//{http://schemas.xmlsoap.org/wsdl/}service')
        if service is not None:
            result['service_name'] = service.get('name', '')
        
        # Find operations from portType
        for port_type in root.findall('.//wsdl:portType', ns) or root.findall('.//{http://schemas.xmlsoap.org/wsdl/}portType'):
            for operation in port_type.findall('wsdl:operation', ns) or port_type.findall('{http://schemas.xmlsoap.org/wsdl/}operation'):
                op_name = operation.get('name', '')
                if not op_name:
                    continue
                
                op_info = {
                    'name': op_name,
                    'soap_action': '',
                    'input_message': '',
                    'output_message': '',
                }
                
                # Find input/output
                input_elem = operation.find('wsdl:input', ns) or operation.find('{http://schemas.xmlsoap.org/wsdl/}input')
                output_elem = operation.find('wsdl:output', ns) or operation.find('{http://schemas.xmlsoap.org/wsdl/}output')
                
                if input_elem is not None:
                    msg = input_elem.get('message', '')
                    op_info['input_message'] = msg.split(':')[-1] if ':' in msg else msg
                    
                if output_elem is not None:
                    msg = output_elem.get('message', '')
                    op_info['output_message'] = msg.split(':')[-1] if ':' in msg else msg
                
                result['operations'].append(op_info)
        
        # Find SOAPAction from binding
        for binding in root.findall('.//wsdl:binding', ns) or root.findall('.//{http://schemas.xmlsoap.org/wsdl/}binding'):
            for operation in binding.findall('wsdl:operation', ns) or binding.findall('{http://schemas.xmlsoap.org/wsdl/}operation'):
                op_name = operation.get('name', '')
                
                # Look for SOAP operation element
                soap_op = (
                    operation.find('soap11:operation', ns) or 
                    operation.find('soap12:operation', ns) or
                    operation.find('{http://schemas.xmlsoap.org/wsdl/soap/}operation') or
                    operation.find('{http://schemas.xmlsoap.org/wsdl/soap12/}operation')
                )
                
                if soap_op is not None:
                    soap_action = soap_op.get('soapAction', '')
                    # Update matching operation
                    for op in result['operations']:
                        if op['name'] == op_name:
                            op['soap_action'] = soap_action
                            break
        
        # Convert operations to endpoints
        for op in result['operations']:
            result['endpoints'].append({
                'uri': f"/{op['name']}",
                'method': 'POST',
                'soap_action': op.get('soap_action', ''),
                'description': f"SOAP operation: {op['name']}",
            })
        
        return result
        
    except Exception as e:
        logger.error(f'Error parsing WSDL: {e}')
        return result


def create_ws_security_header(
    username: str | None = None,
    password: str | None = None,
    password_type: str = 'PasswordText',
    add_timestamp: bool = True,
    timestamp_ttl_seconds: int = 300,
    add_nonce: bool = True,
) -> str:
    """
    Create WS-Security header XML.
    
    Args:
        username: Username for UsernameToken
        password: Password (plaintext or will be hashed)
        password_type: 'PasswordText', 'PasswordDigest' (SHA-1 for legacy compatibility),
                       or 'PasswordDigestSHA256' (preferred, stronger digest)
        add_timestamp: Add Timestamp element
        timestamp_ttl_seconds: Timestamp validity duration
        add_nonce: Add Nonce to UsernameToken
        
    Returns:
        WS-Security header XML string
    """
    wsu_id = f'Timestamp-{uuid.uuid4()}'
    now = datetime.now(timezone.utc)
    created = now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
    expires = (now + timedelta(seconds=timestamp_ttl_seconds)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    
    header_parts = [
        f'<wsse:Security xmlns:wsse="{WSSE_NS}" xmlns:wsu="{WSU_NS}">'
    ]
    
    # Add Timestamp
    if add_timestamp:
        header_parts.append(f'''
    <wsu:Timestamp wsu:Id="{wsu_id}">
        <wsu:Created>{created}</wsu:Created>
        <wsu:Expires>{expires}</wsu:Expires>
    </wsu:Timestamp>''')
    
    # Add UsernameToken
    if username:
        nonce_value = secrets.token_bytes(16)
        nonce_b64 = __import__('base64').b64encode(nonce_value).decode('ascii')
        
        if password and password_type in ('PasswordDigest', 'PasswordDigestSHA256'):
            # Digest = Base64(HASH(Nonce + Created + Password))
            digest_input = nonce_value + created.encode('utf-8') + password.encode('utf-8')
            if password_type == 'PasswordDigestSHA256':
                # WS-Security 1.1 requires SHA-256 for PasswordDigestSHA256.
                # This is a network digest, NOT used for local password storage.
                digest_bytes = hashlib.sha256(digest_input).digest()  # codeql[py/weak-cryptographic-algorithm]: WS-Security UsernameToken digest (transport-level), not password storage
                password_type_uri = (
                    'http://docs.oasis-open.org/wss/2004/01/'
                    'oasis-200401-wss-username-token-profile-1.1#PasswordDigestSHA256'
                )
            else:
                # Legacy UsernameToken Profile PasswordDigest (SHA-1)
                # Specified by OASIS standard; required for SOAP interoperability.
                digest_bytes = hashlib.sha1(digest_input).digest()  # codeql[py/weak-cryptographic-algorithm]: Legacy WS-Security digest for interoperability; not used for password storage
                password_type_uri = (
                    'http://docs.oasis-open.org/wss/2004/01/'
                    'oasis-200401-wss-username-token-profile-1.0#PasswordDigest'
                )
            password_digest = __import__('base64').b64encode(digest_bytes).decode('ascii')
            password_elem = f'''
        <wsse:Password Type="{password_type_uri}">{password_digest}</wsse:Password>'''
        else:
            # Plain text password
            password_elem = f'''
        <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">{password or ''}</wsse:Password>''' if password else ''
        
        nonce_elem = f'''
        <wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">{nonce_b64}</wsse:Nonce>''' if add_nonce else ''
        
        header_parts.append(f'''
    <wsse:UsernameToken wsu:Id="UsernameToken-{uuid.uuid4()}">
        <wsse:Username>{username}</wsse:Username>{password_elem}{nonce_elem}
        <wsu:Created>{created}</wsu:Created>
    </wsse:UsernameToken>''')
    
    header_parts.append('\n</wsse:Security>')
    
    return ''.join(header_parts)


def inject_ws_security(envelope: str, security_header: str) -> str:
    """
    Inject WS-Security header into SOAP envelope.
    
    Args:
        envelope: Original SOAP envelope
        security_header: WS-Security header XML
        
    Returns:
        Modified envelope with security header
    """
    try:
        # Parse to find Header element
        root = _safe_parse_xml(envelope)
        
        # Determine namespace
        ns = root.tag.split('}')[0].strip('{') if '}' in root.tag else SOAP_11_NS
        ns_prefix = 'soap12' if ns == SOAP_12_NS else 'soap'
        
        # Find or create Header
        header = None
        for child in root:
            if 'Header' in child.tag:
                header = child
                break
        
        if header is None:
            # Create Header element
            header = ET.Element(f'{{{ns}}}Header')
            root.insert(0, header)
        
        # Parse and insert security header
        security_elem = _safe_parse_xml(security_header)
        header.insert(0, security_elem)
        
        # Serialize back
        return ET.tostring(root, encoding='unicode')
        
    except Exception as e:
        logger.error(f'Failed to inject WS-Security header: {e}')
        # Return original if injection fails
        return envelope


def validate_wsdl_content(wsdl_content: str) -> tuple[bool, str | None]:
    """
    Validate WSDL content structure.
    
    Args:
        wsdl_content: WSDL XML content
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not wsdl_content or not wsdl_content.strip():
        return False, 'Empty WSDL content'
    
    try:
        root = _safe_parse_xml(wsdl_content)
        
        # Check root element
        if 'definitions' not in root.tag.lower():
            return False, 'Root element must be wsdl:definitions'
        
        # Check for at least one service or portType
        ns = {'wsdl': WSDL_NS}
        has_service = root.find('.//wsdl:service', ns) or root.find('.//{http://schemas.xmlsoap.org/wsdl/}service')
        has_porttype = root.find('.//wsdl:portType', ns) or root.find('.//{http://schemas.xmlsoap.org/wsdl/}portType')
        
        if not has_service and not has_porttype:
            return False, 'WSDL must contain at least one service or portType'
        
        return True, None
        
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        return False, f'WSDL validation failed: {e}'
