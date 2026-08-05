import frappe
from datetime import datetime, timedelta
from salon.whatsapp.utils import send_whatsapp_template
from frappe import _
from frappe.utils import flt



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


###### Customer Deposit ######
### on_submit
def on_payment_submit(doc, method=None):
    if doc.party_type == "Customer" and doc.is_customer_deposit:
        if doc.payment_type == "Receive":
            add_customer_deposit(doc, method)

        elif doc.payment_type == "Pay":
            if frappe.session.user != "Administrator" and frappe.get_value("User", frappe.session.user, "role_profile_name") != "Salon Admin":
                frappe.throw(_("User has no permission to refund deposits. Please be in touch with the administration."))
                return

            cancel_customer_deposit(doc, method)

def add_customer_deposit(doc, method=None):
    if doc.party_type == "Customer" and doc.is_customer_deposit:
        cust = frappe.get_doc("Customer", doc.party)
        cust.deposit_balance += doc.paid_amount
        cust.save(ignore_permissions=True)

        if doc.send_confirmation_message:
            whatsapp_settings = frappe.get_doc("WhatsApp Settings")
            send_whatsapp_template(
                customer_number=cust.mobile_no,
                template_name=whatsapp_settings.default_deposit_confirmation_template,
                components=[
                    {
                        "section_name": "body",
                        "params": [
                            {
                                "type": "text",
                                "text": cust.customer_name
                            },
                            {
                                "type": "text",
                                "text": doc.paid_amount
                            },
                        ]
                    },
                ]
            )

        frappe.db.commit()


def cancel_customer_deposit(doc, method=None):
    cust = frappe.get_doc("Customer", doc.party)

    if (cust.deposit_balance - doc.paid_amount) < 0:
        frappe.throw(_("Customer has insufficient balance."))
        return

    cust.deposit_balance -= doc.paid_amount
    cust.save(ignore_permissions=True)

    frappe.set_value(
        "Payment Entry",
        doc.deposit_id,
        "deposit_refunded",
        1
    )

    frappe.db.commit()
    
    # if doc.send_confirmation_message:
    #     whatsapp_settings = frappe.get_doc("WhatsApp Settings")
    #     send_whatsapp_template(
    #         customer_number=cust.mobile_no,
    #         template_name=whatsapp_settings.default_deposit_confirmation_template,
    #         components=[
    #             {
    #                 "section_name": "body",
    #                 "params": [
    #                     {
    #                         "type": "text",
    #                         "text": cust.customer_name
    #                     },
    #                     {
    #                         "type": "text",
    #                         "text": doc.paid_amount
    #                     },
    #                 ]
    #             },
    #         ]
    #     )


###### Invoices (Transactions) ######

## POS Invoice
### after_insert
# def get_advances(doc, method=None):
#     if doc.use_deposit and doc.deposit_used:
#         doc.set_advances()
#         doc.save()


def get_advances(doc, method=None):
    if not (doc.use_deposit and doc.deposit_used):
        return

    # Already populated (validate ran before before_submit), skip
    if doc.get("advances"):
        return

    doc.set("advances", [])

    advance_entries = frappe.db.sql("""
        SELECT
            'Payment Entry' as reference_type,
            pe.name as reference_name,
            pe.remarks,
            pe.unallocated_amount,
            pe.paid_from as account
        FROM `tabPayment Entry` pe
        WHERE pe.party_type = 'Customer'
            AND pe.party = %s
            AND pe.is_customer_deposit = 1
            AND pe.deposit_refunded = 0
            AND pe.docstatus = 1
            AND pe.unallocated_amount > 0
        ORDER BY pe.posting_date ASC
    """, (doc.customer,), as_dict=1)

    if not advance_entries:
        frappe.throw(
            f"No available deposit entries found for customer {doc.customer}"
        )

    remaining = flt(doc.deposit_used)
    total_allocated = 0.0

    for entry in advance_entries:
        if remaining <= 0:
            break

        allocated = min(flt(entry.unallocated_amount), remaining)

        doc.append("advances", {
            "reference_type": entry.reference_type,
            "reference_name": entry.reference_name,
            "remarks": entry.remarks,
            "advance_amount": flt(entry.unallocated_amount),
            "allocated_amount": allocated,
            "ref_exchange_rate": 1.0,
        })

        remaining -= allocated
        total_allocated += allocated

        # Only permanently debit the PE on before_submit, not on every validate
        if doc.docstatus == 1:
            frappe.db.set_value(
                "Payment Entry",
                entry.reference_name,
                "unallocated_amount",
                flt(entry.unallocated_amount) - allocated,
                update_modified=False,
            )

    if remaining > 0:
        frappe.throw(
            f"Insufficient deposit balance. Short by {frappe.utils.fmt_money(remaining)}"
        )

    # Let ERPNext handle the save — never call doc.save() inside a hook
    total_paid = flt(doc.total_advance) + total_allocated
    doc.total_advance = total_paid
    doc.outstanding_amount = max(
        flt(doc.grand_total) - flt(doc.write_off_amount) - total_paid, 0.0
    )

