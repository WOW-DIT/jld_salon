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

    # --- Shift background blocks ---
    from datetime import datetime, timedelta

    # Extract employee from filters if provided
    filtered_employee = None
    raw_filters = json.loads(filters) if isinstance(filters, str) else (filters or [])
    for f in raw_filters:
        if isinstance(f, list) and len(f) >= 4 and f[1] == "employee" and f[3]:
            filtered_employee = f[3]
            break

    # Only draw shift blocks if a specific employee is selected
    if filtered_employee:
        employee_ids = [filtered_employee]

        start_dt = datetime.strptime(start[:10], "%Y-%m-%d").date()
        end_dt   = datetime.strptime(end[:10],   "%Y-%m-%d").date()

        for employee in employee_ids:
            current = start_dt
            while current <= end_dt:
                weekday = current.weekday()
                shift_start_time = None
                shift_end_time   = None

                employee_times = frappe.get_value(
                    "Employee Appointment Times",
                    {"employee": employee},
                    ["name", "start_time", "end_time"],
                    as_dict=True,
                )
                if employee_times:
                    shift_start_time = employee_times.start_time
                    shift_end_time   = employee_times.end_time
                else:
                    shift_assignment = frappe.get_value(
                        "Shift Assignment",
                        {
                            "employee": employee,
                            "status": "Active",
                            "docstatus": 1,
                            "start_date": ["<=", current],
                            "end_date": [">=", current],
                            "weekday": int(weekday),
                        },
                        ["name", "shift_type"],
                        as_dict=True,
                    )
                    if shift_assignment:
                        shift_type = frappe.get_value(
                            "Shift Type",
                            shift_assignment.shift_type,
                            ["name", "start_time", "end_time"],
                            as_dict=True,
                        )
                        if shift_type:
                            shift_start_time = shift_type.start_time
                            shift_end_time   = shift_type.end_time

                if shift_start_time and shift_end_time:
                    events.append(frappe._dict({
                        "name":      f"shift-bg-{employee}-{current}",
                        "title":     "",
                        "start":     f"{current}T{str(shift_start_time)}",
                        "end":       f"{current}T{str(shift_end_time)}",
                        "rendering": "background",
                        "color":     "#d4f1d4",
                    }))

                current += timedelta(days=1)

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
    department: str,
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


    # def get_concurrent_guests(employee: str, check_datetime: datetime):
    #     """
    #     Counts overlapping appointments for the same employee in the same department,
    #     regardless of service — blocking the slot if any overlap exists.
    #     """
    #     proposed_start = check_datetime
    #     proposed_end = proposed_start + timedelta(seconds=duration_seconds)

    #     proposed_start_str = proposed_start.strftime("%Y-%m-%d %H:%M:%S")
    #     proposed_end_str = proposed_end.strftime("%Y-%m-%d %H:%M:%S")

    #     # Find any Open appointments for this employee+department that overlap
    #     # with [proposed_start, proposed_end), excluding the current appointment
    #     # and excluding appointments for the exact same service (already handled by capacity)
    #     overlapping = frappe.db.count(
    #         "Appointment",
    #         filters={
    #             "name": ["!=", current_appointment_id],
    #             "employee": employee,
    #             "department": department,
    #             "service": ["!=", service_id],        # different service only
    #             "status": "Open",
    #             "scheduled_time": ["<", proposed_end_str],    # other appt starts before our slot ends
    #             "scheduled_end_time": [">", proposed_start_str],  # other appt ends after our slot starts
    #         }
    #     )

    #     # Also count same-service bookings (original capacity logic)
    #     same_service_booked = frappe.db.count(
    #         "Appointment",
    #         filters={
    #             "name": ["!=", current_appointment_id],
    #             "employee": employee,
    #             "service": service_id,
    #             "status": "Open",
    #             "scheduled_time": proposed_start_str,
    #         }
    #     )

    #     # If any cross-service overlap exists, treat slot as fully booked
    #     if overlapping > 0:
    #         return customers_capacity  # forces remaining_capacity = 0

    #     return same_service_booked

    # def get_concurrent_guests(employee: str, check_datetime: datetime):
    #     """
    #     Counts all overlapping appointments for this employee across all services,
    #     then returns the total so the caller can compare against customers_capacity.
    #     """
    #     proposed_start = check_datetime
    #     if isinstance(proposed_start, str):
    #         proposed_start = datetime.strptime(proposed_start, "%Y-%m-%d %H:%M:%S")

    #     proposed_end = proposed_start + timedelta(seconds=duration_seconds)

    #     proposed_start_str = proposed_start.strftime("%Y-%m-%d %H:%M:%S")
    #     proposed_end_str   = proposed_end.strftime("%Y-%m-%d %H:%M:%S")

    #     # Count every overlapping Open appointment for this employee,
    #     # regardless of service — overlap means:
    #     #   other.start < our.end  AND  other.end > our.start
    #     total_booked = frappe.db.count(
    #         "Appointment",
    #         filters={
    #             "name": ["!=", current_appointment_id],
    #             "employee": employee,
    #             "status": "Open",
    #             "department": department,
    #             "scheduled_time": ["<",  proposed_end_str],
    #             "scheduled_end_time": [">",  proposed_start_str],
    #         }
    #     )

    #     return total_booked

    def get_dep_concurrent_guests(employee: str, check_datetime: datetime):
        """
        Counts all overlapping appointments for this employee across all services,
        then returns the total so the caller can compare against customers_capacity.
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
                "name": ["!=", current_appointment_id],
                "employee": employee,
                "status": ["in", ["Open", "Closed"]],
                "department": department,
                "scheduled_time": ["<",  proposed_end_str],
                "scheduled_end_time": [">",  proposed_start_str],
            }
        )

        return total_booked
    
    def get_diff_dep_concurrent_guests(employee: str, check_datetime: datetime):
        """
        Counts all overlapping appointments for this employee across all services,
        then returns the total so the caller can compare against customers_capacity.
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
            deps = [dep["department"] for dep in overlapping_departments] + [department]

            total_booked = frappe.db.count(
                "Appointment",
                filters={
                    "name": ["!=", current_appointment_id],
                    "employee": employee,
                    "status": ["in", ["Open", "Closed"]],
                    "department": ["not in", deps],
                    "scheduled_time": ["<",  proposed_end_str],
                    "scheduled_end_time": [">",  proposed_start_str],
                }
            )
        else:
            # Count every overlapping Open appointment for this employee,
            # regardless of service — overlap means:
            #   other.start < our.end  AND  other.end > our.start
            total_booked = frappe.db.count(
                "Appointment",
                filters={
                    "name": ["!=", current_appointment_id],
                    "employee": employee,
                    "status": ["in", ["Open", "Closed"]],
                    "department": ["!=", department],
                    "scheduled_time": ["<",  proposed_end_str],
                    "scheduled_end_time": [">",  proposed_start_str],
                }
            )

        return total_booked
    

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

    employee_times = frappe.get_value(
        "Employee Appointment Times",
        {
            "employee": employee,
            "start_date": ["<=", date],
            "end_date": [">=", date],
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
        
    setting = appointment_settings[0]
    setting["from"] = start_time
    setting["to"] = end_time

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
        dep_booked_count = get_dep_concurrent_guests(
            employee=employee, 
            check_datetime=current_time,
        )
        
        remaining_capacity = customers_capacity - dep_booked_count
        if remaining_capacity == 0:
            # --- Integration Step 4: Filtering ---
            slot = {
                "value": current_time.strftime("%H:%M:%S"),
                "available": False
            }

        else:
            diff_dep_booked_count = get_diff_dep_concurrent_guests(
                employee=employee, 
                check_datetime=current_time,
            )

            slot = {
                "value": current_time.strftime("%H:%M:%S"),
                "available": diff_dep_booked_count == 0
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


@frappe.whitelist()
def attend_all(date, customer):
    try:
        apps = frappe.get_list(
            "Appointment",
            filters={
                "selected_date": date,
                "customer": customer,
                "status": ["in", ["Open", "Waiting"]],
            }
        )
        for app in apps:
            frappe.set_value("Appointment", app.name, "workflow_state", "Attended")
            frappe.set_value("Appointment", app.name, "status", "Closed")

            frappe.db.commit()

        return {
            "success": True
        }
    
    except Exception as e:
        return {
            "success": False
        }