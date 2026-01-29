# TP-Link Login Script Notes (RSA Padding / Chunking)

This repo contains scripts that automate login to a TP-Link router UI by reproducing the browser-side crypto flow.

## What the router expects

The login request is a `POST` to `/cgi/login` with **query parameters**:

- `data`: Base64 AES-CBC(PKCS7) of the plaintext `"<username>\n<password>"`
- `sign`: RSA-encrypted signature material derived from the AES key/IV plus a sequence value

The working flow (see `scripts/login_node.js` and `scripts/auto2.py`) is:

1. `GET /cgi/getParm` to obtain `nn`, `ee`, and `seq`
2. Encrypt credentials into `data`
3. Compute `sign_plaintext` similar to:

   `key=<AES_KEY>&iv=<AES_IV>&h=<MD5(username+password)>&s=<seq + len(data)>`

4. `POST /cgi/login?...` and then verify with `GET /cgi/getBusy`

## The unusual RSA behavior ("no padding")

The router’s JavaScript crypto (from `encrypt.js` / `tpEncrypt.js`) uses RSA encryption in a way that differs from standard practice:

- It uses **RSA with no randomized padding** (often referred to as “raw RSA” or “RSA/no padding”).
- The JS implementation performs a **right-zero-pad** of each plaintext block up to the RSA block size.
- If the plaintext is longer than one block, it **chunks** the input and RSA-encrypts each chunk, then concatenates the hex blocks.

In other words, for a 512-bit RSA block size:

- block size is 64 bytes
- each encrypted block is 128 hex characters
- a longer `sign_plaintext` can produce a `sign` of length 256, 384, etc. (multiple blocks)

This is why you can see output like:

- `nn bits: 512`
- but `sign length: 256` (two 512-bit blocks concatenated)

In Python, reproducing this required implementing the same:

- right-zero padding
- chunking
- per-block RSA exponentiation

(see `scripts/tplink_crypto.py`).

## Why this is undesirable (security + protocol brittleness)

From a cryptographic engineering perspective, RSA without randomized padding is generally considered **unsafe and fragile**:

- **Deterministic**: encrypting the same plaintext under the same key yields the same ciphertext.
  This leaks information and enables comparison/replay-style analysis.

- **Malleable**: raw RSA has algebraic structure (multiplicative property).
  Without a secure padding scheme, it is easier to manipulate ciphertexts in ways that produce predictable changes to plaintext.

- **Not CCA-secure**: standard secure RSA encryption in modern protocols uses randomized padding such as:
  - RSA-OAEP (recommended for encryption)
  - or PKCS#1 v1.5 (legacy, still common but has known pitfalls)

- **Protocol brittleness / interop issues**: because this is not a standard padding mode, different implementations frequently disagree on:
  - how to map text bytes into the RSA integer
  - whether to left-pad or right-pad with zeros
  - what block size to use
  - whether/when to chunk

These mismatches are exactly what caused earlier login failures (e.g. router errors like `$.ret=71233/71234`) until the Python implementation matched the JS chunking and padding behavior.

## Practical takeaway

- The implementation here exists to interoperate with a router that already deployed this scheme.
- If you were designing a new authentication protocol, you should **avoid raw RSA** and use standard, well-reviewed constructions (e.g. TLS + OAEP/AEAD where appropriate).
