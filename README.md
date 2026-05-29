# 🔐 SecureVault X

### Enterprise-Grade Secure File Storage & Retrieval Platform

SecureVault X is a cybersecurity-focused desktop application designed to provide secure file storage, encrypted transfer, integrity verification, and safe retrieval of sensitive data.

Built using Python and modern security principles, the platform combines encryption, authentication, logging, and threat modeling into a single enterprise-inspired solution.

---

## 🚀 Features

### 🔒 Security Features

* AES/Fernet File Encryption
* HMAC-SHA256 Integrity Verification
* Secure User Authentication (bcrypt)
* HTTPS/TLS-Based Communication
* Threat Model & Mitigation Dashboard
* Secure Key Management

### 📁 File Management

* Secure File Upload
* Encrypted File Storage
* Secure File Retrieval
* File Decryption
* Chunked Upload Support
* Resume Interrupted Uploads
* File Deletion & Management

### 📊 Monitoring & Analytics

* Activity Logging
* Security Dashboard
* Storage Statistics
* Security Status Monitoring
* Threat Analysis Panel

### 🎨 User Experience

* Modern Cybersecurity Dashboard
* Dark Enterprise UI
* Responsive Layout
* Professional Sidebar Navigation
* Real-Time Status Indicators

---

## 🛠️ Technology Stack

| Technology    | Purpose                |
| ------------- | ---------------------- |
| Python        | Core Development       |
| CustomTkinter | Modern GUI             |
| Flask         | Secure Local Server    |
| SQLite        | Database               |
| Cryptography  | Encryption             |
| bcrypt        | Password Hashing       |
| HMAC-SHA256   | Integrity Verification |

---

## 📸 Application Screenshots
<img width="1910" height="1009" alt="Screenshot 2026-05-29 205040" src="https://github.com/user-attachments/assets/bb63b7aa-27cf-4fd9-9ed9-c218e8597890" />


### Dashboard

<img width="1916" height="1078" alt="Screenshot 2026-05-29 205053" src="https://github.com/user-attachments/assets/acaad507-94d6-4297-bc6a-d7935cc14655" />


### My Files

<img width="1910" height="1011" alt="Screenshot 2026-05-29 205541" src="https://github.com/user-attachments/assets/19b020b0-5c26-48cf-b5f1-d5e3c9d80378" />


### Security Center

<img width="1905" height="1009" alt="Screenshot 2026-05-29 205555" src="https://github.com/user-attachments/assets/7c663382-3383-4108-b4de-9f2521b25fb2" />

### Threat Model

<img width="1919" height="1014" alt="Screenshot 2026-05-29 205624" src="https://github.com/user-attachments/assets/cc5f0309-7d98-450b-820e-66751423bda2" />


### Activity Logs
<img width="1905" height="1027" alt="Screenshot 2026-05-29 205609" src="https://github.com/user-attachments/assets/71e6dec7-1e9a-428c-8b42-9a972357a801" />




## 🔐 Security Architecture

### Encryption

Files are encrypted before storage using Fernet encryption (AES-128-CBC + HMAC), ensuring confidentiality and protection against unauthorized access.

### Integrity Verification

HMAC-SHA256 is used to verify file integrity and detect any unauthorized modifications or tampering.

### Authentication

User credentials are protected using bcrypt password hashing.

### Secure Storage

Files remain encrypted while stored and are only decrypted during authorized retrieval operations.

---

## ⚠️ Threat Model & Mitigation

| Threat                   | Mitigation                     |
| ------------------------ | ------------------------------ |
| Man-in-the-Middle Attack | HTTPS/TLS Communication        |
| Unauthorized Access      | Authentication & Authorization |
| File Tampering           | HMAC Integrity Verification    |
| Credential Theft         | bcrypt Password Hashing        |
| Key Leakage              | Secure Key Management          |

---

## 📂 Project Structure

```text
SecureVaultX/
│
├── app.py
├── database/
├── encrypted/
├── decrypted/
├── uploads/
├── logs/
├── server_storage/
├── integrity.json
└── secret.key
```

---

## ▶️ Installation

### Clone Repository

```bash
git clone https://github.com/Hamsa24-am/SyntecxHub_SecureVaultX.git
cd SyntecxHub_SecureVaultX
```

### Install Dependencies

```bash
pip install customtkinter cryptography bcrypt flask requests pillow
```

### Run Application

```bash
python app.py
```

---

## 🎯 Learning Outcomes

This project helped develop practical skills in:

* Secure Software Development
* Encryption & Cryptography
* Authentication Systems
* Integrity Verification
* Secure File Transfer
* Cybersecurity Best Practices
* Python Application Development

---



## 📜 License

This project is licensed under the MIT License.
