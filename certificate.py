from OpenSSL import crypto


def generate_certificate():
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 4096)
    cert = crypto.X509()
    cert.get_subject().CN = "Gozargah"
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(100*365*24*60*60)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha512')
    cert_pem = crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8")
    key_pem = crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8")

    return {
        "cert": cert_pem,
        "key": key_pem
    }
