# SecureVault X - Quick Reference Guide

## 🚀 Getting Started

### Installation
```bash
cd SecureVaultX
python -m venv venv
venv\Scripts\activate  # Windows
pip install customtkinter cryptography bcrypt pillow flask requests
python app.py
```

### Default Login
- Create a new account on first run
- Username: Any text (e.g., "john_doe")
- Password: Any secure password (min 6 chars)

---

## 📊 Dashboard Overview

### Main Features (Sidebar)
| Button | Function |
|--------|----------|
| 📊 Dashboard | Overview with statistics |
| 📁 My Files | Manage encrypted files |
| 🛡️ Security | View security status |
| 🚨 Threat Model | Threats & mitigations |
| 📋 Logs | Activity & event logs |
| ⚙️ Settings | App configuration |
| 🚪 Logout | Exit application |

### Dashboard Stats
- **Total Files**: Number of encrypted files
- **Storage Used**: Total disk space consumed
- **Authentication**: ACTIVE (encrypted connections)
- **Security Score**: 0-100 rating

---

## 📁 File Management

### Upload & Encrypt
1. Click **📤 Upload & Encrypt File**
2. Select file from computer
3. Progress bar shows encryption status
4. File automatically uploaded to server
5. Entry appears in "My Files"

### Decrypt & Download
1. Go to **📁 My Files**
2. Find encrypted file in list
3. Click **🔓** button
4. File integrity verified
5. Saved to `decrypted/` folder
6. Notification confirms success

### Verify Integrity
1. In **📁 My Files**
2. Click **✓** button on file
3. HMAC-SHA256 verification runs
4. Result: "Integrity Verified" or warning
5. Tampered files rejected

### Delete File
1. In **📁 My Files**
2. Click **🗑️** button
3. Confirm deletion
4. Removed from server and database
5. Log entry recorded

---

## 🔐 Security Features

### Encryption
- **Type**: AES (via Fernet)
- **Key Size**: 256-bit
- **Mode**: CBC with authentication
- **Chunking**: 5MB chunks (resumable)

### Integrity
- **Method**: HMAC-SHA256
- **Verification**: Before decryption
- **Detection**: Tamper/corruption
- **Storage**: `integrity.json`

### Authentication
- **Method**: bcrypt password hashing
- **Strength**: 12 rounds
- **Database**: SQLite with user isolation

### Transport
- **Protocol**: HTTPS
- **Server**: Local Flask on :5001
- **Certificates**: Auto-generated SSL

---

## 📝 Activity Logging

### Logged Events
- ✓ User Login/Logout
- ✓ File Uploads
- ✓ File Decryptions
- ✓ Integrity Checks
- ✓ File Deletions
- ✓ Key Generation

### View Logs
1. Click **📋 Activity Logs**
2. Logs displayed newest first
3. Search field filters by keyword
4. Full timestamps included

### Clear Logs
1. Go to **⚙️ Settings**
2. Click **🧹 Clear Logs**
3. Confirm deletion
4. Log file reset

---

## ⚠️ Threat Model

### Identified Threats
1. **Man-in-the-Middle (MITM) Attack**
   - Mitigation: TLS/HTTPS encryption

2. **File Tampering**
   - Mitigation: HMAC-SHA256 verification

3. **Unauthorized Access**
   - Mitigation: bcrypt password hashing

4. **Credential Theft**
   - Mitigation: Secure key management

5. **Key Leakage**
   - Mitigation: Encrypted key storage

---

## ⚙️ Settings

### Appearance
- **🌙 Toggle Dark Mode**: Switch theme

### Data Management
- **🧹 Clear Logs**: Remove all activity logs

### Security
- **🔑 Generate New Key**: Create fresh encryption key
  - ⚠️ Warning: Invalidates existing files!
  - Use only if compromised

### About
- Version: 1.0
- Features listed
- License info

---

## 📂 Directory Structure

```
SecureVaultX/
├── app.py                 # Main application
├── app.db                 # User & file database
├── secret.key             # AES encryption key
├── hmac_secret.key        # HMAC verification key
├── integrity.json         # HMAC values per file
├── encrypted/             # Local encrypted files
├── decrypted/             # Downloaded decrypted files
├── server_storage/        # Server-side storage
├── uploads/               # Resume state tracking
│   └── upload_state.json  # Chunk progress
└── logs/
    └── activity.log       # Event log
```

---

## 🐛 Troubleshooting

### App Won't Start
```bash
# Check Python version
python --version  # Need 3.8+

# Reinstall dependencies
pip install --upgrade customtkinter cryptography bcrypt pillow flask requests

# Run with debug
python -u app.py
```

### Server Port Already In Use
- Default port: 5001
- Close other Flask instances
- Check: `netstat -ano | findstr :5001`

### Can't Decrypt File
1. Check **✓** Verify Integrity first
2. Ensure correct encryption key loaded
3. Check logs for errors
4. Try decrypting different file

### Lost Password
- No recovery option by design
- Create new account with new password
- Old files remain encrypted (inaccessible)

---

## 💡 Best Practices

### Security
- ✅ Use strong passwords (12+ chars, mixed)
- ✅ Backup encryption keys externally
- ✅ Verify files before trusting
- ✅ Check threat model regularly
- ✅ Monitor activity logs

### File Management
- ✅ Upload important files frequently
- ✅ Verify integrity of critical files
- ✅ Keep decrypted files temporary
- ✅ Clear logs periodically
- ✅ Test restore process

### System
- ✅ Keep Python updated
- ✅ Install package updates monthly
- ✅ Backup app.db regularly
- ✅ Secure application folder
- ✅ Use on trusted networks

---

## 🔗 Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Q` | (Implemented) Logout |
| `Tab` | Navigate fields |
| `Enter` | Submit forms |

---

## 📞 Support

### Common Issues

**Issue**: Encryption takes too long
- **Cause**: Large files or slow storage
- **Solution**: Normal for large files (5GB = ~30s)

**Issue**: Server error on upload
- **Cause**: Network or disk full
- **Solution**: Check network, free disk space

**Issue**: Integrity verification fails
- **Cause**: File tampered or corrupted
- **Solution**: Verify again, check logs

**Issue**: Can't login after registration
- **Cause**: Typo or database issue
- **Solution**: Re-register with same details

---

## Version History

**v1.0 (Current)**
- ✅ AES encryption
- ✅ HMAC verification
- ✅ Chunked uploads
- ✅ Resume support
- ✅ Client-server architecture
- ✅ Activity logging
- ✅ Threat modeling
- ✅ Professional dashboard

---

**Last Updated**: May 27, 2026  
**Status**: Production Ready
