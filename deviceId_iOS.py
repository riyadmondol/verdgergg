from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

import base64
import time
import struct
import deviceId_iOS_helper

def aes_gcm_encrypt(key: bytes, iv: bytes, data: bytes):
    encryptor = Cipher(
        algorithms.AES(key),
        modes.GCM(iv),
        backend=default_backend()
    ).encryptor()

    ciphertext = encryptor.update(data) + encryptor.finalize()

    return (ciphertext, encryptor.tag)

def aes_gcm_decrypt(key: bytes, iv: bytes, data: bytes, tag: bytes):
    decryptor = Cipher(
        algorithms.AES(key),
        modes.GCM(iv, tag),
        backend=default_backend()
    ).decryptor()

    plaintext = decryptor.update(data) + decryptor.finalize()

    return plaintext

def generateDeviceToken(appId: str):
    appId = appId.encode()
    KEY, IV, PUB, RAND = deviceId_iOS_helper.rand_key()
    device_cer = deviceId_iOS_helper.get_device_cer()
    now = time.time()

    rawDeviceID = RAND + struct.pack('<dii', now, len(device_cer), len(appId)) + device_cer + appId
    body, tag = aes_gcm_encrypt(KEY, IV, rawDeviceID)
    deviceID = b'\x02\x00\x00\x00' + tag + PUB + RAND + struct.pack('<i', len(body)) + body

    return base64.b64encode(deviceID).decode()

def main():
    ios_device_token = generateDeviceToken('825DDA558L.com.cardify.tinder')
    print(ios_device_token)

if __name__ == '__main__':
    main()

### TODO: check again Apple server
# https://api.development.devicecheck.apple.com/v1/validate_device_token
# https://api.development.devicecheck.apple.com/v1/query_two_bits
# https://api.development.devicecheck.apple.com/v1/update_two_bits
