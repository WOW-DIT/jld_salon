import frappe
from datetime import datetime, timedelta, time
import json

# from frappe.desk.calendar import get_events as _get_base_events

@frappe.whitelist()
def get_appointment_events(doctype, start, end, field_map, filters=None, fields=None):
    field_map_dict = frappe._dict(json.loads(field_map))
    fields = frappe.parse_json(fields)

    doc_meta = frappe.get_meta(doctype)
    for d in doc_meta.fields:
        if d.fieldtype == "Color":
            field_map_dict.update({"color": d.fieldname})

    # Ensure employee is always fetched
    extra_fields = ["customer", "customer_name", "customer_phone_number", "employee", "service", "status", "color"]

    filters = json.loads(filters) if filters else []

    start_date = "ifnull({}, '0001-01-01 00:00:00')".format(field_map_dict.start)
    end_date = "ifnull({}, '2199-12-31 00:00:00')".format(field_map_dict.end)

    filters += [
        [doctype, start_date, "<=", end],
        [doctype, end_date, ">=", start],
    ]

    fetch_fields = list({
        field_map_dict.start,
        field_map_dict.end,
        field_map_dict.title,  # customer
        "name",
        *extra_fields
    })

    events = frappe.get_list(doctype, fields=fetch_fields, filters=filters)

    # Merge customer + employee into a single title string for the calendar
    for event in events:
        mrn = frappe.get_value("Customer", event.get("customer"), "mrn") if event.get("customer") else ""
        customer_name = event.get("customer_name") or ""
        customer_phone_number = event.get("customer_phone_number") or ""
        employee = frappe.get_value("Employee", event.get("employee"), "employee_name") if event.get("employee") else ""
        service = frappe.get_value("Item", event.get("service"), "item_name")
        event["title"] = f"{mrn if mrn else ""} {customer_name}\n{service}\n{customer_phone_number}" if employee else customer_name

    return events


@frappe.whitelist()
def update_schedulers():
    doc = frappe.new_doc(
        "Scheduled Job Type"
    )
    doc.method = "salon.utilities.scheduler.send_appointment_reminder"
    doc.cron_format = "0 */12 * * *"
    doc.frequency = "Cron"
    doc.insert(ignore_permissions=True)
    
    frappe.db.commit()
    dd = frappe.get_all(doc.doctype, filters={"method": doc.method})
    return dd
    
    # return frappe.db.get_all("Scheduled Job Type", filters={"method": "scheduler.send_appointment_reminder"})
    # sync_jobs()

