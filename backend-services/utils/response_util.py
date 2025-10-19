from fastapi.responses import JSONResponse, Response
import os
import logging

from models.response_model import ResponseModel

logger = logging.getLogger('doorman.gateway')

def _normalize_headers(hdrs: dict | None) -> dict | None:
    try:
        if not hdrs:
            return hdrs

        out = dict(hdrs)
        rid = out.get('request_id') or out.get('Request-Id') or out.get('X-Request-ID')

        if rid and 'X-Request-ID' not in out:
            out['X-Request-ID'] = rid
        return out
    except Exception:
        return hdrs

def _envelope(content: dict, status_code: int) -> dict:
    return {
        'status_code': status_code,
        **content
    }

def _add_token_compat(enveloped: dict, payload: dict):
    try:

        if isinstance(payload, dict):
            for key in ('access_token', 'refresh_token'):
                if key in payload:
                    enveloped[key] = payload[key]
    except Exception:
        pass

def respond_rest(model):
    """Return a REST JSONResponse using the normalized envelope logic.

    Accepts either a ResponseModel instance or a dict suitable for ResponseModel.
    """
    if isinstance(model, dict):
        rm = ResponseModel(**model)
    else:
        rm = model
    return process_rest_response(rm)

def process_rest_response(response):
    try:
        strict = os.getenv('STRICT_RESPONSE_ENVELOPE', 'false').lower() == 'true'

        ok = 200 <= int(response.status_code) < 300
        if ok:
            if getattr(response, 'response', None) is not None:
                if not strict:
                    content = response.response
                    http_status = response.status_code
                else:
                    content = _envelope({'response': response.response}, response.status_code)
                    _add_token_compat(content, response.response)
                    http_status = 200
            elif response.message:
                content = {'message': response.message} if not strict else _envelope({'message': response.message}, response.status_code)
                http_status = response.status_code if not strict else 200
            else:
                content = {} if not strict else _envelope({}, response.status_code)
                http_status = response.status_code if not strict else 200
            resp = JSONResponse(content=content, status_code=http_status, headers=_normalize_headers(response.response_headers))
            try:
                # Ensure Content-Length is set for downstream metrics/bandwidth accounting
                blen = len(getattr(resp, 'body', b'') or b'')
                if blen > 0:
                    resp.headers['Content-Length'] = str(blen)
                    resp.headers['X-Body-Length'] = str(blen)
            except Exception:
                pass
            return resp

        err_payload = {}
        if getattr(response, 'error_code', None):
            err_payload['error_code'] = response.error_code

        if getattr(response, 'error_message', None):
            err_payload['error_message'] = response.error_message
        elif getattr(response, 'message', None):
            err_payload['error_message'] = response.message

        if not err_payload:
            err_payload = {'error_message': 'Request failed'}

        content = err_payload if not strict else _envelope(err_payload, response.status_code)
        http_status = response.status_code if not strict else 200
        resp = JSONResponse(content=content, status_code=http_status, headers=_normalize_headers(response.response_headers))
        try:
            blen = len(getattr(resp, 'body', b'') or b'')
            if blen > 0:
                resp.headers['Content-Length'] = str(blen)
                resp.headers['X-Body-Length'] = str(blen)
        except Exception:
            pass
        return resp
    except Exception as e:
        logger.error(f'An error occurred while processing the response: {e}')
        return JSONResponse(content={'error_message': 'Unable to process response'}, status_code=500)

def process_soap_response(response):
    try:
        strict = os.getenv('STRICT_RESPONSE_ENVELOPE', 'false').lower() == 'true'
        if response.status_code == 200:
            if getattr(response, 'soap_envelope', None):
                soap_response = response.soap_envelope
            else:
                soap_response = response.response
        elif response.status_code == 201:
            soap_response = f'<message>{response.message}</message>'
        elif response.status_code in (400, 403, 404):
            soap_response = (
                f'<error>'
                f'<error_code>{response.error_code}</error_code>'
                f'<error_message>{response.error_message}</error_message>'
                f'</error>'
            )
        else:
            soap_response = '<message>An unknown error occurred in SOAP response</message>'

        return Response(
            content=soap_response,
            status_code=response.status_code,
            media_type='application/xml',
            headers=_normalize_headers(response.response_headers),
        )
    except Exception as e:
        logger.error(f'An error occurred while processing the SOAP response: {e}')
        error_response = '<error>Unable to process SOAP response</error>'
        return Response(content=error_response, status_code=500, media_type='application/xml')

def process_response(response, type):
    response = ResponseModel(**response)
    if type == 'rest':
        return process_rest_response(response)
    elif type == 'soap':
        return process_soap_response(response)
    elif type == 'graphql':
        try:
            strict = os.getenv('STRICT_RESPONSE_ENVELOPE', 'false').lower() == 'true'
            if response.status_code == 200:
                content = response.response if not strict else _envelope({'response': response.response}, response.status_code)
                code = response.status_code if not strict else 200
                resp = JSONResponse(content=content, status_code=code, headers=_normalize_headers(response.response_headers))
                try:
                    blen = len(getattr(resp, 'body', b'') or b'')
                    if blen > 0:
                        resp.headers['Content-Length'] = str(blen)
                        resp.headers['X-Body-Length'] = str(blen)
                except Exception:
                    pass
                return resp
            else:
                content = {'error_code': response.error_code, 'error_message': response.error_message}
                if strict:
                    content = _envelope(content, response.status_code)
                code = response.status_code if not strict else 200
                resp = JSONResponse(content=content, status_code=code, headers=_normalize_headers(response.response_headers))
                try:
                    blen = len(getattr(resp, 'body', b'') or b'')
                    if blen > 0:
                        resp.headers['Content-Length'] = str(blen)
                        resp.headers['X-Body-Length'] = str(blen)
                except Exception:
                    pass
                return resp
        except Exception as e:
            logger.error(f'An error occurred while processing the GraphQL response: {e}')
            return JSONResponse(content={'error': 'Unable to process GraphQL response'}, status_code=500)
    elif type == 'grpc':
        try:
            strict = os.getenv('STRICT_RESPONSE_ENVELOPE', 'false').lower() == 'true'
            if response.status_code == 200:
                content = response.response if not strict else _envelope({'response': response.response}, response.status_code)
                code = response.status_code if not strict else 200
                return JSONResponse(content=content, status_code=code, headers=_normalize_headers(response.response_headers))
            else:
                content = {'error_code': response.error_code, 'error_message': response.error_message}
                if strict:
                    content = _envelope(content, response.status_code)
                code = response.status_code if not strict else 200
                return JSONResponse(content=content, status_code=code, headers=_normalize_headers(response.response_headers))
        except Exception as e:
            logger.error(f'An error occurred while processing the gRPC response: {e}')
            return JSONResponse(content={'error': 'Unable to process gRPC response'}, status_code=500)
    else:
        logger.error(f'Unhandled response type: {type}')
        return JSONResponse(content={'error': 'Unhandled response type'}, status_code=500)