### validate
def pos_invoice_validate(doc, method=None):
    get_advances(doc, method)

    for item in doc.items:
        if item.is_service and not item.employee:
            frappe.throw(_("Employee is required for service item {0}").format(item.item_code))

## POS Invoice | Sales Invoice
### validate
def fetch_customer(doc, method=None):
    customer = frappe.db.get_value("Customer", {"mrn": doc.mrn})
    if customer:
        doc.customer = customer


### on_submit
def deduct_deposit_balance(doc, method=None):
    frappe.log_error(
        title="Deduct Deposit Balance Error",
        message=doc.doctype + " " + doc.name
    )
    if doc.doctype == "Sales Invoice" and doc.is_consolidated:
        return
    
    
    if doc.advances:
        cust = frappe.get_doc("Customer", doc.customer)
        for ap in doc.advances:
            advance_amount = ap.allocated_amount

            if cust.deposit_balance < advance_amount:
                frappe.throw("Customer deposit balance is insufficient.")

            cust.deposit_balance -= advance_amount
            cust.save(ignore_permissions=True)

    if doc.doctype == "POS Invoice":
        send_review_messages(doc, method)
        send_invoice(doc, method)


        # Create GL movement if you want accounting entry
        # pe = frappe.new_doc("Payment Entry")
        # pe.payment_type = "Receive"
        # pe.party_type = "Customer"
        # pe.party = doc.customer
        # pe.paid_amount = doc.deposit_used
        # pe.received_amount = doc.deposit_used
        # pe.paid_to = "Customer Deposits"
        # pe.remarks = f"Deposit used for POS Invoice {doc.name}"
        # pe.insert(ignore_permissions=True)
        # pe.submit()


###### Appointments (Calendar) ######
### validate
def validate_appointment(doc, method=None):
    validate_availability(doc, method)
    update_status(doc, method)
    send_cancellation_message(doc, method)

