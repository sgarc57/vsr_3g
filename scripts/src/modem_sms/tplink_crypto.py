import Crypto.Util.number


def rsa_encrypt_nopadding(text, rsa_key, rsa_bits=512, encoding="utf-8"):
    encoded = text.encode(encoding)
    rsa_bytes = (int(rsa_bits) + 7) // 8
    str_en_len = int(rsa_bits) // 4

    if rsa_bytes <= 0 or str_en_len <= 0:
        return None

    out = []
    for start in range(0, len(encoded), rsa_bytes):
        chunk = encoded[start : start + rsa_bytes]
        if len(chunk) > rsa_bytes:
            return None

        ba = bytearray(rsa_bytes)
        ba[: len(chunk)] = chunk
        m = Crypto.Util.number.bytes_to_long(bytes(ba))
        c = pow(m, rsa_key.e, rsa_key.n)
        h = hex(c)[2:]
        if len(h) % 2 != 0:
            h = "0" + h
        out.append(h.zfill(str_en_len))

    return "".join(out)
