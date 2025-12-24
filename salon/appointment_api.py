import frappe
from datetime import datetime, timedelta, time

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
def get_available_times(current_appointment_id: str, date: str, department: str, employee: str):

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


    ## Get employee shift settings
    filters = {
        "employee": employee,
        "department": department,
        "weekday": str(weekday),
    }
    appointment_settings = frappe.get_all(
        "Appointment Setting",
        filters=filters,
        fields=["name", "customers_capacity", "duration", "from", "to"]
    )

    if not appointment_settings:
        return {"times": []}
    
    setting = appointment_settings[0]

    duration_seconds = int(setting.get("duration", 1800))
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

    
    # Loop through the time range, stepping by the appointment duration
    while current_time < end_datetime:
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