def validate_availability(doc, method=None):

    if doc.status in ["Cancelled", "Closed", "Waiting"] or doc.workflow_state in ["Cancelled", "Attended"]:
        return
        
    def get_dep_concurrent_guests(employee: str, check_datetime: datetime):
        """
        Counts all overlapping appointments for this employee in the same department.
        """
        proposed_start = check_datetime
        if isinstance(proposed_start, str):
            proposed_start = datetime.strptime(proposed_start, "%Y-%m-%d %H:%M:%S")
        proposed_end = proposed_start + timedelta(seconds=duration_seconds)
        proposed_start_str = proposed_start.strftime("%Y-%m-%d %H:%M:%S")
        proposed_end_str   = proposed_end.strftime("%Y-%m-%d %H:%M:%S")
        total_booked = frappe.db.count(
            "Appointment",
            filters={
                "name": ["!=", doc.name],
                "employee": employee,
                "status": ["not in", ["Cancelled"]],
                "department": doc.department,
                "scheduled_time": ["<",  proposed_end_str],
                "scheduled_end_time": [">",  proposed_start_str],
            }
        )
        return total_booked

    def get_diff_dep_concurrent_guests(employee: str, check_datetime: datetime):
        """
        Counts overlapping appointments for this employee in different departments,
        respecting allow_overlapping and Overlapping Department settings.
        """
        proposed_start = check_datetime
        if isinstance(proposed_start, str):
            proposed_start = datetime.strptime(proposed_start, "%Y-%m-%d %H:%M:%S")
        proposed_end = proposed_start + timedelta(seconds=duration_seconds)
        proposed_start_str = proposed_start.strftime("%Y-%m-%d %H:%M:%S")
        proposed_end_str   = proposed_end.strftime("%Y-%m-%d %H:%M:%S")

        allow_overlapping = frappe.get_value("Employee", employee, "allow_overlapping")
        if allow_overlapping:
            overlapping_departments = frappe.get_all(
                "Overlapping Department",
                filters={"parent": employee},
                fields=["department"],
            )
            deps = [dep["department"] for dep in overlapping_departments] + [doc.department]
            total_booked = frappe.db.count(
                "Appointment",
                filters={
                    "name": ["!=", doc.name],
                    "employee": employee,
                    "status": ["not in", ["Cancelled"]],
                    "department": ["not in", deps],
                    "scheduled_time": ["<",  proposed_end_str],
                    "scheduled_end_time": [">",  proposed_start_str],
                }
            )
        else:
            total_booked = frappe.db.count(
                "Appointment",
                filters={
                    "name": ["!=", doc.name],
                    "employee": employee,
                    "status": ["not in", ["Cancelled"]],
                    "department": ["!=", doc.department],
                    "scheduled_time": ["<",  proposed_end_str],
                    "scheduled_end_time": [">",  proposed_start_str],
                }
            )
        return total_booked

    def check_employee_leaves():
        employee_times = frappe.get_value(
            "Employee Appointment Times",
            {
                "employee": doc.employee,
                "start_date": ["<=", doc.selected_date],
                "end_date": [">=", doc.selected_date],
            },
            ["name", "start_time", "end_time", "start_date", "end_date", "is_unavailable"],
            as_dict=True,
        )
        if employee_times:
            if employee_times.is_unavailable == 1:
                frappe.throw(f"The employee is not available on {doc.selected_date}.")
        
        leaves = frappe.get_all(
            "Leave Application",
            filters={
                "employee": doc.employee,
                "status": "Approved",
                "from_date": ["<=", doc.selected_date],
                "to_date": [">=", doc.selected_date],
            }
        )
        if leaves:
            frappe.throw(f"The employee is not available on {doc.selected_date}.")

    if doc.status == "Cancelled":
        return
    
    check_employee_leaves()

    start_date = doc.scheduled_time
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")

    service_duration = frappe.get_value("Item", doc.service, "service_duration")
    appointment_settings = frappe.get_all(
        "Service Employee",
        filters={
            "parent": doc.service,
            "employee": doc.employee,
        },
        fields=["name", "customers_capacity"]
    )
    if not appointment_settings:
        frappe.throw(
            "No appointment settings found for this employee on the selected day."
        )

    duration_seconds = int(service_duration) if service_duration else 1800
    customers_capacity = int(appointment_settings[0].customers_capacity or 1)

    # Step 1: Check same-department capacity
    dep_booked_count = get_dep_concurrent_guests(doc.employee, doc.scheduled_time)
    remaining_capacity = customers_capacity - dep_booked_count

    if remaining_capacity <= 0:
        frappe.throw(
            f"""This time slot is fully booked.
            • Current guests: {dep_booked_count}
            • Allowed capacity: {customers_capacity}
            Please check the calendar or select another time.""",
            title="Slot Not Available",
        )

    # Step 2: Check cross-department conflicts
    diff_dep_booked_count = get_diff_dep_concurrent_guests(doc.employee, doc.scheduled_time)
    if diff_dep_booked_count > 0:
        frappe.throw(
            f"""The employee is already booked in another department during this time slot.
            • Conflicting appointments: {diff_dep_booked_count}
            Please select another time.""",
            title="Employee Not Available",
        )

    return True

def after_inserting_appointment(doc, method=None):
    send_appointment_notifications(doc, method)

def send_appointment_notifications(doc, method=None):
    if doc.send_confirmation_message == 0:
        return
    customer = frappe.get_doc("Customer", doc.party)
    whatsapp_settings = frappe.get_doc("WhatsApp Settings")

    date, time = parse_scheduled_time(doc.scheduled_time)

    service_name = frappe.get_value("Item", doc.service, "item_name_in_arabic")
    if not service_name:
        service_name = frappe.get_value("Item", doc.service, "item_name")

    send_whatsapp_template(
        customer_number = customer.mobile_no,
        template_name = whatsapp_settings.default_appointment_template,
        components=[
            {
                "section_name": "body",
                "params": [
                    {
                        "type": "text",
                        "text": customer.customer_name
                    },
                    {
                        "type": "text",
                        "text": service_name
                    },
                    {
                        "type": "text",
                        "text": date
                    },
                    {
                        "type": "text",
                        "text": time
                    }
                ]
            },
        ]
    )

def update_status(doc, method=None):
    if doc.workflow_state == "Attended":
        doc.status = "Closed"

        if not frappe.db.exists("Customer Cart", {"customer": doc.party, "docstatus": 0}):
            cart = frappe.new_doc("Customer Cart")
            cart.customer = doc.party
            cart.insert(ignore_permissions=True)

        if not frappe.db.exists("Lab Transaction", {"appointment": doc.name}):
            cart = frappe.new_doc("Lab Transaction")
            cart.appointment = doc.name
            cart.insert(ignore_permissions=True)

        frappe.db.commit()
            
    elif doc.workflow_state == "Cancelled":
        doc.status = "Cancelled"

    if doc.status == "Open":
        doc.color = "#ffa3a3"

    elif doc.status == "Closed":
        doc.color = "#aeff9f"

    elif doc.status == "Cancelled":
        doc.color = "#d4d4d4"

    elif doc.status == "Unverified":
        doc.color = "#fff09c"

    elif doc.status == "Waiting":
        doc.color = "#aaebff"
        
