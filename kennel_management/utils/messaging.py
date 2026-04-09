import frappe
from frappe import _
import json
import requests


def send_sms(phone, message):
    """Send SMS using configured provider."""
    settings = frappe.get_single("Kennel Management Settings")

    if not settings.enable_sms:
        frappe.log_error(title="SMS Not Enabled", message="SMS is not enabled in Kennel Management Settings.")
        return False

    provider = settings.sms_provider
    api_key = settings.get_password("sms_api_key") if settings.sms_api_key else ""
    api_secret = settings.get_password("sms_api_secret") if settings.sms_api_secret else ""

    if not phone or not message:
        return False

    # Clean phone number
    phone = phone.strip().replace(" ", "").replace("-", "")

    try:
        if provider == "Twilio":
            return _send_twilio_sms(phone, message, api_key, api_secret, settings.sms_sender_id)
        elif provider == "BulkSMS":
            return _send_bulksms(phone, message, api_key, api_secret)
        elif provider == "Clickatell":
            return _send_clickatell_sms(phone, message, api_key)
        elif provider == "AfricasTalking":
            return _send_africastalking_sms(phone, message, api_key, api_secret, settings.sms_sender_id)
        elif provider == "Custom":
            return _send_custom_sms(phone, message, settings.sms_gateway_url, api_key)
        else:
            frappe.log_error(title="SMS Provider Error", message=f"Unknown SMS provider: {provider}")
            return False
    except Exception:
        frappe.log_error(title="SMS Send Error", message=frappe.get_traceback())
        return False


def _send_twilio_sms(phone, message, account_sid, auth_token, from_number):
    """Send SMS via Twilio."""
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    response = requests.post(
        url,
        data={"To": phone, "From": from_number, "Body": message},
        auth=(account_sid, auth_token),
        timeout=30,
    )
    response.raise_for_status()
    return True


def _send_bulksms(phone, message, username, password):
    """Send SMS via BulkSMS."""
    url = "https://api.bulksms.com/v1/messages"
    response = requests.post(
        url,
        json={"to": phone, "body": message},
        auth=(username, password),
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    return True


def _send_clickatell_sms(phone, message, api_key):
    """Send SMS via Clickatell."""
    url = "https://platform.clickatell.com/messages/http/send"
    response = requests.get(
        url,
        params={"apiKey": api_key, "to": phone, "content": message},
        timeout=30,
    )
    response.raise_for_status()
    return True


def _send_africastalking_sms(phone, message, api_key, username, sender_id):
    """Send SMS via Africa's Talking."""
    url = "https://api.africastalking.com/version1/messaging"
    headers = {
        "apiKey": api_key,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    data = {"username": username, "to": phone, "message": message}
    if sender_id:
        data["from"] = sender_id
    response = requests.post(url, headers=headers, data=data, timeout=30)
    response.raise_for_status()
    return True


def _send_custom_sms(phone, message, gateway_url, api_key):
    """Send SMS via custom gateway."""
    if not gateway_url:
        frappe.throw(_("Custom SMS gateway URL not configured."))
    response = requests.post(
        gateway_url,
        json={"phone": phone, "message": message, "api_key": api_key},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    return True


def send_whatsapp(phone, message):
    """Send WhatsApp message using configured provider."""
    settings = frappe.get_single("Kennel Management Settings")

    if not settings.enable_whatsapp:
        return False

    provider = settings.whatsapp_provider
    api_key = settings.get_password("whatsapp_api_key") if settings.whatsapp_api_key else ""

    if not phone or not message:
        return False

    phone = phone.strip().replace(" ", "").replace("-", "")

    try:
        if provider == "Meta Cloud API":
            return _send_meta_whatsapp(phone, message, api_key, settings.whatsapp_phone_number_id)
        elif provider == "Twilio":
            return _send_twilio_whatsapp(phone, message, api_key, settings.whatsapp_phone_number_id)
        else:
            frappe.log_error(title="WhatsApp Provider Error", message=f"Unknown provider: {provider}")
            return False
    except Exception:
        frappe.log_error(title="WhatsApp Send Error", message=frappe.get_traceback())
        return False


def _send_meta_whatsapp(phone, message, access_token, phone_number_id):
    """Send WhatsApp message via Meta Cloud API."""
    url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message},
    }
    response = requests.post(url, headers=headers, json=data, timeout=30)
    response.raise_for_status()
    return True


def _send_twilio_whatsapp(phone, message, auth_token, from_number):
    """Send WhatsApp message via Twilio."""
    # For Twilio WhatsApp, the from number should be prefixed
    if not from_number.startswith("whatsapp:"):
        from_number = f"whatsapp:{from_number}"
    if not phone.startswith("whatsapp:"):
        phone = f"whatsapp:{phone}"

    url = f"https://api.twilio.com/2010-04-01/Accounts/{auth_token}/Messages.json"
    response = requests.post(
        url,
        data={"To": phone, "From": from_number, "Body": message},
        timeout=30,
    )
    response.raise_for_status()
    return True
