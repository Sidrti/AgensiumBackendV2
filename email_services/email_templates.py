"""
HTML email templates for Agensium.
Professional, responsive email templates for authentication flows.
"""
import json


def get_otp_template(
    user_name: str,
    otp_code: str,
    otp_type: str,
    expiry_minutes: int
) -> str:
    """
    Generate HTML template for OTP emails.

    Args:
        user_name: User's full name
        otp_code: 6-digit OTP code
        otp_type: 'registration' or 'password_reset'
        expiry_minutes: OTP validity in minutes

    Returns:
        HTML string
    """
    if otp_type == "registration":
        title = "Verify Your Email"
        message = "Thank you for registering with Agensium! Please use the following OTP to verify your email address:"
        action_text = "verify your email"
    else:
        title = "Reset Your Password"
        message = "We received a request to reset your password. Please use the following OTP to proceed:"
        action_text = "reset your password"

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f7;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 0;">
                <table role="presentation" style="width: 100%; max-width: 600px; border-collapse: collapse; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 600;">
                                Agensium
                            </h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <h2 style="margin: 0 0 20px; color: #333333; font-size: 24px; font-weight: 600;">
                                {title}
                            </h2>
                            
                            <p style="margin: 0 0 20px; color: #666666; font-size: 16px; line-height: 1.6;">
                                Hi {user_name},
                            </p>
                            
                            <p style="margin: 0 0 30px; color: #666666; font-size: 16px; line-height: 1.6;">
                                {message}
                            </p>

                            <!-- OTP Code Box -->
                            <div style="background-color: #f8f9fa; border: 2px dashed #667eea; border-radius: 8px; padding: 30px; text-align: center; margin: 0 0 30px;">
                                <p style="margin: 0 0 10px; color: #666666; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">
                                    Your OTP Code
                                </p>
                                <p style="margin: 0; color: #333333; font-size: 36px; font-weight: 700; letter-spacing: 8px; font-family: 'Courier New', monospace;">
                                    {otp_code}
                                </p>
                            </div>

                            <p style="margin: 0 0 20px; color: #999999; font-size: 14px; line-height: 1.6;">
                                ⏱️ This code will expire in <strong>{expiry_minutes} minutes</strong>.
                            </p>

                            <p style="margin: 0; color: #999999; font-size: 14px; line-height: 1.6;">
                                If you didn't request to {action_text}, please ignore this email or contact support if you have concerns.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px; background-color: #f8f9fa; border-radius: 0 0 8px 8px; text-align: center;">
                            <p style="margin: 0 0 10px; color: #999999; font-size: 12px;">
                                © 2025 Agensium. All rights reserved.
                            </p>
                            <p style="margin: 0; color: #999999; font-size: 12px;">
                                Need help? Contact us at 
                                <a href="mailto:support@agensium.com" style="color: #667eea; text-decoration: none;">support@agensium.com</a>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def get_welcome_template(user_name: str) -> str:
    """
    Generate HTML template for welcome email.

    Args:
        user_name: User's full name

    Returns:
        HTML string
    """
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to Agensium</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f7;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 0;">
                <table role="presentation" style="width: 100%; max-width: 600px; border-collapse: collapse; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 600;">
                                🎉 Welcome to Agensium!
                            </h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <h2 style="margin: 0 0 20px; color: #333333; font-size: 24px; font-weight: 600;">
                                Hi {user_name}!
                            </h2>
                            
                            <p style="margin: 0 0 20px; color: #666666; font-size: 16px; line-height: 1.6;">
                                Your email has been successfully verified. Welcome to Agensium - your intelligent data mastering platform!
                            </p>

                            <p style="margin: 0 0 20px; color: #666666; font-size: 16px; line-height: 1.6;">
                                Here's what you can do:
                            </p>

                            <ul style="margin: 0 0 30px; padding-left: 20px; color: #666666; font-size: 16px; line-height: 1.8;">
                                <li><strong>Profile Your Data</strong> - Understand your data quality</li>
                                <li><strong>Clean Your Data</strong> - Fix issues automatically</li>
                                <li><strong>Master Your Data</strong> - Create golden records</li>
                            </ul>

                            <!-- CTA Button -->
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="https://agensium2.netlify.app/login" 
                                   style="display: inline-block; padding: 16px 32px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 600;">
                                    Get Started →
                                </a>
                            </div>

                            <p style="margin: 0; color: #999999; font-size: 14px; line-height: 1.6;">
                                If you have any questions, feel free to reach out to our support team.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px; background-color: #f8f9fa; border-radius: 0 0 8px 8px; text-align: center;">
                            <p style="margin: 0 0 10px; color: #999999; font-size: 12px;">
                                © 2025 Agensium. All rights reserved.
                            </p>
                            <p style="margin: 0; color: #999999; font-size: 12px;">
                                Need help? Contact us at 
                                <a href="mailto:support@agensium.com" style="color: #667eea; text-decoration: none;">support@agensium.com</a>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def get_password_changed_template(user_name: str) -> str:
    """
    Generate HTML template for password changed notification.

    Args:
        user_name: User's full name

    Returns:
        HTML string
    """
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Password Changed</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f7;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 0;">
                <table role="presentation" style="width: 100%; max-width: 600px; border-collapse: collapse; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 600;">
                                Agensium
                            </h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <h2 style="margin: 0 0 20px; color: #333333; font-size: 24px; font-weight: 600;">
                                🔐 Password Changed
                            </h2>
                            
                            <p style="margin: 0 0 20px; color: #666666; font-size: 16px; line-height: 1.6;">
                                Hi {user_name},
                            </p>
                            
                            <p style="margin: 0 0 30px; color: #666666; font-size: 16px; line-height: 1.6;">
                                Your password has been successfully changed. If you made this change, no further action is needed.
                            </p>

                            <div style="background-color: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 20px; margin: 0 0 30px;">
                                <p style="margin: 0; color: #856404; font-size: 14px; line-height: 1.6;">
                                    ⚠️ <strong>Didn't make this change?</strong><br>
                                    If you didn't change your password, please contact our support team immediately or reset your password.
                                </p>
                            </div>

                            <p style="margin: 0; color: #999999; font-size: 14px; line-height: 1.6;">
                                For security reasons, this notification is sent whenever your password is changed.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px; background-color: #f8f9fa; border-radius: 0 0 8px 8px; text-align: center;">
                            <p style="margin: 0 0 10px; color: #999999; font-size: 12px;">
                                © 2025 Agensium. All rights reserved.
                            </p>
                            <p style="margin: 0; color: #999999; font-size: 12px;">
                                Need help? Contact us at 
                                <a href="mailto:support@agensium.com" style="color: #667eea; text-decoration: none;">support@agensium.com</a>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def get_form_notification_template(
    form_type: str,
    form_data: dict,
    submitted_by: str
) -> str:
    """
    Generate HTML template for admin/client form submission notifications.

    Args:
        form_type: 'contact_request', 'custom_build', or 'investment_hub'
        form_data: The full form data dict
        submitted_by: Email of the user who submitted the form

    Returns:
        HTML string
    """
    form_type_labels = {
        "contact_request": ("Contact to Deploy Request", "#3b82f6", "📋"),
        "custom_build": ("Custom Build Request", "#8b5cf6", "🛠️"),
        "investment_hub": ("Product Investment Inquiry", "#10b981", "💼"),
    }
    label, accent_color, icon = form_type_labels.get(
        form_type, ("Form Submission", "#667eea", "📝")
    )

    # Build a simple key-value rows HTML from the flat parts of form_data
    def _flatten(data: dict, prefix: str = "") -> list[tuple[str, str]]:
        rows = []
        for k, v in data.items():
            display_key = (prefix + k).replace("_", " ").title()
            if isinstance(v, dict):
                rows.extend(_flatten(v, prefix=k + " → "))
            else:
                rows.append((display_key, str(v) if v is not None else "—"))
        return rows

    rows_html = ""
    for key, value in _flatten(form_data):
        rows_html += f"""
                            <tr>
                                <td style="padding: 10px 12px; color: #555555; font-size: 14px; font-weight: 600; background-color: #f8f9fa; border: 1px solid #e9ecef; width: 35%; vertical-align: top;">{key}</td>
                                <td style="padding: 10px 12px; color: #333333; font-size: 14px; border: 1px solid #e9ecef; word-break: break-word;">{value}</td>
                            </tr>"""

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>New {label}</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f7;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 0;">
                <table role="presentation" style="width: 100%; max-width: 640px; border-collapse: collapse; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 36px 40px 24px; text-align: center; background: linear-gradient(135deg, {accent_color} 0%, #764ba2 100%); border-radius: 8px 8px 0 0;">
                            <p style="margin: 0 0 8px; font-size: 32px;">{icon}</p>
                            <h1 style="margin: 0; color: #ffffff; font-size: 22px; font-weight: 700;">
                                New {label}
                            </h1>
                            <p style="margin: 8px 0 0; color: rgba(255,255,255,0.85); font-size: 14px;">
                                Agensium Platform
                            </p>
                        </td>
                    </tr>

                    <!-- Alert Banner -->
                    <tr>
                        <td style="padding: 16px 40px; background-color: #fffbeb; border-bottom: 1px solid #fde68a;">
                            <p style="margin: 0; color: #92400e; font-size: 14px; text-align: center;">
                                A user just submitted a <strong>{label}</strong>. Please review the details below.
                            </p>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 36px 40px;">
                            <h2 style="margin: 0 0 20px; color: #333333; font-size: 18px; font-weight: 600; border-bottom: 2px solid {accent_color}; padding-bottom: 10px;">
                                Submission Details
                            </h2>

                            <table style="width: 100%; border-collapse: collapse; margin-bottom: 30px;">
                                {rows_html}
                            </table>

                            <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 16px; margin-top: 10px;">
                                <p style="margin: 0; color: #166534; font-size: 13px;">
                                    <strong>Submitted by:</strong> {submitted_by}
                                </p>
                            </div>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 40px; background-color: #f8f9fa; border-radius: 0 0 8px 8px; text-align: center;">
                            <p style="margin: 0 0 6px; color: #999999; font-size: 12px;">
                                © 2026 Agensium. All rights reserved.
                            </p>
                            <p style="margin: 0; color: #999999; font-size: 12px;">
                                This is an automated notification from the Agensium platform.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
