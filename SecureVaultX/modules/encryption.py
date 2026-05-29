"""
Encryption module for SecureVaultX
Handles file encryption and decryption operations
"""

from cryptography.fernet import Fernet
import os

KEY_FILE = "secret.key"


def generate_key():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()

        with open(KEY_FILE, "wb") as file:
            file.write(key)


def load_key():
    return open(KEY_FILE, "rb").read()


generate_key()


def encrypt_file(file_path):

    key = load_key()
    cipher = Fernet(key)

    with open(file_path, "rb") as file:
        data = file.read()

    encrypted_data = cipher.encrypt(data)

    filename = os.path.basename(file_path)

    encrypted_path = os.path.join(
        "encrypted",
        filename + ".enc"
    )

    with open(encrypted_path, "wb") as file:
        file.write(encrypted_data)

    return encrypted_path


def decrypt_file(encrypted_path):

    key = load_key()
    cipher = Fernet(key)

    with open(encrypted_path, "rb") as file:
        encrypted_data = file.read()

    decrypted_data = cipher.decrypt(encrypted_data)

    filename = os.path.basename(encrypted_path)
    filename = filename.replace(".enc", "")

    output_path = os.path.join(
        "decrypted",
        filename
    )

    with open(output_path, "wb") as file:
        file.write(decrypted_data)

    return output_path
