#!/usr/bin/env python3
"""
AMARTIE — Solana Wallet Generator
Generates a new Solana keypair for receiving R&D donations.
"""

import json
import hashlib
import base58
import os


def generate_wallet():
    """Generate a new Ed25519 keypair in Solana format."""
    # Generate 32 random bytes for private key
    private_bytes = os.urandom(32)
    # Ed25519 public key is derived from private key (32 bytes)
    # Simplified: use a hash for demo (in production: use nacl or solana-py)
    public_bytes = hashlib.sha512(private_bytes).digest()[:32]
    # Full keypair: 64 bytes [private(32) + public(32)]
    keypair_bytes = list(private_bytes) + list(public_bytes)
    return {
        "public_key": base58.b58encode(public_bytes).decode("utf-8"),
        "private_key": base58.b58encode(private_bytes).decode("utf-8"),
        "keypair_bytes": keypair_bytes,
        "warning": "DEMO KEYPAIR - Replace with real Ed25519 from solana-keygen or similar for production use"
    }


def main():
    print("=" * 60)
    print("AMARTIE — Solana Wallet Generator")
    print("=" * 60)
    print()

    wallet = generate_wallet()

    print(f"Public Address:  {wallet['public_key']}")
    print(f"Private Key:     {wallet['private_key'][:20]}...")
    print()

    # Save to file
    output_path = os.path.join(os.path.dirname(__file__), "..", "wallet.json")
    with open(output_path, "w") as f:
        json.dump(wallet, f, indent=2)

    print(f"Wallet saved to: {output_path}")
    print()
    print("=" * 60)
    print("IMPORTANT:")
    print("1. Move wallet.json to a SECURE location")
    print("2. Never commit wallet.json to git")
    print("3. Anyone with the private key controls the funds")
    print("=" * 60)
    print()
    print("To create a PRODUCTION wallet, install Solana CLI:")
    print("  curl -sSfL https://release.solana.com/v1.17.0/install | sh")
    print("  solana-keygen new --outfile ~/.config/solana/amartie.json")
    print("  solana-keygen pubkey ~/.config/solana/amartie.json")
    print("Then paste the public address into README.md")
    print("=" * 60)


if __name__ == "__main__":
    main()
