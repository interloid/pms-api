import hashlib

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()


def hash_passcode(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _password_hash.verify(plain_password, hashed_password)

