import frappe
from datetime import datetime


###### Customer Deposit ######
### on_submit
def add_customer_deposit(doc, method=None):
    if doc.party_type == "Customer" and doc.is_customer_deposit:
        cust = frappe.get_doc("Customer", doc.party)
        cust.deposit_balance += doc.paid_amount
        cust.save(ignore_permissions=True)

        # for row in doc.deductions:
        #     if "Customer Deposits" in row.account:
        #         deposit_change = row.amount
        #     cust.deposit_balance += deposit_change
        #     cust.save(ignore_permissions=True)


###### Invoices (Transactions) ######

## POS Invoice
### after_insert
def get_advances(doc, method=None):
    if doc.use_deposit and doc.deposit_used:
        doc.set_advances()
        doc.save()

## POS Invoice | Sales Invoice
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
def validate_availability(doc, method=None):
    def get_concurrent_guests(employee: str, scheduled_time: datetime):
        """Calculates the number of guests already booked concurrently with the proposed slot."""

        # Fetch existing appointments for the employee on that date
        concurrent_count = frappe.db.count(
            "Appointment",
            filters={
                "name": ["!=", doc.name],
                "employee": employee,
                "scheduled_time": scheduled_time,
                "status": "Open",
            },
        )

        return concurrent_count

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
        date = start_date.split(" ")[0]
        year = int(date.split("-")[0])
        month = int(date.split("-")[1])
        day = int(date.split("-")[2])

        time = start_date.split(" ")[1]
        hour = int(time.split(":")[0])
        minute = int(time.split(":")[1])
        second = int(time.split(":")[2])
        
        start_date = datetime(year, month, day, hour, minute, second)
    
    
    weekday = start_date.weekday()
    filters = {
        "department": doc.department,
        "employee": doc.employee,
        "weekday": str(weekday),
    }
    setting = frappe.get_all(
        "Appointment Setting",
        filters=filters,
        fields=["name", "customers_capacity", "duration", "from", "to"]
    )

    if not setting:
        frappe.throw(
            "No appointment settings found for this employee on the selected day."
        )

    capacity = int(setting[0].customers_capacity or 1)

    concurrent_count  = get_concurrent_guests(
        doc.employee,
        doc.scheduled_time
    )

    if concurrent_count >= capacity:
        frappe.throw(
            f"""
            This time slot is fully booked.

            • Current guests: {concurrent_count}
            • Allowed capacity: {capacity}

            Please check the calendar or select another time.
            """,
            title="Slot Not Available",
        )

    return True


def send_review_messages(doc, method=None):
    if not doc.invoice:
        frappe.throw("Invoice is required before submitting")

    for service in doc.services:
        review = frappe.new_doc("Service Review")
        review.order_id = doc.name
        review.service = service.service
        review.employee = service.employee
        review.insert(ignore_permissions=True)