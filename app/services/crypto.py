from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class CryptoConfigError(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = settings.JIRA_ENCRYPTION_KEY
    if not key:
        raise CryptoConfigError(
            "JIRA_ENCRYPTION_KEY no configurada. Generala con: "
            "python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise CryptoConfigError(f"JIRA_ENCRYPTION_KEY inválida: {exc}") from exc


def encrypt_token(plain: str) -> bytes:
    return _fernet().encrypt(plain.encode("utf-8"))


def decrypt_token(blob: bytes) -> str:
    try:
        return _fernet().decrypt(blob).decode("utf-8")
    except InvalidToken as exc:
        raise CryptoConfigError("Token cifrado inválido o clave incorrecta") from exc
