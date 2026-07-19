#!/usr/bin/env python3
"""Generate a LiveKit access token using the REST API.

Usage:
    python scripts/generate_token.py --room intermediary-room --identity user1
    
This avoids SDK version issues by using the HTTP API directly.
"""

import argparse
import json
import time
import urllib.request
import urllib.error
import hashlib
import hmac
import base64


def generate_token(api_key, api_secret, room, identity, ttl=3600):
    """Generate a LiveKit JWT token manually.
    
    This uses the same algorithm as the SDK but without SDK dependencies.
    """
    # Create header
    header = {"alg": "HS256", "typ": "JWT"}
    
    # Create payload
    now = int(time.time())
    payload = {
        "iss": api_key,
        "sub": identity,
        "nbf": now,
        "exp": now + ttl,
        "video": {
            "room": room,
            "roomJoin": True,
            "canPublish": True,
            "canSubscribe": True,
        }
    }
    
    # Encode
    def b64url(data):
        return base64.urlsafe_b64encode(json.dumps(data, separators=(',', ':')).encode()).rstrip(b'=')
    
    segments = b64url(header) + b'.' + b64url(payload)
    
    # Sign
    sig = hmac.new(api_secret.encode(), segments, hashlib.sha256).digest()
    token = segments + b'.' + base64.urlsafe_b64encode(sig).rstrip(b'=')
    
    return token.decode()


def main():
    parser = argparse.ArgumentParser(description="Generate LiveKit token")
    parser.add_argument("--room", default="intermediary-room")
    parser.add_argument("--identity", default="user1")
    parser.add_argument("--ttl", type=int, default=3600)
    parser.add_argument("--key", default="devkey")
    parser.add_argument("--secret", default="secret")
    args = parser.parse_args()
    
    token = generate_token(args.key, args.secret, args.room, args.identity, args.ttl)
    print(f"Room: {args.room}")
    print(f"Identity: {args.identity}")
    print(f"Token: {token}")


if __name__ == "__main__":
    main()
