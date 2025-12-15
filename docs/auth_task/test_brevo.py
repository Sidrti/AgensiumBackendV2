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
