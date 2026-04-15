"""
SMS Notification Service — EduSystem
=====================================
This module is the central hub for SMS notifications.

Current Status: STUB (ready for SMS provider integration)
============================================================
To activate real SMS sending, replace the `send_sms()` function with
your chosen provider's SDK, such as:

  - Twilio:    pip install twilio
  - Africa's Talking (recommended for Ghana/Africa): pip install africastalking
  - Vonage:    pip install vonage

Africa's Talking Example (uncomment to use):
----------------------------------------------
# import africastalking
# africastalking.initialize(username='YOUR_USERNAME', api_key='YOUR_API_KEY')
# sms = africastalking.SMS
#
# def send_sms(phone_number, message):
#     try:
#         response = sms.send(message, [phone_number])
#         return response
#     except Exception as e:
#         print(f"SMS failed: {e}")
#         return None
"""

import logging
import os

logger = logging.getLogger(__name__)

# Dynamically initialize Africa's Talking if credentials are present
AT_USERNAME = os.environ.get('AT_USERNAME', 'sandbox') # AT uses 'sandbox' for testing
AT_API_KEY = os.environ.get('AT_API_KEY', '')

sms_gateway = None

# We use the key to determine if we should switch into Live production mode
if AT_API_KEY:
    try:
        import africastalking
        africastalking.initialize(AT_USERNAME, AT_API_KEY)
        sms_gateway = africastalking.SMS
        logger.info("Africa's Talking SDK successfully initialized for LIVE mode.")
    except Exception as e:
        logger.error(f"Failed to initialize Africa's Talking SDK: {e}")


def send_sms(phone_number: str, message: str) -> bool:
    """
    Send an SMS to a phone number using Africa's Talking.
    
    If AT credentials are not present in .env, this gracefully falls back 
    to STUB mode and logs the message internally without throwing an error.
    
    Args:
        phone_number: Recipient phone number (include country code e.g. +233...)
        message: The SMS body text
    
    Returns:
        True if sent (or simulated), False on error
    """
    if not phone_number:
        return False

    try:
        # 1. Live SMS Production Mode
        if sms_gateway:
            response = sms_gateway.send(message, [phone_number])
            logger.info(f"[LIVE SMS] Sent to {phone_number}. Response: {response}")
            return True
            
        # 2. Fallback Stub Mode (if API key not configured yet)
        else:
            logger.info(f"[SMS STUB] To: {phone_number} | Message: {message}")
            print(f"\n[SMS NOTIFICATION STUB FALLBACK]")
            print(f"   To     : {phone_number}")
            print(f"   Message: {message}\n")
            return True
            
    except Exception as e:
        logger.error(f"Failed to execute SMS flow for {phone_number}: {e}")
        # Even if SMS fails, return False gracefully so the calling system (like Attendance) doesn't crash
        return False


def send_attendance_sms(student, school_name="EduSystem School") -> bool:
    """
    Send an SMS to a student's emergency contact when they are
    marked as present in school.

    Args:
        student: Student model instance
        school_name: Name of school to include in message

    Returns:
        True if SMS was sent (or simulated)
    """
    phone = student.emergency_contact_phone or student.parent_phone
    if not phone:
        return False

    contact_name = student.emergency_contact_name or student.parent_name or "Parent/Guardian"
    student_name = student.user.get_full_name() or student.student_id

    from datetime import date
    today = date.today().strftime("%d %B %Y")

    message = (
        f"Dear {contact_name}, "
        f"this is to inform you that {student_name} "
        f"has been marked present at {school_name} today ({today}). "
        f"Have a great day!"
    )

    return send_sms(phone, message)


def send_absence_sms(student, school_name="EduSystem School") -> bool:
    """
    Send an SMS to a student's emergency contact when they are
    marked as ABSENT from school.
    
    Args:
        student: Student model instance
        school_name: Name of school to include in message
        
    Returns:
        True if SMS was sent (or simulated)
    """
    phone = student.emergency_contact_phone or student.parent_phone
    if not phone:
        return False

    contact_name = student.emergency_contact_name or student.parent_name or "Parent/Guardian"
    student_name = student.user.get_full_name() or student.student_id

    from datetime import date
    today = date.today().strftime("%d %B %Y")

    # ⚠️ URGENT: Absence alert
    message = (
        f"URGENT: {school_name} Attendance Alert. "
        f"Dear {contact_name}, {student_name} was marked ABSENT "
        f"from school today ({today}). "
        f"Please contact the school office if this is unexpected."
    )

    return send_sms(phone, message)
