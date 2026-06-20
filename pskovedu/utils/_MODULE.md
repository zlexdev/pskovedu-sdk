# utils/

Internal helpers with no domain knowledge.

## jwt.py

Base64url decode of JWT header and payload — no signature verification.
The portal uses HS256 (symmetric); we don't have the server secret.

```python
decode_header(token: str) -> dict[str, Any]   # {"alg": "HS256", "typ": "JWT"}
decode_payload(token: str) -> dict[str, Any]  # {"sessionId": ..., "exp": ..., "iat": ..., "jti": ...}
```

Raises `ValueError` on malformed input.

## url_encode.py

GUID / UUID validators and query-string encoding.

```python
validate_guid(value: str) -> str   # 30–40 hex chars, optional {} braces
validate_uuid(value: str) -> str   # RFC 4122 UUID
encode_query(params: dict) -> str  # URL query string, None values omitted
```

`Guid` and `Uuid` annotated types in `models/common.py` use these as
`AfterValidator` callbacks, so validation fires at Pydantic parse time.
