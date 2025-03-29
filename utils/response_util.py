from fastapi.responses import JSONResponse
from models.response_model import ResponseModel

import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

def process_resposnse(response):
    """
    Process the response from the API.
    """
    response = ResponseModel(**response)
    try:
        processed_response = None
        if response.status_code == 200:
            processed_response = response.response
        elif response.status_code == 201:
            processed_response = {"message": response.message}
        elif response.status_code == 400:
            processed_response = {
                "code": response.error_code,
                "message": response.error_message
            }
        else:
            processed_response = {
                "message": "An unknown error occurred"
            }
        return JSONResponse(content=processed_response, status_code=response.status_code)
    except Exception as e:
        logger.error(f"An error occurred while processing the response: {e}")
        return JSONResponse(content={"error": "Unable to process response"}, status_code=500)