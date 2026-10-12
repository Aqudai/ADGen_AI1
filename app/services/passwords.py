"""Хеширование паролей.

Пароль в базе не хранится — только хеш scrypt (стандартная библиотека Python).
scrypt специально медленный и требует много памяти: подбор пароля по украденной базе
становится очень дорогим. Соль — своя для каждого пароля, поэтому одинаковые пароли
дают разные хеши.
"""

import hashlib
import hmac
import secrets

# Параметры scrypt: n — «стоимость» (память и время), r и p — рекомендованные значения
N, R, P = 2**14, 8, 1


def hash_password(password: str) -> str:
    """Возвращает строку «scrypt$соль$хеш» — всё нужное для проверки лежит в одном поле."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algorithm != "scrypt":
        return False
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=N, r=R, p=P)
    # compare_digest сравнивает за одинаковое время — не подсказывает, сколько символов совпало
    return hmac.compare_digest(digest.hex(), digest_hex)
