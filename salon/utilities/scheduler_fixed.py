import frappe
from datetime import datetime, timedelta
from frappe.utils import today, nowdate, now_datetime, add_days, get_datetime, add_to_date
import requests
from salon.whatsapp.utils import send_whatsapp_template


def parse_scheduled_time(scheduled_time):
    """
    Accepts datetime object or string, returns (date_str, time_str_12h_arabic)
    """
    if isinstance(scheduled_time, str):
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
        dt = datetime.combine(scheduled_time, datetime.min.time())

    date_str = dt.strftime("%Y-%m-%d")
    hour = dt.hour
    minute = dt.minute
    period = "صباحاً" if hour < 12 else "مساءً"
    hour_12 = hour % 12 or 12
    time_str = f"{hour_12}:{minute:02d} {period}"

    return date_str, time_str


def unify_mobile_number(number, document):
    """
    Takes common mobile number formats [05..., 5...]
    and unifies them into 9665...
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


def _get_service_display_name(service_code):
    service_name = frappe.get_value("Item", service_code, "item_name_in_arabic")
    if not service_name:
        service_name = frappe.get_value("Item", service_code, "item_name")
    return service_name or service_code


def send_reminder_to_whatsapp(
    services_text,
    customer_name,
    customer_number,
    appointment_date,
    appointment_time,
    template_name,
    api_base_url,
    api_key,
):
    """
    Sends ONE whatsapp template message. Returns True only if BOTH
    init_broadcast AND submit_broadcast succeeded. Never raises silently.
    """
    try:
        template = frappe.get_doc("WhatsApp Template", template_name)
        whatsapp_number = frappe.get_doc("WhatsApp Number", template.whatsapp_number)

        init_url = (
            f"{api_base_url}/whatsapp_integration.whatsapp_integration.doctype."
            f"whatsapp_broadcast_message.whatsapp_broadcast_message.init_broadcast"
        )
        payload = {
            "instance_id": whatsapp_number.instance_id,
            "message_type": "template",
            "text": None,
            "template_name": template_name,
            "numbers": [customer_number],
            "components": [
                {
                    "section_name": "body",
                    "params": [
                        {"type": "text", "text": f"{customer_name}"},
                        {"type": "text", "text": f"{services_text}"},
                        {"type": "text", "text": f"{appointment_date}"},
                        {"type": "text", "text": f"*{appointment_time}*"},
                    ],
                }
            ],
        }
        headers = {"Authorization": f"Basic {api_key}"}

        init_response = requests.post(init_url, headers=headers, json=payload, timeout=20)

        if init_response.status_code != 200:
            frappe.log_error(
                title="WhatsApp Reminder - init_broadcast failed",
                message=f"status={init_response.status_code} body={init_response.text} number={customer_number}",
            )
            return False

        init_data = init_response.json().get("message", {})
        if not init_data.get("success"):
            frappe.log_error(
                title="WhatsApp Reminder - init_broadcast returned success=False",
                message=f"response={init_data} number={customer_number}",
            )
            return False

        reference_id = init_data.get("reference_id")

        submit_url = (
            f"{api_base_url}/whatsapp_integration.whatsapp_integration.doctype."
            f"whatsapp_broadcast_message.whatsapp_broadcast_message.submit_broadcast"
        )
        submit_response = requests.post(
            submit_url, headers=headers, json={"reference_id": reference_id}, timeout=20
        )

        if submit_response.status_code != 200:
            frappe.log_error(
                title="WhatsApp Reminder - submit_broadcast failed",
                message=f"status={submit_response.status_code} body={submit_response.text} reference_id={reference_id}",
            )
            return False

        submit_data = submit_response.json().get("message", {})
        if not submit_data.get("success"):
            frappe.log_error(
                title="WhatsApp Reminder - submit_broadcast returned success=False",
                message=f"response={submit_data} reference_id={reference_id}",
            )
            return False

        return True

    except Exception as e:
        frappe.log_error(
            title="WhatsApp Reminder - unexpected exception",
            message=f"{e} | number={customer_number}",
        )
        return False


# def send_appointment_reminder():
#     """
#     Runs frequently (recommend every 15-30 min via cron, NOT every 12h).
#     Groups all of a customer's appointments on the same day into ONE message,
#     for each enabled Appointment Reminder Schedule (day-before / hour-before / etc).
#     Trigger reference = earliest scheduled_time among that day's appointments.
#     """
#     whatsapp_settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
#     api_base_url = whatsapp_settings.api_url
#     api_key = whatsapp_settings.get_password("api_key")

#     now = now_datetime()
#     today_str = nowdate()

#     schedules = frappe.get_all(
#         "Appointment Reminder Schedule",
#         filters={"enabled": 1},
#         fields=["name", "channel", "before_date"],
#     )

#     if not schedules:
#         return

#     # Widest lookahead window across all schedules, so we only query once.
#     max_before_seconds = max(int(s.before_date) for s in schedules)
#     upper_bound = add_to_date(now, seconds=max_before_seconds)

