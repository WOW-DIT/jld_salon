import frappe
import requests
from datetime import datetime


def send_whatsapp_template(
    customer_number: str,
    template_name: str,
    components: list,
):
    try:
        whatsapp_settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
        api_base_url = whatsapp_settings.api_url
        api_key = whatsapp_settings.get_password("api_key")

        # template_name = whatsapp_settings.default_appointment_template
        template = frappe.get_doc("WhatsApp Template", template_name)
        whatsapp_number = frappe.get_doc("WhatsApp Number", template.whatsapp_number)

        url = f"{api_base_url}/whatsapp_integration.whatsapp_integration.doctype.whatsapp_broadcast_message.whatsapp_broadcast_message.init_broadcast"

        payload = {
            "instance_id": whatsapp_number.instance_id,
            "message_type": "template",
            "text": None,
            "template_name": template_name,
            "numbers": [
                customer_number
            ],
            "components": components
        }
        headers = {"Authorization": f"Basic {api_key}"}
        response = requests.post(url, headers=headers, json=payload, timeout=15)

        if response.status_code == 200:
            data = response.json()["message"]

        if data.get("success"):
            reference_id = data.get("reference_id")

            url = f"{api_base_url}/whatsapp_integration.whatsapp_integration.doctype.whatsapp_broadcast_message.whatsapp_broadcast_message.submit_broadcast"
            payload = {
                "reference_id": reference_id
            }
            response = requests.post(url, headers=headers, json=payload, timeout=15)

        return {
            "success": response.status_code == 200,
            "data": response.text,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }