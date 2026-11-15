import hmac

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

bearer = HTTPBearer(auto_error=False, scheme_name="AYE local bearer token")


def require_api_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    expected = get_settings().api_token
    if not expected or len(expected) < 32:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="API access token is not configured (set AYE_API_TOKEN to at least 32 characters)")
    if credentials is None or credentials.scheme.lower() != "bearer" or not hmac.compare_digest(
        credentials.credentials.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing bearer token",
                            headers={"WWW-Authenticate": "Bearer"})
    return "local-owner"
