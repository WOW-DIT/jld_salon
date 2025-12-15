import frappe
from datetime import datetime, timedelta
from frappe.utils import nowdate, add_days, get_datetime, date_diff, add_to_date

def unify_mobile_number(number, document):
    """
    Takes common mobile number formats [05..., 5...]
    and unifies them into 9665...
    
    :return: 9665... mobile number format
    """
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
    """
    Called every day to send reminders via WhatsApp or SMS
    """
    def send_reminder_to_whatsapp(customer_name, customer_number, appointment_time, template_name):
        template = frappe.get_doc("WhatsApp Template", template_name)
        whatsapp_number = frappe.get_doc("WhatsApp Number", template.whatsapp_number)

        broadcast = frappe.new_doc("WhatsApp Message")
        broadcast.whatsapp_number = whatsapp_number
        broadcast.append("numbers", {"number": customer_number})
        broadcast.message_type = "template"
        broadcast.template = template_name
        broadcast.append(
            "components",
            {
                "section_name": "body",
                "order": 1,
                "type": "text",
                "text": customer_name
            }
        )
        broadcast.append(
            "components",
            {
                "section_name": "body",
                "order": 2,
                "type": "text",
                "text": appointment_time,
            }
        )
        broadcast.insert(ignore_permissions=True)


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
                t1.party, 
                t1.customer_name, 
                t1.customer_email, 
                t1.customer_phone_number,
                t1.scheduled_time
            FROM 
                `tabAppointment` AS t1
            WHERE 
                t1.status IN ('Open', 'Confirmed')
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
            if customer_number is None:
                continue
            
            try:
                log = frappe.new_doc("Appointment Reminder Log")
                log.appointment = ap.name
                log.schedule = s.name
                log.sent_date = today
                log.insert(ignore_permissions=True)
                continue
                ## Send reminder
                if s.channel == "WhatsApp":
                    response = send_reminder_to_whatsapp(
                        ap.customer_name,
                        customer_number,
                        ap.scheduled_time,
                        s.whatsapp_template,
                    )

                elif s.channel == "SMS":
                    pass
                elif s.channel == "WhatsApp & SMS":
                    response = send_reminder_to_whatsapp(
                        ap.customer_name,
                        customer_number,
                        ap.scheduled_time,
                        s.whatsapp_template,
                    )
                
                ## Save reminder logs
                log = frappe.new_doc("Appointment Reminder Log")
                log.appointment = ap.name
                log.schedule = s.name
                log.sent_date = today
                log.insert(ignore_permissions=True)
            except Exception as e:
                pass

        frappe.db.commit()

    return days
