# Brevo Setup Guide

A step-by-step guide to setting up Brevo (formerly Sendinblue) for Agensium email services.

---

## Table of Contents

1. [Account Setup](#1-account-setup)
2. [API Key Generation](#2-api-key-generation)
3. [Sender Configuration](#3-sender-configuration)
4. [Domain Verification](#4-domain-verification)
5. [Environment Configuration](#5-environment-configuration)
6. [Testing Your Setup](#6-testing-your-setup)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Account Setup

### 1.1 Create a Brevo Account

1. Go to [https://www.brevo.com/](https://www.brevo.com/)
2. Click **"Sign up free"**
3. Fill in your details:
   - Email address
   - Password
   - Company name (use "Agensium" or your project name)
4. Verify your email address
5. Complete the onboarding questionnaire

### 1.2 Choose the Right Plan

| Plan       | Daily Emails | Monthly Emails | Price   | Best For            |
| ---------- | ------------ | -------------- | ------- | ------------------- |
| **Free**   | 300          | 9,000          | $0      | Development/Testing |
| Starter    | ~650         | 20,000         | $25/mo  | Small production    |
| Business   | ~3,300       | 100,000        | $65/mo  | Growing apps        |
| Enterprise | Custom       | Custom         | Contact | High volume         |

> 💡 **Recommendation**: Start with the Free plan for development. Upgrade to Starter when going to production.

### 1.3 Account Verification

Brevo requires account verification before you can send emails:

1. **Phone Verification**: Enter your phone number for SMS verification
2. **Identity Verification**: May require additional details for higher sending limits
3. **Business Information**: Complete your company profile

---

## 2. API Key Generation

### 2.1 Generate API Key

1. Log in to your Brevo dashboard
2. Go to **SMTP & API** section (in the left sidebar)
3. Click on **"API Keys"** tab
4. Click **"Generate a new API key"**
5. Name your key (e.g., "Agensium Backend - Production")
6. **Important**: Copy and save the API key immediately - it won't be shown again!

### 2.2 API Key Format

Brevo API keys look like this:

```
xkeysib-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx-xxxxxxxxxxxxxx


```

### 2.3 API Key Security Best Practices

| Do ✅                             | Don't ❌                |
| --------------------------------- | ----------------------- |
| Store in environment variables    | Commit to git           |
| Use different keys for dev/prod   | Share keys publicly     |
| Rotate keys periodically          | Log keys in plain text  |
| Restrict IP access (if available) | Use same key everywhere |

---

## 3. Sender Configuration

### 3.1 Add Sender Email

1. Go to **Senders & IP** in Brevo dashboard
2. Click **"Add a sender"**
3. Enter sender details:
   - **Name**: `Agensium` (or your app name)
   - **Email**: `noreply@agensium.com` (or your domain)
4. Click **"Save"**

### 3.2 Verify Sender Email

For individual sender emails:

1. Brevo sends a verification email
2. Click the verification link in the email
3. Status changes to "Verified"

> ⚠️ **Note**: For production, use domain-level verification instead (see Section 4).

---

## 4. Domain Verification

### 4.1 Why Domain Verification?

- ✅ Higher deliverability rates
- ✅ Professional sender addresses
- ✅ Any email address @yourdomain.com works
- ✅ Better spam score

### 4.2 Add Your Domain

1. Go to **Senders & IP** → **Domains**
2. Click **"Add a domain"**
3. Enter your domain (e.g., `agensium.com`)
4. Click **"Verify this domain"**

### 4.3 DNS Records to Add

Brevo will provide DNS records to add. Example:

#### DKIM Record (Required)

```
Type: TXT
Name: mail._domainkey.agensium.com
Value: k=rsa;p=MIGfMA0GCSq... (long key provided by Brevo)
```

#### SPF Record (Required)

```
Type: TXT
Name: agensium.com
Value: v=spf1 include:sendinblue.com ~all
```

#### DMARC Record (Recommended)

```
Type: TXT
Name: _dmarc.agensium.com
Value: v=DMARC1; p=none; rua=mailto:dmarc@agensium.com
```

### 4.4 Verify DNS Records

1. Add the records to your DNS provider (e.g., Cloudflare, Route53, GoDaddy)
2. Wait for DNS propagation (can take up to 48 hours, usually minutes)
3. Click **"Verify"** in Brevo dashboard
4. Status should change to **"Verified"** ✅

### 4.5 DNS Verification Tools

Use these tools to verify your DNS records:

- [MXToolbox](https://mxtoolbox.com/SPFRecordLookup.aspx) - SPF lookup
- [Mail-Tester](https://www.mail-tester.com/) - Full email test
- [DKIM Validator](https://dkimvalidator.com/) - DKIM check

---

## 5. Environment Configuration

### 5.1 Required Environment Variables

Add these to your `.env` file:

```env
# ============================================================================
# BREVO EMAIL CONFIGURATION
# ============================================================================

# Brevo API Key (get from: https://app.brevo.com/settings/keys/api)
BREVO_API_KEY=xkeysib-your-api-key-here

# Sender configuration
BREVO_SENDER_EMAIL=noreply@agensium.com
BREVO_SENDER_NAME=Agensium

# Feature flags
EMAIL_ENABLED=true
EMAIL_DEBUG=false

# OTP settings
OTP_EXPIRE_MINUTES=10
```

### 5.2 Environment-Specific Settings

#### Development

```env
BREVO_API_KEY=xkeysib-dev-key
EMAIL_ENABLED=true
EMAIL_DEBUG=true  # Logs emails instead of sending
```

#### Staging

```env
BREVO_API_KEY=xkeysib-staging-key
EMAIL_ENABLED=true
EMAIL_DEBUG=false
BREVO_SENDER_EMAIL=staging-noreply@agensium.com
```

#### Production

```env
BREVO_API_KEY=xkeysib-prod-key
EMAIL_ENABLED=true
EMAIL_DEBUG=false
BREVO_SENDER_EMAIL=noreply@agensium.com
```

### 5.3 Update requirements.txt

Add the Brevo SDK:

```txt
# Email - Brevo (Sendinblue)
sib-api-v3-sdk>=7.0.0
```

Install it:

```bash
pip install sib-api-v3-sdk
```

---

## 6. Testing Your Setup

### 6.1 Quick Test Script

Create a test file `test_brevo.py`:

```python
"""
Quick test for Brevo email configuration.
Run: python test_brevo.py
"""
import os
from dotenv import load_dotenv
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

load_dotenv()

def test_brevo_connection():
    """Test Brevo API connection."""
    api_key = os.getenv("BREVO_API_KEY")

    if not api_key:
        print("❌ BREVO_API_KEY not found in environment")
        return False

    print(f"✓ API Key found: {api_key[:20]}...")

    # Configure API
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = api_key

    # Test account info
    api_instance = sib_api_v3_sdk.AccountApi(sib_api_v3_sdk.ApiClient(configuration))

    try:
        account = api_instance.get_account()
        print(f"✓ Connected to Brevo!")
        print(f"  Company: {account.company_name}")
        print(f"  Email: {account.email}")
        print(f"  Plan: {account.plan[0].type if account.plan else 'Unknown'}")
        return True
    except ApiException as e:
        print(f"❌ Failed to connect: {e}")
        return False

def test_send_email(to_email: str):
    """Test sending an email."""
    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("BREVO_SENDER_EMAIL", "noreply@agensium.com")
    sender_name = os.getenv("BREVO_SENDER_NAME", "Agensium")

    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = api_key

    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
        sib_api_v3_sdk.ApiClient(configuration)
    )

    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        sender=sib_api_v3_sdk.SendSmtpEmailSender(
            email=sender_email,
            name=sender_name
        ),
        to=[sib_api_v3_sdk.SendSmtpEmailTo(
            email=to_email,
            name="Test User"
        )],
        subject="🧪 Agensium Test Email",
        html_content="""
        <html>
        <body>
            <h1>Test Email from Agensium</h1>
            <p>If you're reading this, the Brevo integration is working! ✅</p>
        </body>
        </html>
        """
    )

    try:
        response = api_instance.send_transac_email(send_smtp_email)
        print(f"✓ Test email sent!")
        print(f"  Message ID: {response.message_id}")
        return True
    except ApiException as e:
        print(f"❌ Failed to send email: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Brevo Email Configuration Test")
    print("=" * 50)
    print()

    # Test connection
    if test_brevo_connection():
        print()
        # Optionally test sending
        test_email = input("Enter email to send test (or press Enter to skip): ").strip()
        if test_email:
            test_send_email(test_email)

    print()
    print("=" * 50)
```

Run it:

```bash
python test_brevo.py
```

### 6.2 Expected Output

```
==================================================
Brevo Email Configuration Test
==================================================

✓ API Key found: xkeysib-12345678901...
✓ Connected to Brevo!
  Company: Agensium
  Email: admin@agensium.com
  Plan: free

Enter email to send test (or press Enter to skip): test@example.com
✓ Test email sent!
  Message ID: <abc123@mail.brevo.com>

==================================================
```

### 6.3 Verify Email Receipt

1. Check inbox of test email
2. Check spam folder if not in inbox
3. Verify sender name and email match configuration

---

## 7. Troubleshooting

### 7.1 Common Issues

#### API Key Not Working

| Symptom            | Solution                                 |
| ------------------ | ---------------------------------------- |
| 401 Unauthorized   | Check API key is correct and not expired |
| 403 Forbidden      | Verify account is activated              |
| Connection refused | Check network/firewall settings          |

#### Emails Not Delivered

| Symptom             | Solution                             |
| ------------------- | ------------------------------------ |
| Emails in spam      | Verify domain (SPF/DKIM/DMARC)       |
| Sender not verified | Complete sender verification         |
| Rate limit exceeded | Wait for limit reset or upgrade plan |
| Invalid recipient   | Check email address format           |

#### Domain Verification Failed

| Issue                | Solution                                   |
| -------------------- | ------------------------------------------ |
| DNS not propagated   | Wait 24-48 hours, verify with dig/nslookup |
| Wrong record format  | Double-check record values from Brevo      |
| Multiple TXT records | Ensure SPF records are merged correctly    |

### 7.2 Debug Mode

Enable debug mode to log emails without sending:

```env
EMAIL_DEBUG=true
```

In debug mode:

- Emails are logged to console
- No actual emails are sent
- No API quota used
- Great for development

### 7.3 Checking Brevo Logs

1. Go to Brevo dashboard → **Transactional** → **Logs**
2. Filter by date range
3. Check email status:
   - ✅ **Delivered**: Email reached inbox
   - ⚠️ **Soft bounce**: Temporary delivery failure
   - ❌ **Hard bounce**: Permanent delivery failure
   - 📭 **Blocked**: Recipient blocked by Brevo

### 7.4 Rate Limits

| Plan     | Daily Limit | Hourly Limit |
| -------- | ----------- | ------------ |
| Free     | 300         | ~50          |
| Starter  | 650         | ~100         |
| Business | 3,300       | ~500         |

If you hit rate limits:

1. Implement queue/retry mechanism
2. Upgrade plan
3. Request limit increase from Brevo

### 7.5 Getting Help

- **Brevo Documentation**: [https://developers.brevo.com/](https://developers.brevo.com/)
- **API Reference**: [https://developers.brevo.com/reference](https://developers.brevo.com/reference)
- **Brevo Support**: support@brevo.com
- **Community**: [Brevo Community Forum](https://community.brevo.com/)

---

## Quick Reference

### Environment Variables Summary

| Variable             | Required | Default              | Description             |
| -------------------- | -------- | -------------------- | ----------------------- |
| `BREVO_API_KEY`      | ✅ Yes   | -                    | Brevo API key           |
| `BREVO_SENDER_EMAIL` | No       | noreply@agensium.com | Sender email            |
| `BREVO_SENDER_NAME`  | No       | Agensium             | Sender display name     |
| `EMAIL_ENABLED`      | No       | true                 | Enable/disable emails   |
| `EMAIL_DEBUG`        | No       | false                | Debug mode (no sending) |
| `OTP_EXPIRE_MINUTES` | No       | 10                   | OTP validity            |

### Useful Links

| Resource           | URL                                                |
| ------------------ | -------------------------------------------------- |
| Brevo Dashboard    | https://app.brevo.com/                             |
| API Keys           | https://app.brevo.com/settings/keys/api            |
| Sender & IP        | https://app.brevo.com/senders                      |
| Transactional Logs | https://app.brevo.com/campaign/message/logs        |
| Python SDK Docs    | https://github.com/sendinblue/APIv3-python-library |

---

**Setup Status**: Ready for use ✅
