from passlib.context import CryptContext

# argon2 is the current recommended password hash
_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _context.verify(plain, hashed)
