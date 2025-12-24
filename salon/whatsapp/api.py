import frappe
from datetime import datetime, timedelta
from salon.appointment_api import get_available_times
import json
import math

def normalize_saudi_mobile(mobile: str) -> dict:
    mobile = mobile.strip().replace(" ", "").replace("-", "")

    if mobile.startswith("966"):
        core = mobile[-9:]
    elif mobile.startswith("05"):
        core = mobile[2:]
    elif mobile.startswith("5"):
        core = mobile
    else:
        core = mobile[-9:]

    return {
        "core": core,
        "966": f"966{core}",
        "05": f"05{core}",
        "5": core,
    }


@frappe.whitelist(allow_guest=True, methods=["POST"])
def webhook():
    def normalize_rating(rating: float) -> float:
        return {
            1.0: 0.2,
            2.0: 0.4,
            3.0: 0.6,
            4.0: 0.8,
            5.0: 1.0,
        }[rating]

    wa_settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
    try:
        # raw_body = frappe.request.data
        raw_data = frappe.request.get_data(as_text=True)
        data = json.loads(raw_data)

        interactive = data.get("interactive")
        message_type = interactive.get("type")
        if message_type == "list_reply":
            reply = interactive.get("list_reply")
            reply_id = reply.get("id")
            reply_title = reply.get("title")
            reply_description = reply.get("description")

            review_id = reply_id.split("_")[0]
            rating = float(reply_id.split("_")[1])

            review = frappe.get_value("Service Review", {"name": review_id, "status": "Pending"})
            if review:
                review_doc = frappe.get_doc("Service Review", review_id)
                review_doc.rating = normalize_rating(rating)
                review_doc.rating_number = int(rating)
                review_doc.description = reply_description
                review_doc.status = "Reviewed"
                review_doc.save(ignore_permissions=True)
        
                return {"success": True, "body": data, "review_id": review_doc.name, "rating": normalize_rating(rating)}
    
    except Exception as e:
        frappe.throw(str(e))


@frappe.whitelist(methods=["GET"])
def check_customer(mobile_number: str):
    try:
        numbers = normalize_saudi_mobile(mobile_number)

        customers = frappe.get_list(
            "Customer",
            filters={
                "mobile_no": ["in", [numbers["966"], numbers["05"], numbers["5"]]]
            },
            fields=["name", "customer_name", "email_id", "mobile_no", "gender"]
        )

        if customers:
            frappe.response["customers"] = customers
            return
        
        else:
            frappe.response["message"] = "Customer not registered with this mobile number."
            return
        
    except Exception as e:
        frappe.response["message"] = f"Failed to check customer against the database: {e}"
        return
    


@frappe.whitelist(methods=["POST"])
def create_customer(first_name: str, middle_name: str, last_name: str, mobile_number: str):
    try:
        customers = frappe.get_list(
            "Customer",
            filters={"mobile_no": mobile_number, "customer_name": ["like", f"%{first_name} {middle_name} {last_name}%"]},
            fields=["customer_name", "email_id", "mobile_no", "gender"]
        )

        if customers:
            frappe.response["message"] = "Customer already registered with this mobile number."
            return

        else:
            customer = frappe.new_doc("Customer")
            customer.customer_name = f"{first_name} {middle_name} {last_name}"
            customer.mobile_no = mobile_number
            customer.customer_type = "Individual"
            customer.insert()
            
            frappe.response["message"] = "Customer created successfully"
            return
        
    except Exception as e:
        frappe.response["message"] = f"Failed to create customer: {e}"
        return
        
    

@frappe.whitelist(methods=["GET"])
def get_appointments(customer_id: str, from_date: str, to_date: str):
    try:
        appointments = frappe.get_list(
            "Appointment",
            filters=[
                ["Appointment", "customer", "=", customer_id],
                ["Appointment", "status", "=", "Open"],
                ["Appointment", "selected_date", ">=", from_date],
                ["Appointment", "selected_date", "<=", to_date],
            ],
            fields=["department", "employee", "scheduled_time", "scheduled_end_time"],
        )
        for app in appointments:
            employee_name = frappe.db.get_value("Employee", app.employee, "employee_name")
            app.employee = employee_name

        frappe.response["my_appointments"] = appointments
        return
    
    except Exception as e:
        frappe.response["message"] = f"Failed to fetch appointments: {e}"
        return
    


