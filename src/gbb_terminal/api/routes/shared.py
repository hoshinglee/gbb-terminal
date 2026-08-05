from fastapi import HTTPException


def bad_request(error: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(error))

