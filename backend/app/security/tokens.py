from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt


class TokenError(Exception):
    pass


@dataclass(frozen=True)
class TokenData:
    user_id: int
    email: str
    role: str


def create_token(user_id: int, email: str, role: str, secret: str, expires_min: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=expires_min),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> TokenData:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    return TokenData(user_id=int(payload["sub"]), email=payload["email"],
                     role=payload["role"])