#     appointments = frappe.db.sql(
#         """
#         SELECT
#             t1.name,
#             t1.service,
#             t1.customer,
#             t1.customer_name,
#             t1.customer_phone_number,
#             t1.selected_date,
#             t1.scheduled_time
#         FROM `tabAppointment` AS t1
#         WHERE
#             t1.status IN ('Open', 'Unverified')
#             AND t1.scheduled_time > %s
#             AND t1.scheduled_time <= %s
#         ORDER BY t1.customer, t1.selected_date, t1.scheduled_time ASC
#         """,
#         (now, upper_bound),
#         as_dict=True,
#     )

#     if not appointments:
#         return

#     # Group by (customer, selected_date) -> one message per day per customer
#     groups = {}
#     for ap in appointments:
#         key = (ap.customer, str(ap.selected_date))
#         groups.setdefault(key, []).append(ap)

#     for (customer, selected_date), group_appointments in groups.items():
#         group_appointments.sort(key=lambda a: a.scheduled_time)
#         earliest = group_appointments[0]
#         earliest_dt = get_datetime(earliest.scheduled_time)

#         for s in schedules:
#             threshold_seconds = int(s.before_date)
#             window_start = earliest_dt - timedelta(seconds=threshold_seconds)

#             # Not yet within this schedule's reminder window, or already past due.
#             if not (window_start <= now < earliest_dt):
#                 continue

#             appointment_names = [a.name for a in group_appointments]

#             # Skip whole group if ANY appointment in it already got this schedule's reminder.
#             already_sent = frappe.db.exists(
#                 "Appointment Reminder Log",
#                 {
#                     "appointment": ["in", appointment_names],
#                     "schedule": s.name,
#                 },
#             )
#             if already_sent:
#                 continue

#             customer_number = unify_mobile_number(earliest.customer_phone_number, earliest)
#             if not customer_number:
#                 continue

#             try:
#                 date_str, time_str = parse_scheduled_time(earliest.scheduled_time)

#                 service_names = [_get_service_display_name(a.service) for a in group_appointments]
#                 # Deduplicate while preserving order (in case of repeated services).
#                 seen = set()
#                 unique_services = []
#                 for name in service_names:
#                     if name not in seen:
#                         seen.add(name)
#                         unique_services.append(name)
#                 services_text = "، ".join(unique_services)

#                 sent_ok = False
#                 if s.channel in ("WhatsApp", "WhatsApp & SMS"):
#                     sent_ok = send_reminder_to_whatsapp(
#                         services_text,
#                         earliest.customer_name,
#                         customer_number,
#                         date_str,
#                         time_str,
#                         whatsapp_settings.default_appointment_reminder_template,
#                         api_base_url,
#                         api_key,
#                     )

#                 if s.channel in ("SMS", "WhatsApp & SMS"):
#                     # SMS channel not implemented yet - log so it's visible, not silent.
#                     frappe.log_error(
#                         title="Appointment Reminder - SMS channel not implemented",
#                         message=f"schedule={s.name} customer={customer}",
#                     )

#                 # Only log success as sent if the message actually went out.
#                 if sent_ok:
#                     for ap_name in appointment_names:
#                         log = frappe.new_doc("Appointment Reminder Log")
#                         log.appointment = ap_name
#                         log.schedule = s.name
#                         log.sent_date = today_str
#                         log.insert(ignore_permissions=True)
#                     frappe.db.commit()

#             except Exception as e:
#                 frappe.log_error(
#                     title="Appointment Reminder - group processing failed",
#                     message=f"{e} | customer={customer} date={selected_date} appointments={appointment_names}",
#                 )
#                 continue

