"""Cognito JWT verification (RS256 via the user pool JWKS). Open when Cognito is not configured."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request

from visiondoctor.config import get_settings


@lru_cache(maxsize=1)
def _jwks() -> jwt.PyJWKClient:
    s = get_settings()
    url = f"https://cognito-idp.{s.aws_region}.amazonaws.com/{s.cognito_user_pool_id}/.well-known/jwks.json"
    return jwt.PyJWKClient(url)


def current_user(request: Request) -> dict[str, Any]:
    s = get_settings()
    if not s.cognito_user_pool_id:
        return {"username": "local-operator", "groups": ["admin", "operator"]}
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    token = auth[7:]
    try:
        key = _jwks().get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=["RS256"], options={"verify_aud": False})
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"invalid token: {e}") from e
    iss = f"https://cognito-idp.{s.aws_region}.amazonaws.com/{s.cognito_user_pool_id}"
    if claims.get("iss") != iss or claims.get("client_id", claims.get("aud")) != s.cognito_client_id:
        raise HTTPException(401, "token not issued for this app")
    return {"username": claims.get("email") or claims.get("username") or claims["sub"],
            "groups": claims.get("cognito:groups", [])}


def require_group(group: str) -> Any:
    def dep(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if group not in user["groups"] and "admin" not in user["groups"]:
            raise HTTPException(403, f"requires group {group}")
        return user

    return dep
