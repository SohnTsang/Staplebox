from django.core.signing import Signer

signer = Signer()

def sign_uuid(uuid):
    return signer.sign(str(uuid))

def unsign_uuid(uuid):
    try:
        return signer.unsign(uuid)
    except Exception:
        return None