def send_appointment_reminder():
    """
    Runs frequently (recommend every 15-30 min via cron, NOT every 12h).
    Groups all of a customer's appointments on the same day into ONE message,
    for each enabled Appointment Reminder Schedule (day-before / hour-before / etc).
    Trigger reference = earliest scheduled_time among that day's appointments.
    """
    whatsapp_settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
    api_base_url = whatsapp_settings.api_url
    api_key = whatsapp_settings.get_password("api_key")

    now = now_datetime()
    today_str = nowdate()

    schedules = frappe.get_all(
        "Appointment Reminder Schedule",
        filters={"enabled": 1},
        fields=["name", "channel", "before_date"],
    )

    if not schedules:
        return

    # Widest lookahead window across all schedules, so we only query once.
    max_before_seconds = max(int(s.before_date) for s in schedules)
    upper_bound = add_to_date(now, seconds=max_before_seconds)

    appointments = frappe.db.sql(
        """
        SELECT
            t1.name,
            t1.service,
            t1.customer,
            t1.customer_name,
            t1.customer_phone_number,
            t1.selected_date,
            t1.scheduled_time
        FROM `tabAppointment` AS t1
        WHERE
            t1.status IN ('Open', 'Unverified')
            AND t1.scheduled_time > %s
            AND t1.scheduled_time <= %s
        ORDER BY t1.customer, t1.selected_date, t1.scheduled_time ASC
        """,
        (now, upper_bound),
        as_dict=True,
    )

    if not appointments:
        return

    # Group by (customer, selected_date) -> one message per day per customer
    groups = {}
    for ap in appointments:
        key = (ap.customer, str(ap.selected_date))
        groups.setdefault(key, []).append(ap)

    for (customer, selected_date), group_appointments in groups.items():
        group_appointments.sort(key=lambda a: a.scheduled_time)
        earliest = group_appointments[0]
        earliest_dt = get_datetime(earliest.scheduled_time)
        appointment_names = [a.name for a in group_appointments]

        # Collect every schedule that is currently due AND hasn't been sent yet
        # for this group. If the appointment was booked shortly before its time,
        # several schedules (1h/12h/1d/2d...) can all be due at once - we still
        # want to send only ONE message, but must record ALL of them as sent so
        # none of them fire again on a later cron run.
        due_schedules = []
        for s in schedules:
            threshold_seconds = int(s.before_date)
            window_start = earliest_dt - timedelta(seconds=threshold_seconds)

            # Not yet within this schedule's reminder window, or already past due.
            if not (window_start <= now < earliest_dt):
                continue

            already_sent = frappe.db.exists(
                "Appointment Reminder Log",
                {
                    "appointment": ["in", appointment_names],
                    "schedule": s.name,
                },
            )
            if already_sent:
                continue

            due_schedules.append(s)

        if not due_schedules:
            continue

        customer_number = unify_mobile_number(earliest.customer_phone_number, earliest)
        if not customer_number:
            continue

        try:
            date_str, time_str = parse_scheduled_time(earliest.scheduled_time)

            service_names = [_get_service_display_name(a.service) for a in group_appointments]
            # Deduplicate while preserving order (in case of repeated services).
            seen = set()
            unique_services = []
            for name in service_names:
                if name not in seen:
                    seen.add(name)
                    unique_services.append(name)
            services_text = "، ".join(unique_services)

            # All schedules currently share the same template/content, so it makes
            # no difference which due schedule "wins" - we send exactly once.
            channels_due = {s.channel for s in due_schedules}

            sent_ok = False
            if channels_due & {"WhatsApp", "WhatsApp & SMS"}:
                sent_ok = send_reminder_to_whatsapp(
                    services_text,
                    earliest.customer_name,
                    customer_number,
                    date_str,
                    time_str,
                    whatsapp_settings.default_appointment_reminder_template,
                    api_base_url,
                    api_key,
                )
            elif channels_due & {"SMS"}:
                # Only SMS-only schedules were due, and SMS isn't implemented yet.
                frappe.log_error(
                    title="Appointment Reminder - SMS channel not implemented",
                    message=f"schedules={[s.name for s in due_schedules]} customer={customer}",
                )

            # Only log success as sent if the message actually went out - and log
            # it against EVERY due schedule, not just one, so none of them re-fire.
            if sent_ok:
                for s in due_schedules:
                    for ap_name in appointment_names:
                        log = frappe.new_doc("Appointment Reminder Log")
                        log.appointment = ap_name
                        log.schedule = s.name
                        log.sent_date = today_str
                        log.insert(ignore_permissions=True)
                frappe.db.commit()

        except Exception as e:
            frappe.log_error(
                title="Appointment Reminder - group processing failed",
                message=f"{e} | customer={customer} date={selected_date} appointments={appointment_names}",
            )
            continue

def check_loyalty_expiry():
    whatsapp_settings = frappe.get_doc("WhatsApp Settings")
    one_month_later = add_days(today(), 30)

    expiring_entries = frappe.get_all(
        "Loyalty Point Entry",
        filters={
            "expiry_date": ["between", [today(), one_month_later]],
            "loyalty_points": [">", 0],
        },
        fields=["customer", "loyalty_points", "expiry_date"],
    )

    for entry in expiring_entries:
        customer = frappe.get_value(
            "Customer",
            entry.customer,
            ["mobile_no", "customer_name"],
            as_dict=True,
        )
        if not customer:
            continue

        total_points = (
            frappe.db.sql(
                """
                SELECT SUM(loyalty_points)
                FROM `tabLoyalty Point Entry`
                WHERE customer = %s AND loyalty_points > 0
                """,
                (entry.customer,),
            )[0][0]
            or 0
        )

        try:
            send_whatsapp_template(
                customer_number=customer.mobile_no,
                template_name=whatsapp_settings.default_royalty_points_expiry_template,
                components=[
                    {
                        "section_name": "body",
                        "params": [
                            {"type": "text", "text": customer.customer_name},
                            {"type": "text", "text": str(int(total_points))},
                            {"type": "text", "text": str(int(entry.loyalty_points))},
                            {"type": "text", "text": str(entry.expiry_date)},
                        ],
                    },
                ],
            )
        except Exception as e:
            frappe.log_error(
                title="Loyalty Expiry Reminder failed",
                message=f"{e} | customer={entry.customer}",
            )