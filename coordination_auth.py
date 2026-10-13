"""Stockage local du mot de passe coordinateur, sous forme dérivée."""
import hashlib
import hmac
import json
import os
import secrets
import tempfile


def verify_coordinateur(path, password, initial_password):
    if not path.exists():
        return hmac.compare_digest(password.encode(), initial_password.encode())
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        salt=bytes.fromhex(data['salt'])
        expected=bytes.fromhex(data['hash'])
        if data['version']!=1 or len(salt)!=16 or len(expected)!=32:
            raise ValueError('Format invalide')
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError('Le fichier du compte coordinateur est invalide. Contactez l’administrateur.') from exc
    actual=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,200000)
    return hmac.compare_digest(actual,expected)


def save_coordinateur_password(path,password):
    if not password:
        raise ValueError('Le nouveau mot de passe ne peut pas être vide.')
    salt=secrets.token_bytes(16)
    data={'version':1,'salt':salt.hex(),'hash':hashlib.pbkdf2_hmac('sha256',password.encode(),salt,200000).hex()}
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as file:
            temporary=file.name
            json.dump(data,file)
        os.replace(temporary,path)
    finally:
        if temporary and os.path.exists(temporary):os.unlink(temporary)
