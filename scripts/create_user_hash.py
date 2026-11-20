"""Generate a scrypt hash for LIVECAST_USERS_JSON. Do not commit passwords.

Usage: python scripts/create_user_hash.py
Paste returned hash into Render's secret environment variable for a named user.
"""
import hashlib
import secrets
import getpass
password=getpass.getpass('New password (16+ characters): ')
if len(password)<16:raise SystemExit('Use at least 16 characters')
salt=secrets.token_bytes(16)
result=hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1).hex()
print('scrypt$16384$8$1$'+salt.hex()+'$'+result)
