import hashlib
import secrets

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()


def generate_passcode() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_passcode(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def verify_passcode(plain_passcode: str, hashed_passcode: str) -> bool:
    hashed_input = hashlib.sha256(plain_passcode.encode("utf-8")).hexdigest()

    return secrets.compare_digest(
        hashed_input,
        hashed_passcode,
    )


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _password_hash.verify(plain_password, hashed_password)
