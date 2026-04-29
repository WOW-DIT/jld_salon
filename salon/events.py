import frappe
from datetime import datetime, timedelta
from salon.whatsapp.utils import send_whatsapp_template

###### Customer Deposit ######
### on_submit
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

###### Invoices (Transactions) ######

## POS Invoice
### after_insert
def get_advances(doc, method=None):
    if doc.use_deposit and doc.deposit_used:
        doc.set_advances()
        doc.save()

## POS Invoice | Sales Invoice
### validate
def fetch_customer(doc, method=None):
    customer = frappe.db.get_value("Customer", {"mrn": doc.mrn})
    if customer:
        doc.customer = customer


### on_submit
def deduct_deposit_balance(doc, method=None):
    if doc.advances:
        cust = frappe.get_doc("Customer", doc.customer)
        for ap in doc.advances:
            advance_amount = ap.allocated_amount

            if cust.deposit_balance < advance_amount:
                frappe.throw("Customer deposit balance is insufficient.")

            cust.deposit_balance -= advance_amount
            cust.save(ignore_permissions=True)


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
# def validate_availability(doc, method=None):
#     def get_concurrent_guests(employee: str, check_datetime: datetime):
#         proposed_start = check_datetime
#         if isinstance(proposed_start, str):
#             proposed_start = datetime.strptime(proposed_start, "%Y-%m-%d %H:%M:%S")

#         proposed_end = proposed_start + timedelta(seconds=duration_seconds)

#         proposed_start_str = proposed_start.strftime("%Y-%m-%d %H:%M:%S")
#         proposed_end_str   = proposed_end.strftime("%Y-%m-%d %H:%M:%S")

#         total_booked = frappe.db.count(
#             "Appointment",
#             filters={
#                 "name": ["!=", doc.name],
#                 "employee": employee,
#                 "status": ["in", ["Open", "Closed"]],
#                 "department": doc.department,
#                 "scheduled_time": ["<",  proposed_end_str],
#                 "scheduled_end_time": [">",  proposed_start_str],
#             }
#         )

#         return total_booked
    

#     def check_employee_leaves():
#         leaves = frappe.get_all(
#             "Leave Application",
#             filters={
#                 "employee": doc.employee,
#                 "status": "Approved",
#                 "from_date": ["<=", doc.selected_date],
#                 "to_date": [">=", doc.selected_date],
#             }
#         )
#         if leaves:
#             frappe.throw(f"The employee is not available on {doc.selected_date}.")

#     check_employee_leaves()

#     start_date = doc.scheduled_time

#     if isinstance(start_date, str):
#         date = start_date.split(" ")[0]
#         year = int(date.split("-")[0])
#         month = int(date.split("-")[1])
#         day = int(date.split("-")[2])

#         time = start_date.split(" ")[1]
#         hour = int(time.split(":")[0])
#         minute = int(time.split(":")[1])
#         second = int(time.split(":")[2])
        
#         start_date = datetime(year, month, day, hour, minute, second)
    
#     # weekday = start_date.weekday()
#     # filters = {
#     #     "department": doc.department,
#     #     "employee": doc.employee,
#     #     "weekday": str(weekday),
#     # }
#     # setting = frappe.get_all(
#     #     "Appointment Setting",
#     #     filters=filters,
#     #     fields=["name", "customers_capacity", "duration", "from", "to"]
#     # )
#     service_duration = frappe.get_value("Item", doc.service, "service_duration")
#     appointment_settings = frappe.get_all(
#         "Service Employee",
#         filters={
#             "parent": doc.service,
#             "employee": doc.employee,
#         },
#         fields=["name", "customers_capacity"]
#     )

#     if not appointment_settings:
#         frappe.throw(
#             "No appointment settings found for this employee on the selected day."
#         )

#     duration_seconds = int(service_duration) if service_duration else 1800
#     customers_capacity = int(appointment_settings[0].customers_capacity or 1)

#     concurrent_count  = get_concurrent_guests(
#         doc.employee,
#         doc.scheduled_time
#     )

#     if concurrent_count >= customers_capacity:
#         frappe.throw(
#             f"""
#             This time slot is fully booked.

#             • Current guests: {concurrent_count}
#             • Allowed capacity: {customers_capacity}

#             Please check the calendar or select another time.
#             """,
#             title="Slot Not Available",
#         )

#     update_status(doc, method)

#     return True

def validate_availability(doc, method=None):
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
                "status": ["in", ["Open", "Closed"]],
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
                    "status": ["in", ["Open", "Closed"]],
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
                    "status": ["in", ["Open", "Closed"]],
                    "department": ["!=", doc.department],
                    "scheduled_time": ["<",  proposed_end_str],
                    "scheduled_end_time": [">",  proposed_start_str],
                }
            )
        return total_booked

    def check_employee_leaves():
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

    update_status(doc, method)
    return True

def after_inserting_appointment(doc, method=None):
    send_appointment_notifications(doc, method)

def send_appointment_notifications(doc, method=None):
    if doc.send_confirmation_message == 0:
        return

    customer = frappe.get_doc("Customer", doc.party)
    whatsapp_settings = frappe.get_doc("WhatsApp Settings")

    if isinstance(doc.scheduled_time, datetime):
        appointment_datetime = doc.scheduled_time
    else:
        appointment_datetime = datetime.strptime(doc.scheduled_time, "%Y-%m-%d %H:%M:%S")

    date = appointment_datetime.strftime("%Y-%m-%d")
    time = appointment_datetime.strftime("%H:%M")

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
                        "text": date
                    },
                    {
                        "type": "text",
                        "text": time
                    },
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
        

def send_review_messages(doc, method=None):
    if not doc.invoice:
        frappe.throw("Invoice is required before submitting")

    for service in doc.services:
        review = frappe.new_doc("Service Review")
        review.order_id = doc.name
        review.service = service.service
        review.employee = service.employee
        review.insert(ignore_permissions=True)

##### Customer
def before_inserting_customer(doc, method=None):
    assign_mrn(doc, method)

def assign_mrn(doc, method=None):
    # if not doc.mrn:
    max_mrn = frappe.db.sql("SELECT MAX(CAST(mrn AS UNSIGNED)) FROM `tabCustomer`")[0][0] or 0
    doc.mrn = str(int(max_mrn) + 1)
    # doc.save(ignore_permissions=True)