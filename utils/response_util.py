from fastapi.responses import JSONResponse, Response
from models.response_model import ResponseModel

import logging
from fastapi.responses import Response

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("doorman.gateway")

def process_rest_response(response):
    try:
        processed_response = None
        if response.status_code == 200:
            if response.message:
                processed_response = {
                    "message": response.message
                    }
            else:
                processed_response = response.response
        elif response.status_code == 201:
            processed_response = {
                "message": response.message
                }
        elif response.status_code in (400, 403, 404):
            processed_response = {
                "error_code": response.error_code,
                "error_message": response.error_message
            }
        else:
            processed_response = {
                "message": "An unknown error occurred"
            }
        return JSONResponse(content=processed_response, status_code=response.status_code, headers=response.response_headers)
    except Exception as e:
        logger.error(f"An error occurred while processing the response: {e}")
        return JSONResponse(content={"error": "Unable to process response"}, status_code=500)
    
def process_soap_response(response):
    try:
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
            if response.status_code == 200:
                return JSONResponse(
                    content=response.response,
                    status_code=response.status_code,
                    headers=response.response_headers
                )
            else:
                return JSONResponse(
                    content={
                        "error_code": response.error_code,
                        "error_message": response.error_message
                    },
                    status_code=response.status_code,
                    headers=response.response_headers
                )
        except Exception as e:
            logger.error(f"An error occurred while processing the GraphQL response: {e}")
            return JSONResponse(content={"error": "Unable to process GraphQL response"}, status_code=500)
    else:
        logger.error(f"Unhandled response type: {type}")
        return JSONResponse(content={"error": "Unhandled response type"}, status_code=500)