"""Shared password hashing; importing this module does not start or configure the app."""
import hashlib
import hmac
import secrets

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return "$".join(("scrypt", "16384", "8", "1", salt, digest))

def valid_hash(encoded):
    try:
        algorithm, n, r, p, salt, digest = encoded.split("$")
        return (algorithm, n, r, p) == ("scrypt", "16384", "8", "1") and len(bytes.fromhex(salt)) == 16 and len(bytes.fromhex(digest)) == 64
    except (ValueError, AttributeError):
        return False

def password_matches(password, encoded):
    return valid_hash(encoded) and hmac.compare_digest(password_hash(password, encoded.split("$")[4]), encoded)
