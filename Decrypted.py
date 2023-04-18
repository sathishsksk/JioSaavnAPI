import base64
import pyDes

def decrypt_url(url):
    key = b"38346591"
    des_cipher = pyDes.des(key, pyDes.ECB, padmode=pyDes.PAD_PKCS5)
    enc_url = base64.b64decode(url.strip())
    dec_url = des_cipher.decrypt(enc_url)
    dec_url = dec_url.decode('utf-8')
    dec_url = dec_url.replace("_96.mp4", "_320.mp4")
    return dec_url
  
  decrypted_url = decrypt_url("ID2ieOjCrwfgWvL5sXl4B1ImC5QfbsDyFNsfQCO91T0dC9btMN5x/FlZmbA/MpEGc30F7gTMuUdelA8wZuh/oRw7tS9a8Gtq")
  print(decrypted_url)


