"""Generate a VAPID key pair for push notifications (see push.py).

    killshot vapid

Prints three lines, ready to paste into .env (or Railway's Variables):
VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY and VAPID_SUBJECT. Run it once -- the same
pair is reused for every subscription, so regenerating it later throws away
everyone's existing subscription (their browser would need to subscribe
again).
"""
import argparse
import base64

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid02


def generate() -> tuple[str, str]:
    """(public key, private key), each as the url-safe base64 string that
    push.py and the browser's Push API expect."""
    v = Vapid02()
    v.generate_keys()
    private = v.private_key.private_numbers().private_value.to_bytes(32, "big")
    public = v.public_key.public_bytes(encoding=serialization.Encoding.X962,
                                       format=serialization.PublicFormat.UncompressedPoint)
    return _b64(public), _b64(private)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def main() -> None:
    ap = argparse.ArgumentParser(prog="killshot vapid", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.parse_args()
    public, private = generate()
    print(f"VAPID_PUBLIC_KEY={public}")
    print(f"VAPID_PRIVATE_KEY={private}")
    print("VAPID_SUBJECT=mailto:you@example.com   # change to a real contact address")


if __name__ == "__main__":
    main()