@frappe.whitelist()
def get_available_times(
    current_appointment_id: str,
    date: str,
    service_id: str,
    employee: str,
    now: str=None,
):
    def parse_time_field(time_value):
        """Converts a time string or timedelta object into a time object."""
        if isinstance(time_value, str):
            # Assume string format is 'HH:MM:SS'
            return datetime.strptime(time_value, "%H:%M:%S").time()
        elif isinstance(time_value, (timedelta, time)):
            # If it's a timedelta, convert it to seconds, then to HH:MM:SS for replacement
            # If it's a time object, return it directly
            if isinstance(time_value, timedelta):
                total_seconds = int(time_value.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                return time(hours, minutes, seconds)
            return time_value
        else:
            raise TypeError(f"Unsupported time type: {type(time_value)}")
    
    def check_employee_leaves():
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
            # frappe.throw(f"The employee is not available on {date}.")

    def get_concurrent_guests(employee: str, check_datetime: datetime):
        """Calculates the number of guests already booked concurrently with the proposed slot."""
        
        proposed_start = check_datetime
        # proposed_end = proposed_start + timedelta(seconds=duration_seconds)

        full_datetime_str = proposed_start.strftime("%Y-%m-%d %H:%M:%S")

        # Fetch existing appointments for the employee on that date
        concurrent_count = frappe.db.count(
            "Appointment",
            filters={
                "name": ["!=", current_appointment_id],
                "employee": employee,
                "scheduled_time": full_datetime_str,
                "status": "Open",
            }
        )

        return concurrent_count
    

    ## Convert date string to datetime
    if isinstance(date, str):
        date_obj = datetime.strptime(date, "%Y-%m-%d")
    else:
        # If date is already a datetime object
        date_obj = date

    weekday = date_obj.weekday()

    employee_leaves = check_employee_leaves()
    if employee_leaves:
        return {"times": [], "duration": 0}
    
    ## Get employee shift settings
    # filters = {
    #     "employee": employee,
    #     "department": department,
    #     "weekday": str(weekday),
    # }
    # appointment_settings = frappe.get_all(
    #     "Appointment Setting",
    #     filters=filters,
    #     fields=["name", "customers_capacity", "duration", "from", "to"]
    # )
    service_duration = frappe.get_value("Item", service_id, "service_duration")
    appointment_settings = frappe.get_all(
        "Service Employee",
        filters={
            "parent": service_id,
            "employee": employee,
        },
        fields=["name", "customers_capacity"]
    )

    if not appointment_settings:
        return {"times": []}
    
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
    
    setting = appointment_settings[0]
    setting["from"] = shift_type.start_time
    setting["to"] = shift_type.end_time

    duration_seconds = int(service_duration) if service_duration else 1800
    customers_capacity = int(setting.get("customers_capacity"))


    ## Parse shift start and end times
    try:
        start_time_obj = parse_time_field(setting["from"])
        end_time_obj = parse_time_field(setting["to"])
    except ValueError:
        return {"error": "Invalid time format in Appointment Setting."}
    
    # Combine the date object with the shift times
    start_datetime = date_obj.replace(
        hour=start_time_obj.hour, 
        minute=start_time_obj.minute, 
        second=start_time_obj.second, 
        microsecond=0
    )
    end_datetime = date_obj.replace(
        hour=end_time_obj.hour, 
        minute=end_time_obj.minute, 
        second=end_time_obj.second, 
        microsecond=0
    )

    step = timedelta(seconds=duration_seconds)
    available_times = []
    current_time = start_datetime

    now_datetime = None
    if now:
        try:
            now_datetime = datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            now_datetime = None

    
    # Loop through the time range, stepping by the appointment duration
    while current_time < end_datetime:
        if now_datetime and date_obj.date() == now_datetime.date():
            if current_time <= now_datetime:
                current_time += step
                continue

        slot_end_time = current_time + step
        
        if slot_end_time > end_datetime:
            break
            
        # --- Integration Step 2 & 3: Check Concurrent Bookings ---
        # Determine how many guests are already booked in this specific slot
        booked_count = get_concurrent_guests(
            employee=employee, 
            check_datetime=current_time,
        )
        
        remaining_capacity = customers_capacity - booked_count

        # --- Integration Step 4: Filtering ---
        slot = {
            "value": current_time.strftime("%H:%M:%S"),
            "available": remaining_capacity > 0
        }
        available_times.append(slot)
        
        current_time += step
        
    return {"times": available_times, "duration": duration_seconds}


@frappe.whitelist()
def get_service_employees(service_id: str):
    employees = frappe.get_all(
        "Service Employee",
        filters={"parent": service_id},
        fields=["employee"],
    )
    emp_names = []
    for emp in employees:
        emp_names.append(emp.employee)

    return emp_names


@frappe.whitelist()
def get_end_date(start_date: str, duration: int):
    ## Convert date string to datetime
    if isinstance(start_date, str):
        date_obj = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
    else:
        date_obj = date

    step = timedelta(seconds=duration)

    end_date = date_obj + step

    return end_date.strftime("%Y-%m-%d %H:%M:%S")


@frappe.whitelist()
def set_package_appointments(
    department_id,
    service_id,
    employee_id,
    selected_date,
    start_time,
    end_time,
):
    package = frappe.get_doc("Item", service_id)
    if not package.is_package:
        return {"success": True}

    if isinstance(selected_date, str):
        date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
    else:
        # If date is already a datetime object
        date_obj = selected_date

    weekday = date_obj.weekday()

    for item in package.child_items:
        service = frappe.get_doc("Item", item.item)
        department = service.item_group

    ## Get employee shift settings
    filters = {
        "employee": employee_id,
        "department": department_id,
        "weekday": str(weekday),
    }
    appointment_settings = frappe.get_all(
        "Appointment Setting",
        filters=filters,
        fields=["name", "customers_capacity", "duration", "from", "to"]
    )

import frappe


@frappe.whitelist()
def get_appointments_on_date(customer, selected_date, exclude_name=None):
    filters = {
        "customer": customer,
        "selected_date": selected_date,
    }
    if exclude_name:
        filters["name"] = ("!=", exclude_name)

    apps = frappe.get_all(
        "Appointment",
        filters=filters,
        fields=["name", "service", "employee", "scheduled_time", "scheduled_end_time", "status", "color"],
        order_by="scheduled_time asc",
    )

    for app in apps:
        app.service_name = frappe.get_value("Item", app.service, "item_name")

    return apps

