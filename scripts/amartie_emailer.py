#!/usr/bin/env python3
"""AMARTIE Email Sender — Resend API with browser User-Agent."""

import json, os, urllib.request, ssl

RESEND_KEY_PATH = os.path.expanduser("~/.halo_secrets/resend_full_key.txt")
SENDER = "AMARTIE <oracle@amartie.com>"

def load_key():
    with open(RESEND_KEY_PATH) as f:
        return f.read().strip()

def send_email(to, subject, html_body):
    """Send via Resend API."""
    key = load_key()
    
    data = json.dumps({
        "from": SENDER,
        "to": [to],
        "subject": subject,
        "html": html_body,
    }).encode()
    
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
    )
    
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            result = json.loads(resp.read())
            print(f"  SENT to {to}: {result.get('id','')}")
            return result
    except Exception as e:
        print(f"  FAILED to {to}: {e}")
        return None

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: amartie_emailer.py <to> <subject> <body_html>")
        sys.exit(1)
    
    to = sys.argv[1]
    subject = sys.argv[2]
    body = sys.argv[3]
    
    # If body is a file, read it
    if os.path.exists(body):
        with open(body) as f:
            body = f.read()
    
    send_email(to, subject, body)