@frappe.whitelist(methods=["POST"])
def create_appointment(
    department: str,
    employee: str,
    selected_date: str,
    selected_time: str,
    customer_name: str,
    customer_mobile_number: str,
):
    try:
        customer_id = frappe.get_value(
            "Customer",
            {"customer_name": customer_name, "mobile_no": customer_mobile_number},
        )
        if not customer_id:
            frappe.response["message"] = f"({customer_name}) customer with mobile number ({customer_mobile_number}) is not registered."
            return
        
        date = datetime.strptime(selected_date, "%Y-%m-%d")
        weekday = date.weekday()

        app_settings = frappe.get_list(
            "Appointment Setting",
            filters = {
                "employee": employee,
                "department": department,
                "weekday": str(weekday),
            },
            fields=["name", "customers_capacity", "duration", "from", "to"]
        )

        if not app_settings:
            frappe.response["message"] = f"The employee is not available on {selected_date} {selected_time}"
            return
        
        duration_seconds = app_settings[0].duration
        start_datetime = datetime.strptime(f"{selected_date} {selected_time}", "%Y-%m-%d %H:%M:%S")
        end_datetime = start_datetime + timedelta(seconds=duration_seconds)

        appointment = frappe.new_doc("Appointment")
        appointment.department = department
        appointment.employee = employee
        appointment.selected_date = selected_date
        appointment.scheduled_time = f"{selected_date} {selected_time}"
        appointment.scheduled_end_time = end_datetime
        appointment.customer = customer_id
        appointment.customer_name = customer_name
        appointment.customer_phone_number = customer_mobile_number
        appointment.appointment_with = "Customer"
        appointment.party = customer_id
        appointment.insert()
        
        frappe.response["message"] = f"New appointment created successfully on {selected_date} {selected_time}"
        return
    
    except Exception as e:
        frappe.response["message"] = f"Failed to create a new appointment: {e}"
        return


@frappe.whitelist(methods=["GET"])
def get_departments():
    try:
        departments = frappe.get_list(
            "Item Group",
            filters={
                "parent_item_group": ["in", ["Services", "الشعر", "هايلايت وتقنيات الصبغة"]],
                "name": ["!=", "الشعر"],
            },
            limit=0,
        )
        deps = []
        for dep in departments:
            deps.append(dep.name)

        frappe.response["departments"] = deps
        return
    
    except Exception as e:
        frappe.response["message"] = f"Failed to fetch departments: {e}"
        return


@frappe.whitelist(methods=["GET"])
def get_all_services(language: str="ar"):
    try:
        fields = ["name"]

        if language == "ar":
            fields.append("item_name_in_arabic")
            fields.append("description_in_arabic")
        else:
            fields.append("description")


        services = frappe.get_list(
            "Item",
            fields=fields,
            limit=0,
        )

        for service in services:
            item_price = frappe.get_list(
                "Item Price",
                filters={"item_code": service.name, "selling": 1},
                fields=["price_list_rate"],
                limit=1,
            )
            if item_price:
                service.vat_exclusive_price = item_price[0].price_list_rate
            else:
                service.vat_exclusive_price = "Unspecified"

        frappe.response["services"] = services
        return
    
    except Exception as e:
        frappe.response["message"] = f"Failed to fetch services: {e}"
        return
    

@frappe.whitelist(methods=["GET"])
def get_services_by_department(department: str, language: str="ar"):
    try:
        fields = ["name"]

        if language == "ar":
            fields.append("item_name_in_arabic")
            fields.append("description_in_arabic")
        else:
            fields.append("description")

        services = frappe.get_list(
            "Item",
            filters={
                "item_group": department,
            },
            fields=fields,
            limit=0,
        )

        for service in services:
            item_price = frappe.get_list(
                "Item Price",
                filters={"item_code": service.name, "selling": 1},
                fields=["price_list_rate"],
                limit=1,
            )
            if item_price:
                service.vat_exclusive_price = item_price[0].price_list_rate
            else:
                service.vat_exclusive_price = "Unspecified"

        frappe.response["services"] = services
        return
    
    except Exception as e:
        frappe.response["message"] = f"Failed to fetch services: {e}"
        return


@frappe.whitelist(methods=["GET"])
def get_all_employees():
    try:
        employees = frappe.get_list(
            "Employee",
            fields=["employee_name"],
            limit=0,
        )
        
        frappe.response["employees"] = employees
        return
    
    except Exception as e:
        frappe.response["message"] = f"Failed to fetch employees: {e}"
        return
    

@frappe.whitelist(methods=["GET"])
def get_employees_by_department(department: str):
    try:
        selected_department = frappe.get_doc("Item Group", department)
        
        employees_table = selected_department.employees

        employees = []
        for emp in employees_table:
            employees.append({"ID": emp.employee, "Name": emp.employee_name})
            
        
        frappe.response["employees"] = employees
        return
    
    except Exception as e:
        frappe.response["message"] = f"Failed to fetch employees: {e}"
        return



@frappe.whitelist(methods=["GET"])
def get_times(date: str, department: str, employee: str):
    try:
        leaves = frappe.get_list(
            "Leave Application",
            filters={
                "employee": employee,
                "status": "Approved",
                "from_date": ["<=", date],
                "to_date": [">=", date],
            }
        )
        if leaves:
            employee_name = frappe.db.get_value("Employee", employee, "employee_name")
            frappe.response["message"] = f"{employee_name} is not available on {date}"
            return
        
        else:
            times = get_available_times(
                current_appointment_id="None",
                date=date,
                department=department,
                employee=employee,
            )["times"]

            if not times:
                frappe.response["message"] = f"no available times on {date}"
                return
            
            av_times = []
            for time in times:
                if time.get("available"):
                    av_times.append(time.get("value"))

            frappe.response["available_times"] = av_times
            return
    
    except Exception as e:
        frappe.response["message"] = f"Failed to fetch available times: {e}"
        return