def send_cancellation_message(doc, method):
    customer = frappe.get_doc("Customer", doc.party)
    whatsapp_settings = frappe.get_doc("WhatsApp Settings")

    if isinstance(doc.scheduled_time, datetime):
        appointment_datetime = doc.scheduled_time
    else:
        appointment_datetime = datetime.strptime(doc.scheduled_time, "%Y-%m-%d %H:%M:%S")

    service_name = frappe.get_value("Item", doc.service, "item_name_in_arabic")
    if not service_name:
        service_name = frappe.get_value("Item", doc.service, "item_name")


    if doc.workflow_state == "Cancelled" and doc.sent_cancelation == 0:
        appointment_date = appointment_datetime.strftime("%Y-%m-%d")
        appointment_time = appointment_datetime.strftime("%H:%M:%S")
        response = send_whatsapp_template(
            customer_number = customer.mobile_no,
            template_name = whatsapp_settings.default_appointment_cancelation_template,
            components=[
                {
                    "section_name": "body",
                    "params": [
                        {
                            "type": "text",
                            "text": customer.customer_name
                        },
                        {
                            "type": "text",
                            "text": service_name
                        },
                        {
                            "type": "text",
                            "text": appointment_date
                        },
                        {
                            "type": "text",
                            "text": appointment_time
                        }
                    ]
                },
            ]
        )

        if response.get("success"):
            doc.sent_cancelation = 1

    
def send_review_messages(doc, method=None):
    try:
        cust = frappe.get_doc("Customer", doc.customer)
        
        response = send_whatsapp_template(
            customer_number=cust.mobile_no,
            template_name="service_rating_ar",
            components=[
                {
                    "section_name": "body",
                    "params": [
                        {
                            "type": "text",
                            "text": cust.customer_name
                        },
                    ]
                },
            ]
        )

        # frappe.log_error(
        #     title="Service Review",
        #     message= doc.name
        # )

        # for service in doc.items:
        #     if not service.employee:
        #         continue
        #     review = frappe.new_doc("Service Review")
        #     review.reference_type = doc.doctype
        #     review.order_id = doc.name
        #     review.customer = doc.customer
        #     review.service = service.item_code
        #     review.employee = service.employee
        #     review.insert(ignore_permissions=True)
    except Exception as e:
        note = frappe.new_doc("Note")
        note.public = 1
        note.title = "WHATSAPPPPPP"
        note.content = str(e)
        note.insert(ignore_permissions=True)
        frappe.db.commit()

        frappe.log_error(
            title="Service Review Error",
            message=str(e)
        )


def send_invoice(doc, method=None):
    try:
        whatsapp_settings = frappe.get_doc("WhatsApp Settings")
        cust = frappe.get_doc("Customer", doc.customer)

        pdf_content = frappe.get_print(
            doc.doctype,
            doc.name,
            "POS Invoice V2",
            as_pdf=True,
        )

        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": f"Invoice-{doc.name}.pdf",
            "content": pdf_content,
            "attached_to_doctype": doc.doctype,
            "attached_to_name": doc.name,
            "is_private": 0,
        })
        file_doc.insert(ignore_permissions=True)

        file_url = frappe.utils.get_url() + file_doc.file_url

        send_whatsapp_template(
            customer_number=cust.mobile_no,
            template_name=whatsapp_settings.default_invoice_template,
            components=[
                {
                    "section_name": "header",
                    "params": [
                        {
                            "type": "document",
                            "file_url": file_url,
                            "file_name": f"Invoice-{doc.posting_date}.pdf",
                        },
                    ]
                },
            ]
        )

    except Exception as e:
        note = frappe.new_doc("Note")
        note.public = 1
        note.title = "WHATSAPPPPPP"
        note.content = str(e)
        note.insert(ignore_permissions=True)
        frappe.db.commit()

        frappe.log_error(
            title="Send Invoice Error",
            message=str(e)
        )
    

##### Customer
def before_inserting_customer(doc, method=None):
    assign_mrn(doc, method)

def assign_mrn(doc, method=None):
    # if not doc.mrn:
    max_mrn = frappe.db.sql("SELECT MAX(CAST(mrn AS UNSIGNED)) FROM `tabCustomer`")[0][0] or 0
    doc.mrn = str(int(max_mrn) + 1)
    # doc.save(ignore_permissions=True)


## Leave Application
def on_submit_leave(doc, method=None):
    if doc.status == "Approved":
        frappe.db.set_value(
            "Appointment",
            {
                "employee": doc.employee,
                "status": ["in", ["Open", "Unverified", "Waiting"]],
                "selected_date": ["between", [doc.from_date, doc.to_date]]
            },
            "status",
            "Reschedule",
        )


## Employee
def on_employee_save(doc, method=None):
    doc.first_last_name = f"{doc.first_name} {doc.last_name}"