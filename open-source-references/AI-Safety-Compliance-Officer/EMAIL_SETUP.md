# 📧 Email Setup Guide - AI Safety Compliance Officer

## Quick Setup (5 minutes)

### Step 1: Get Gmail App Password

**⚠️ IMPORTANT: You MUST use an App Password for Gmail (not your regular password)**

1. **Enable 2-Step Verification:**
   - Go to: https://myaccount.google.com/security
   - Find "2-Step Verification" and turn it ON
   - Follow the setup wizard

2. **Generate App Password:**
   - Go to: https://myaccount.google.com/apppasswords
   - Select app: "Mail"
   - Select device: "Windows Computer"
   - Click "Generate"
   - **Copy the 16-character password** (e.g., `abcd efgh ijkl mnop`)

### Step 2: Configure .env File

Open the `.env` file in this directory and fill in:

```env
# Email Configuration
EMAIL_SENDER=your_email@gmail.com
EMAIL_PASSWORD=abcdefghijklmnop
EMAIL_RECIPIENTS=manager1@company.com,manager2@company.com
```

**Notes:**
- `EMAIL_SENDER`: Your Gmail address
- `EMAIL_PASSWORD`: The 16-character App Password (remove spaces)
- `EMAIL_RECIPIENTS`: Comma-separated list of recipients

### Step 3: Test Email Configuration

Run the test script:
```powershell
python test_email.py
```

This will:
- ✅ Check if .env file exists
- ✅ Validate credentials
- ✅ Test SMTP connection
- ✅ Send a test email

### Step 4: Verify Test Email

Check your inbox (and spam folder) for the test email.

---

## Using Other Email Providers

### Outlook / Office 365

```env
EMAIL_SENDER=your_email@outlook.com
EMAIL_PASSWORD=your_password
```

Update `config.py`:
```python
SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587
```

### Yahoo Mail

```env
EMAIL_SENDER=your_email@yahoo.com
EMAIL_PASSWORD=your_app_password
```

Update `config.py`:
```python
SMTP_SERVER = "smtp.mail.yahoo.com"
SMTP_PORT = 587
```

Generate Yahoo App Password: https://login.yahoo.com/account/security

### Custom SMTP Server

```env
EMAIL_SENDER=your_email@company.com
EMAIL_PASSWORD=your_password
```

Update `config.py`:
```python
SMTP_SERVER = "smtp.your-company.com"
SMTP_PORT = 587  # or 465 for SSL
```

---

## Troubleshooting

### Error: "Authentication failed"

**Cause:** Wrong credentials or not using App Password

**Fix:**
1. Make sure you're using App Password (not regular password)
2. Remove spaces from App Password: `abcd efgh ijkl mnop` → `abcdefghijklmnop`
3. Verify 2-Step Verification is enabled

### Error: "Connection refused"

**Cause:** Firewall or network blocking SMTP

**Fix:**
1. Check internet connection
2. Try different network (maybe your company blocks SMTP)
3. Check antivirus/firewall settings

### Error: "SMTP AUTH extension not supported"

**Cause:** Wrong SMTP server or port

**Fix:**
- Gmail: `smtp.gmail.com:587`
- Outlook: `smtp.office365.com:587`

### Emails go to spam

**Fix:**
1. Add sender to contacts
2. Mark first email as "Not Spam"
3. Set up SPF/DKIM records (for production)

### No error but email not received

**Fix:**
1. Check spam folder
2. Verify recipient email is correct
3. Check email provider logs
4. Try sending to different email

---

## Email Features in System

### 1. Violation Alerts

When a safety violation is detected:
- **Subject:** 🚨 URGENT: Safety Violation Detected - [Type]
- **Attachments:** PDF report with photos
- **Body:** Violation details, OSHA regulations, recommendations

### 2. Daily Summary Reports

End of day report:
- **Subject:** Daily Safety Summary - [Count] Violations
- **Attachments:** Summary PDF
- **Body:** Statistics and trends

### 3. Testing Without Email

To test the system without email:

Edit `config.py`:
```python
EMAIL_ENABLED = False
```

Reports will still be generated as PDFs in the `reports/` folder.

---

## Email Configuration Reference

### Complete .env Example

```env
# OpenAI API Key
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx

# Email Configuration (Gmail)
EMAIL_SENDER=safety.officer@gmail.com
EMAIL_PASSWORD=abcdefghijklmnop
EMAIL_RECIPIENTS=manager@company.com,safety@company.com,admin@company.com

# Site Info
SITE_NAME=Downtown Construction Site
COMPANY_NAME=ABC Construction Inc
```

### config.py Email Settings

```python
# Enable/disable email
EMAIL_ENABLED = True

# SMTP Configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Email credentials (loaded from .env)
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECIPIENTS = os.getenv("EMAIL_RECIPIENTS", "").split(",")
```

---

## Security Best Practices

### ✅ DO:
- Use App Passwords for Gmail
- Keep .env file private (it's in .gitignore)
- Use separate email for system notifications
- Enable 2-Step Verification
- Rotate App Passwords periodically

### ❌ DON'T:
- Commit .env file to git
- Share your App Password
- Use your personal email password
- Disable 2-Step Verification
- Email sensitive data without encryption

---

## Need Help?

### Test Email Configuration
```powershell
python test_email.py
```

### Check Email Logs
The system prints detailed logs:
- ✅ Connection successful
- ✅ Email sent
- ❌ Error details

### Common Questions

**Q: Can I use multiple recipients?**  
A: Yes! Separate with commas: `email1@example.com,email2@example.com`

**Q: How often are emails sent?**  
A: Immediately when violation detected (with 5-minute cooldown per violation type)

**Q: Can I disable emails temporarily?**  
A: Yes, set `EMAIL_ENABLED = False` in `config.py`

**Q: What if I don't have a Gmail account?**  
A: Use any SMTP provider (Outlook, Yahoo, custom server)

**Q: Are attachments included?**  
A: Yes! PDF reports with violation photos are attached

---

## Quick Test Command

Test everything in one command:

```powershell
python test_email.py
```

Expected output:
```
✅ .env file exists
✅ EMAIL_SENDER: your_email@gmail.com
✅ EMAIL_PASSWORD: ****************
✅ EMAIL_RECIPIENTS: manager@company.com
✅ Connected to SMTP server
✅ TLS started
✅ Login successful!
✅ Test email sent
```

---

**That's it! Once configured, the system will automatically send emails when violations are detected. 🎉**
