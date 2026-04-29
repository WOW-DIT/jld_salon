import json
from datetime import datetime, timedelta
import frappe

# @frappe.whitelist()
# def get_employees(service=None, date=None):
#     filters = {
#         "designation": ["in", ["مصففة شعر", "فنية تجميل"]],
#         "status": "Active",
#     }

#     if service:
#         employees = frappe.get_all(
#             "Service Employee",
#             filters={"parent": service},
#             fields=["employee"],
#         )
#         emp_names = [emp.employee for emp in employees]
#         filters["name"] = ["in", emp_names]

#     all_employees = frappe.get_all(
#         "Employee",
#         filters=filters,
#         fields=["name", "employee_name", "image"],
#     )

#     if date:
#         result = []
#         for emp in all_employees:
#             leaves = check_employee_leaves(emp.name, date)
#             if leaves:
#                 continue  # filter out employees on leave

#             shift = employee_shift(emp.name, date)
#             emp["shift_start"] = str(shift["start_time"]) if shift.get("start_time") else None
#             emp["shift_end"]   = str(shift["end_time"])   if shift.get("end_time")   else None
#             emp["unavailable"] = not shift.get("start_time")
#             result.append(emp)
#         return result

#     return all_employees

@frappe.whitelist()
def get_employees(service=None, date=None, department=None):
    filters = {
        "designation": ["in", ["مصففة شعر", "فنية تجميل"]],
        "status": "Active",
    }
 
    if service:
        # Service takes priority — ignore department filter
        employees = frappe.get_all(
            "Service Employee",
            filters={"parent": service},
            fields=["employee"],
        )
        emp_names = [emp.employee for emp in employees]
        filters["name"] = ["in", emp_names]
 
    elif department:
        # No service selected — filter by department via Department Employee child table
        dept_employees = frappe.get_all(
            "Department Employee",
            filters={"parent": department},
            fields=["employee"],
        )
        emp_names = [emp.employee for emp in dept_employees]
        filters["name"] = ["in", emp_names]
 
    all_employees = frappe.get_all(
        "Employee",
        filters=filters,
        fields=["name", "employee_name", "image"],
    )
 
    if date:
        result = []
        for emp in all_employees:
            leaves = check_employee_leaves(emp.name, date)
            if leaves:
                continue  # filter out employees on leave
 
            shift = employee_shift(emp.name, date)
            emp["shift_start"] = str(shift["start_time"]) if shift.get("start_time") else None
            emp["shift_end"]   = str(shift["end_time"])   if shift.get("end_time")   else None
            emp["unavailable"] = not shift.get("start_time")
            result.append(emp)
        return result
 
    return all_employees

def check_employee_leaves(employee: str, date):
        leaves = frappe.get_all(
            "Leave Application",
            filters={
                "employee": employee,
                "status": "Approved",
                "from_date": ["<=", date],
                "to_date": [">=", date],
            }
        )
        return leaves

@frappe.whitelist()
def employee_shift(employee: str, date):
    if isinstance(date, str):
        date_obj = datetime.strptime(date, "%Y-%m-%d")
    else:
        # If date is already a datetime object
        date_obj = date

    weekday = date_obj.weekday()

    employee_times = frappe.get_value(
        "Employee Appointment Times",
        {
            "employee": employee,
            "start_date": ["<=", date_obj],
            "end_date": [">=", date_obj],
        },
        ["name", "start_time", "end_time", "start_date", "end_date", "is_unavailable"],
        as_dict=True,
    )
    if employee_times:
        if employee_times.is_unavailable == 1:
            return {"times": []}
        
        start_time = employee_times.start_time
        end_time = employee_times.end_time

    else:
        shift_assignment = frappe.get_value(
            "Shift Assignment",
            {
                "employee": employee,
                "status": "Active",
                "docstatus": 1,
                "start_date": ["<=", date],
                "end_date": [">=", date],
                "weekday": int(weekday),
            },
            ["name","shift_type"],
            as_dict=True,
        )
        if not shift_assignment:
            return {"times": []}
        
        shift_type = frappe.get_value(
            "Shift Type",
            shift_assignment.shift_type,
            ["name", "start_time", "end_time"],
            as_dict=True
        )
        start_time = shift_type.start_time
        end_time = shift_type.end_time

    return {
        "start_time": str(start_time),
        "end_time":   str(end_time),
    }


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
def get_appointment_events(doctype, start, end, field_map, filters=None, fields=None, customer=None, department=None, service=None):
    frappe.log_error(f"customer={customer!r}  service={service!r}  filters={filters!r}", "EmpCal Debug")
    field_map_dict = frappe._dict(json.loads(field_map))

    doc_meta = frappe.get_meta(doctype)
    for d in doc_meta.fields:
        if d.fieldtype == "Color":
            field_map_dict.update({"color": d.fieldname})

    extra_fields = [
        "customer", "customer_name", "customer_phone_number",
        "employee",  "department", "service",
        "status", "color", "special_request",
        "paid_deposit",
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

    if service:
        filters += [["Appointment", "service", "=", service]]

    if department:
        filters += [["Appointment", "department", "=", department]]

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

        event["service_name"] = service_name

        event["paid_deposit"] = event.paid_deposit == 1 or frappe.db.exists(
            "Payment Entry",
            {"is_customer_deposit": 1, "appointment": event.name},
        )

        event["title"] = (
            f"{str(mrn)+' ' if mrn else ''}{customer_name}\n{service_name}\n{phone}".strip()
            if has_employee else customer_name
        )

        # Resolve employee name for the frontend resourceId display
        event["employee_name"] = employee_map.get(event.get("employee"), "")

        # Build URL without fetching the full doc
        event["url"] = f"/app/{frappe.scrub(doctype)}/{event['name']}"

    return {"events": events, "_debug": {"customer": customer, "service": service, "filters": filters}}