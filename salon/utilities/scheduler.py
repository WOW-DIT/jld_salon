import frappe
from datetime import datetime, timedelta
from frappe.utils import today, nowdate, add_days, get_datetime, date_diff, add_to_date
import requests
from salon.whatsapp.utils import send_whatsapp_template

def parse_scheduled_time(scheduled_time):
    """
    Accepts datetime object or string, returns (date_str, time_str_12h_arabic)
    """
    if isinstance(scheduled_time, str):
        # Try common frappe datetime formats
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                dt = datetime.strptime(scheduled_time, fmt)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"Unrecognized datetime string format: {scheduled_time}")
    elif isinstance(scheduled_time, datetime):
        dt = scheduled_time
    else:
        # Handle date-only objects (no time component)
        dt = datetime.combine(scheduled_time, datetime.min.time())

    date_str = dt.strftime("%Y-%m-%d")

    hour = dt.hour
    minute = dt.minute
    period = "صباحاً" if hour < 12 else "مساءً"
    hour_12 = hour % 12 or 12  # convert 0 -> 12
    time_str = f"{hour_12}:{minute:02d} {period}"

    return date_str, time_str


def unify_mobile_number(number, document):
    """
    Takes common mobile number formats [05..., 5...]
    and unifies them into 9665...
    
    :return: 9665... mobile number format
    """
    unified_number = None
    if len(number) == 10 and number[:2] == "05":
        short_number = str(number[1:]).replace(" ", "")

        unified_number = f"966{short_number}"

    elif len(number) < 10 and number[0] == "5":
        unified_number = f"966{number}"

    else:
        unified_number = None
        frappe.log_error(
            title="Invalid Number Format",
            message="Invalid customer number format",
            reference_doctype=document.doctype,
            reference_name=document.name,
        )

    return unified_number

# @frappe.whitelist(allow_guest=True)
def send_appointment_reminder():
    whatsapp_settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
    api_base_url = whatsapp_settings.api_url
    api_key = whatsapp_settings.get_password("api_key")

    """
    Called every day to send reminders via WhatsApp or SMS
    """
    def send_reminder_to_whatsapp(
        service,
        customer_name,
        customer_number,
        appointment_date,
        appointment_time,
        template_name,
    ):
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
            "components": [
                {
                    "section_name": "body",
                    "params": [
                        {
                            "type": "text",
                            "text": f"{customer_name}"
                        },
                        {
                            "type": "text",
                            "text": f"{service}"
                        },
                        {
                            "type": "text",
                            "text": f"{appointment_date}"
                        },
                        {
                            "type": "text",
                            "text": f"*{appointment_time}*"
                        }
                    ]
                }
            ]
        }
        headers = {"Authorization": f"Basic {api_key}"}
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 200:
            data = response.json()["message"]

            if data.get("success"):
                reference_id = data.get("reference_id")

                url = f"{api_base_url}/whatsapp_integration.whatsapp_integration.doctype.whatsapp_broadcast_message.whatsapp_broadcast_message.submit_broadcast"
                payload = {
                    "reference_id": reference_id
                }
                response = requests.post(url, headers=headers, json=payload)

    
    today = nowdate()

    schedules = frappe.get_all(
        "Appointment Reminder Schedule",
        filters={"enabled": 1},
        fields=["name", "channel", "whatsapp_template", "before_date"]
    )

    days = []
    for s in schedules:
        threshold_datetime = add_to_date(today, seconds=int(s.before_date))
        days.append(threshold_datetime)
        # threshold_date_str = threshold_datetime.strftime("%Y-%m-%d")

        appointments_to_remind = frappe.db.sql("""
            SELECT 
                t1.name,
                t1.service,
                t1.customer,
                t1.customer_name,
                t1.customer_email,
                t1.customer_phone_number,
                t1.scheduled_time
            FROM 
                `tabAppointment` AS t1
            WHERE 
                t1.status IN ('Open', 'Unverified')
                AND t1.selected_date >= %s
                AND t1.selected_date <= %s
            ORDER BY
                t1.selected_date ASC
        """, (today, threshold_datetime, ), as_dict=True)

        for ap in appointments_to_remind:
            ## Skip if the reminder was sent already
            if frappe.db.exists("Appointment Reminder Log", {"appointment": ap.name, "schedule": s.name}):
                continue

            ## Skip if another reminder was sent on the same day
            if frappe.db.exists("Appointment Reminder Log", {"appointment": ap.name, "sent_date": today}):
                continue

            customer_number = unify_mobile_number(ap.customer_phone_number, ap)

            ## Invalid customer number
            if customer_number == None:
                continue
            
            try:
                date, time = parse_scheduled_time(ap.scheduled_time)
                service_name = frappe.get_value("Item", ap.service, "item_name_in_arabic")
                if not service_name:
                    service_name = frappe.get_value("Item", ap.service, "item_name")
                
                ## Send reminder
                if s.channel == "WhatsApp" or s.channel == "WhatsApp & SMS":
                    response = send_reminder_to_whatsapp(
                        service_name,
                        ap.customer_name,
                        customer_number,
                        date,
                        time,
                        whatsapp_settings.default_appointment_reminder_template,
                    )

                if s.channel == "SMS" or s.channel == "WhatsApp & SMS":
                    pass
                
                ## Save reminder logs
                log = frappe.new_doc("Appointment Reminder Log")
                log.appointment = ap.name
                log.schedule = s.name
                log.sent_date = today
                log.insert(ignore_permissions=True)
            except Exception as e:
                frappe.throw(str(e))
                pass

        frappe.db.commit()

    return days


def check_loyalty_expiry():
    whatsapp_settings = frappe.get_doc("WhatsApp Settings")

    one_month_later = add_days(today(), 30)

    expiring_entries = frappe.get_all(
        "Loyalty Point Entry",
        filters={
            "expiry_date": ["between", [today(), one_month_later]],
            "loyalty_points": [">", 0]
        },
        fields=["customer", "loyalty_points", "expiry_date"]
    )

    for entry in expiring_entries:
        customer = frappe.get_value(
            "customer",
            entry.customer,
            ["mobile_no", "customer_name"],
            as_dict=True,
        )

        total_points = frappe.db.sql("""
            SELECT SUM(loyalty_points)
            FROM `tabLoyalty Point Entry`
            WHERE customer = %s AND loyalty_points > 0
        """, (entry.customer,))[0][0] or 0

        send_whatsapp_template(
            customer_number=customer.mobile_no,
            template_name=whatsapp_settings.default_royalty_points_expiry_template,
            components=[
                {
                    "section_name": "body",
                    "params": [
                        {
                            "type": "text",
                            "text": customer.customer_name.split(" ")
                        },
                        {
                            "type": "text",
                            "text": str(int(total_points))
                        },
                        {
                            "type": "text",
                            "text": str(int(entry.loyalty_points))
                        },
                        {
                            "type": "text",
                            "text": str(entry.expiry_date)
                        },
                    ]
                },
            ]
        )
        # frappe.sendmail(
        #     recipients=[frappe.db.get_value("Customer", entry.customer, "email_id")],
        #     subject="Your Loyalty Points Are Expiring Soon!",
        #     message=f"""
        #         Dear {entry.customer},<br><br>
        #         You have <b>{entry.loyalty_points} loyalty points</b> expiring on 
        #         <b>{entry.expiry_date}</b>.<br>
        #         Use them before they expire!<br><br>
        #         Thank you.
        #     """
        # )