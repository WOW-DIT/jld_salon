# import frappe
# import json

# @frappe.whitelist()
# def get_employees():
#     return frappe.get_all(
#         "Employee",
#         filters={"designation": ["in", ["مصففة شعر", "فنية تجميل"]]},
#         fields=["name", "employee_name"],
#     )

# @frappe.whitelist()
# def get_appointment_events(doctype, start, end, field_map, filters=None, fields=None):
#     field_map_dict = frappe._dict(json.loads(field_map))
#     fields = frappe.parse_json(fields)

#     doc_meta = frappe.get_meta(doctype)
#     for d in doc_meta.fields:
#         if d.fieldtype == "Color":
#             field_map_dict.update({"color": d.fieldname})

#     # Ensure employee is always fetched
#     extra_fields = ["customer", "customer_name", "customer_phone_number", "employee", "service", "status", "color"]

#     filters = json.loads(filters) if filters else []

#     start_date = "ifnull({}, '0001-01-01 00:00:00')".format(field_map_dict.start)
#     end_date = "ifnull({}, '2199-12-31 00:00:00')".format(field_map_dict.end)

#     filters += [
#         [doctype, start_date, "<=", end],
#         [doctype, end_date, ">=", start],
#     ]

#     fetch_fields = list({
#         field_map_dict.start,
#         field_map_dict.end,
#         field_map_dict.title,  # customer
#         "name",
#         *extra_fields
#     })

#     events = frappe.get_list(doctype, fields=fetch_fields, filters=filters)

#     # Merge customer + employee into a single title string for the calendar
#     for event in events:
#         mrn = frappe.get_value("Customer", event.get("customer"), "mrn") if event.get("customer") else ""
#         customer_name = event.get("customer_name") or ""
#         customer_phone_number = event.get("customer_phone_number") or ""
#         employee = frappe.get_value("Employee", event.get("employee"), "employee_name") if event.get("employee") else ""
#         service = frappe.get_value("Item", event.get("service"), "item_name")
#         event["title"] = f"{mrn if mrn else ""} {customer_name}\n{service}\n{customer_phone_number}" if employee else customer_name
        
#         app = frappe.get_doc(doctype, event.name)
#         event["url"] = app.get_url()

#     return events

import json
import frappe

@frappe.whitelist()
def get_employees(service=None):
    filters = {
        "designation": ["in", ["مصففة شعر", "فنية تجميل"]],
        "status": "Active",
    }

    if service:
        # frappe.throw(service)
        # Get employees linked to this service via Item Price or a custom table
        # Adjust "Employee Service" and fieldnames to match your actual doctype
        employees = frappe.get_all(
            "Service Employee",
            filters={"parent": service},
            fields=["employee"],
        )
        emp_names = []
        for emp in employees:
            emp_names.append(emp.employee)

        filters["name"] = ["in", emp_names]

    return frappe.get_all(
        "Employee",
        filters=filters,
        fields=["name", "employee_name", "image"],
    )


@frappe.whitelist()
def get_services(department=None):
    filters = {"is_service": 1, "disabled": 0}

    if department:
        filters["item_group"] = department

    return frappe.get_all(
        "Item",
        filters=filters,
        fields=["name", "item_name", "item_group"],
        order_by="item_name asc",
    )


@frappe.whitelist()
def get_appointment_events(doctype, start, end, field_map, filters=None, fields=None, customer=None):
    field_map_dict = frappe._dict(json.loads(field_map))

    doc_meta = frappe.get_meta(doctype)
    for d in doc_meta.fields:
        if d.fieldtype == "Color":
            field_map_dict.update({"color": d.fieldname})

    extra_fields = [
        "customer", "customer_name", "customer_phone_number",
        "employee", "service", "status", "color",
    ]

    filters = json.loads(filters) if filters else []

    filters += [
        ["Appointment", "scheduled_time", "<=", end],
        ["Appointment", "scheduled_end_time", ">=", start],
    ]

    if not customer:
        filters += [["Appointment", "status", "!=", "Cancelled"]]
    else:
        filters += [["Appointment", "customer", "=", customer]]

    fetch_fields = list({
        field_map_dict.start,
        field_map_dict.end,
        field_map_dict.get("title", "customer_name"),
        "name",
        *extra_fields,
    })

    events = frappe.get_list(doctype, fields=fetch_fields, filters=filters)

    # Cache employee names and item names to avoid N+1 queries
    employee_ids  = list({e.get("employee") for e in events if e.get("employee")})
    service_ids   = list({e.get("service")  for e in events if e.get("service")})
    customer_ids  = list({e.get("customer") for e in events if e.get("customer")})

    employee_map = {
        r.name: r.employee_name
        for r in frappe.get_all("Employee", filters={"name": ["in", employee_ids]}, fields=["name", "employee_name"])
    } if employee_ids else {}

    service_map = {
        r.name: r.item_name
        for r in frappe.get_all("Item", filters={"name": ["in", service_ids]}, fields=["name", "item_name"])
    } if service_ids else {}

    customer_map = {
        r.name: r.mrn
        for r in frappe.get_all("Customer", filters={"name": ["in", customer_ids]}, fields=["name", "mrn"])
    } if customer_ids else {}

    for event in events:
        mrn = customer_map.get(event.get("customer"), "")
        mrn = str(mrn)
        customer_name = event.get("customer_name") or ""
        phone = event.get("customer_phone_number") or ""
        service_name = service_map.get(event.get("service"), event.get("service") or "")
        has_employee = bool(event.get("employee"))

        event["title"] = (
            f"{str(mrn)+' ' if mrn else ''}{customer_name}\n{service_name}\n{phone}".strip()
            if has_employee else customer_name
        )

        # Resolve employee name for the frontend resourceId display
        event["employee_name"] = employee_map.get(event.get("employee"), "")

        # Build URL without fetching the full doc
        event["url"] = f"/app/{frappe.scrub(doctype)}/{event['name']}"

    return events