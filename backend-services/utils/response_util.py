from fastapi.responses import JSONResponse, Response
import os
from models.response_model import ResponseModel

import logging
from fastapi.responses import Response

logger = logging.getLogger("doorman.gateway")

def _envelope(content: dict, status_code: int) -> dict:
    return {
        "status_code": status_code,
        **content
    }

def _add_token_compat(enveloped: dict, payload: dict):
    try:
        # Expose tokens at top-level as a compatibility convenience
        if isinstance(payload, dict):
            for key in ("access_token", "refresh_token"):
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
        processed_response = None
        strict = os.getenv("STRICT_RESPONSE_ENVELOPE", "false").lower() == "true"
        if response.status_code == 200:
            # Prefer returning the actual response payload when present.
            # Include message only when no response data is provided.
            if getattr(response, 'response', None) is not None:
                if not strict:
                    processed_response = response.response
                else:
                    processed_response = _envelope({"response": response.response}, response.status_code)
                    # Add access_token/refresh_token at top-level for clients expecting flat payloads
                    _add_token_compat(processed_response, response.response)
            elif response.message:
                processed_response = {"message": response.message} if not strict else _envelope({"message": response.message}, response.status_code)
            else:
                processed_response = None if not strict else _envelope({}, response.status_code)
        elif response.status_code == 201:
            processed_response = {"message": response.message} if not strict else _envelope({"message": response.message}, response.status_code)
        elif response.status_code in (400, 403, 404):
            processed_response = {"error_code": response.error_code, "error_message": response.error_message}
            if strict:
                processed_response = _envelope(processed_response, response.status_code)
        else:
            processed_response = {"message": "An unknown error occurred"}
            if strict:
                processed_response = _envelope(processed_response, response.status_code)
        return JSONResponse(content=processed_response, status_code=response.status_code, headers=response.response_headers)
    except Exception as e:
        logger.error(f"An error occurred while processing the response: {e}")
        return JSONResponse(content={"error": "Unable to process response"}, status_code=500)
    
def process_soap_response(response):
    try:
        strict = os.getenv("STRICT_RESPONSE_ENVELOPE", "false").lower() == "true"
        if response.status_code == 200:
            if getattr(response, 'soap_envelope', None):
                soap_response = response.soap_envelope
            else:
                soap_response = response.response
        elif response.status_code == 201:
            soap_response = f"<message>{response.message}</message>"
        elif response.status_code in (400, 403, 404):
            soap_response = (
                f"<error>"
                f"<error_code>{response.error_code}</error_code>"
                f"<error_message>{response.error_message}</error_message>"
                f"</error>"
            )
        else:
            soap_response = "<message>An unknown error occurred in SOAP response</message>"

        return Response(
            content=soap_response,
            status_code=response.status_code,
            media_type="application/xml",
            headers=response.response_headers,
        )
    except Exception as e:
        logger.error(f"An error occurred while processing the SOAP response: {e}")
        error_response = "<error>Unable to process SOAP response</error>"
        return Response(content=error_response, status_code=500, media_type="application/xml")
    
def process_response(response, type):
    response = ResponseModel(**response)
    if type == "rest":
        return process_rest_response(response)
    elif type == "soap":
        return process_soap_response(response)
    elif type == "graphql":
        try:
            strict = os.getenv("STRICT_RESPONSE_ENVELOPE", "false").lower() == "true"
            if response.status_code == 200:
                content = response.response if not strict else _envelope({"response": response.response}, response.status_code)
                return JSONResponse(content=content, status_code=response.status_code, headers=response.response_headers)
            else:
                content = {"error_code": response.error_code, "error_message": response.error_message}
                if strict:
                    content = _envelope(content, response.status_code)
                return JSONResponse(content=content, status_code=response.status_code, headers=response.response_headers)
        except Exception as e:
            logger.error(f"An error occurred while processing the GraphQL response: {e}")
            return JSONResponse(content={"error": "Unable to process GraphQL response"}, status_code=500)
    elif type == "grpc":
        try:
            strict = os.getenv("STRICT_RESPONSE_ENVELOPE", "false").lower() == "true"
            if response.status_code == 200:
                content = response.response if not strict else _envelope({"response": response.response}, response.status_code)
                return JSONResponse(content=content, status_code=response.status_code, headers=response.response_headers)
            else:
                content = {"error_code": response.error_code, "error_message": response.error_message}
                if strict:
                    content = _envelope(content, response.status_code)
                return JSONResponse(content=content, status_code=response.status_code, headers=response.response_headers)
        except Exception as e:
            logger.error(f"An error occurred while processing the gRPC response: {e}")
            return JSONResponse(content={"error": "Unable to process gRPC response"}, status_code=500)
    else:
        logger.error(f"Unhandled response type: {type}")
        return JSONResponse(content={"error": "Unhandled response type"}, status_code=500)
