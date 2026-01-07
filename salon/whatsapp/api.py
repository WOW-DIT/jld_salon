import frappe
from datetime import datetime, timedelta
from salon.appointment_api import get_available_times
import json
import math
import requests

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


@frappe.whitelist(methods=["POST"])
def webhook():
    def normalize_rating(rating: float) -> float:
        return {
            1.0: 0.2,
            2.0: 0.4,
            3.0: 0.6,
            4.0: 0.8,
            5.0: 1.0,
        }[rating]

    def handle_error(err):
        def halt_broadcasting():
            broadcasts = frappe.get_list(
                "WhatsApp Message Broadcast",
                filters={"sending_status": "Sending", "cancel_requested": 0}
            )
            for b in broadcasts:
                broadcast = frappe.get_doc("WhatsApp Message Broadcast", b.name)
                broadcast.sending_status = "Failed"
                broadcast.cancel_requested = 1
                broadcast.failure_reason = error_title
                # broadcast.completed_numbers = broadcast.completed_numbers.replace(f"{user_number}\n", "\n")
                broadcast.save()
            frappe.db.commit()


        error_code = err.get("code")
        error_title = err.get("title")

        ## Payment error
        if error_code == 131042:
            halt_broadcasting()

        # Rate Limit Error
        elif error_code in [80007, 130429, 131048]:
            halt_broadcasting()

    wa_settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
    try:
        # raw_body = frappe.request.data
        raw_data = frappe.request.get_data(as_text=True)
        data = json.loads(raw_data)
        instance_id = data.get("whatsapp_instance_id")

        note = frappe.new_doc("Note")
        note.title = "WHATSAPP LOG (55555555555555)"
        note.type = "External"
        note.public = 1
        note.content = str(data)
        note.insert(ignore_permissions=True)
        frappe.db.commit()

        whatsapp_number_id = frappe.db.get_value("WhatsApp Number", {"instance_id": instance_id})
        if not whatsapp_number_id:
            return
        
        event = data.get("event")
        user_number = data.get("user_number")
        
        if event == "interactive":
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

        elif event == "errors":
            errors = data.get("errors")

            for err in errors:
                handle_error(err)

    except Exception as e:
        note = frappe.new_doc("Note")
        note.title = "WhatsApp ERROR"
        note.content = str(e)
        note.public = 1
        note.insert(ignore_permissions=True)
        return
    
        frappe.throw(str(e))


@frappe.whitelist(methods=["GET"])
def get_whatsapp_rate_limit(whatsapp_number_id):
    wa_settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
    wa_number = frappe.get_doc("WhatsApp Number", whatsapp_number_id)
    instance_id = wa_number.instance_id

    wa_settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
    api_base_url = wa_settings.api_url
    api_key = wa_settings.get_password("api_key")

    url = f"{api_base_url}/whatsapp_integration.whatsapp_api.get_whatsapp_rate_limit"
    request_body = {
        "instance_id": instance_id
    }
    headers = {
        "Authorization": f"Basic {api_key}"
    }
    response = requests.post(url, headers=headers, json=request_body, timeout=20)

    if response.status_code == 200:
        data = response.json()
        status = data.get("status")
        success = data.get("success")
        if success:
            message = data.get("message")
            rate_limit = message.get("whatsapp_business_manager_messaging_limit")
            return {
                "value": int(rate_limit.split("_")[1]),
                "fieldtype": "Int",
            }
        
        frappe.throw(response.json())


@frappe.whitelist()
def whatsapp_messaging_limit_card():
    return get_whatsapp_rate_limit("Main Number")


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
            frappe.response.update({
                "success": True,
                "customers": customers
            })
            return
        
        else:
            frappe.response.update({
                "success": False,
                "message": "Customer not registered with this mobile number."
            })
            return
        
    except Exception as e:
        frappe.response.update({
            "success": False,
            "message": f"Failed to get customer: {e}"
        })
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
            frappe.response.update({
                "success": False,
                "message": "Customer already registered with this mobile number."
            })
            return

        else:
            customer = frappe.new_doc("Customer")
            customer.customer_name = f"{first_name} {middle_name} {last_name}"
            customer.mobile_no = mobile_number
            customer.customer_type = "Individual"
            customer.insert()
            
            frappe.response.update({
                "success": True,
                "message": "Customer created successfully"
            })
            return
        
    except Exception as e:
        frappe.response.update({
            "success": False,
            "message": f"Failed to create customer: {e}"
        })
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

        frappe.response.update({
            "success": True,
            "departments": deps
        })
        return
    
    except Exception as e:
        frappe.response.update({
            "success": False,
            "message": f"Failed to fetch departments: {e}"
        })
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

        frappe.response.update({
            "success": True,
            "services": services
        })
        return
    
    except Exception as e:
        frappe.response.update({
            "success": False,
            "message": f"Failed to fetch services: {e}"
        })
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

        frappe.response.update({
            "success": True,
            "services": services
        })
        return
    
    except Exception as e:
        frappe.response.update({
            "success": False,
            "message": f"Failed to fetch services: {e}"
        })
        return


@frappe.whitelist(methods=["GET"])
def get_all_employees():
    try:
        employees = frappe.get_list(
            "Employee",
            fields=["employee_name"],
            limit=0,
        )
        
        frappe.response.update({
            "success": True,
            "employees": employees
        })
        return
    
    except Exception as e:
        frappe.response.update({
            "success": False,
            "message": f"Failed to fetch employees: {e}"
        })
        return
    

@frappe.whitelist(methods=["GET"])
def get_employees_by_department(department: str):
    try:
        selected_department = frappe.get_doc("Item Group", department)
        
        employees_table = selected_department.employees

        employees = []
        for emp in employees_table:
            employees.append({"ID": emp.employee, "Name": emp.employee_name})
                    
        frappe.response.update({
            "success": True,
            "employees": employees
        })
        return
    
    except Exception as e:
        frappe.response.update({
            "success": False,
            "message": f"Failed to fetch employees: {e}"
        })
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
            frappe.response.update({
                "success": True,
                "message": f"{employee_name} is not available on {date}"
            })
            return
        
        else:
            times = get_available_times(
                current_appointment_id="None",
                date=date,
                department=department,
                employee=employee,
            )["times"]

            if not times:
                frappe.response.update({
                    "success": False,
                    "message": f"no available times on {date}"
                })
                return
            
            av_times = []
            for time in times:
                if time.get("available"):
                    av_times.append(time.get("value"))

            frappe.response.update({
                "success": True,
                "available_times": av_times
            })
            return
    
    except Exception as e:
        frappe.response.update({
            "success": False,
            "message": f"Failed to fetch available times: {e}"
        })
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

        frappe.response.update({
            "success": True,
            "my_appointments": appointments
        })
        return
    
    except Exception as e:
        frappe.response.update({
            "success": False,
            "message": f"Failed to fetch appointments: {e}"
        })
        return


@frappe.whitelist(methods=["GET"])
def get_appointment_details(appointment_id: str):
    try:
        if not frappe.db.exists("Appointment", appointment_id):
            frappe.response.update({
                "success": False,
                "message": f"The appointment with id **{appointment_id}** was not found"
            })
            return

        appointment = frappe.get_doc("Appointment", appointment_id)
        employee = frappe.get_doc("Employee", appointment.employee)

        frappe.response.update({
            "success": True,
            "appointment_details": {
                "name": appointment.name,
                "employee_id": employee.name,
                "employee_name": employee.employee_name,
                "date": appointment.selected_date,
                "start_time": appointment.scheduled_time,
                "end_time": appointment.scheduled_end_time,
                "status": appointment.status,
            }
        })
        return
    
    except Exception as e:
        frappe.response.update({
            "success": False,
            "message": f"Failed to get appointment details: {e}"
        })
        return


@frappe.whitelist(methods=["POST"])
def get_payment_link(
    department: str,
    employee: str,
    selected_date: str,
    selected_time: str,
    customer_name: str,
    email: str,
    customer_mobile_number: str,
):
    try:
        first_name = customer_name.split(" ")[0]
        last_name = customer_name.split(" ")[1]

        deposit_item = frappe.get_doc("Item", "Customer Deposit - 001")
        deposit_price = frappe.get_value("Item Price", {"item_code": deposit_item.name}, "price_list_rate")

        whatsapp_settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
        api_base_url = whatsapp_settings.api_url
        api_key = whatsapp_settings.get_password("api_key")

        # whatsapp_number = frappe.get_doc("WhatsApp Number", whatsapp_settings.default_review_number)

        url = f"{api_base_url}/connectly.payment_api.intention"

        headers = {"Authorization": f"Basic {api_key}"}
        payload = {
            "total_amount": deposit_price,
            "items": [
                {
                    "name": "Deposit",
                    "amount": deposit_price,
                }
            ],
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone_number": customer_mobile_number,
            "notification_url": "https://jeanlouisdavidsa.cloud/api/method/salon.payment_api.payment_webhook",
            "redirection_url": "https://www.google.com",
            "extras": {
                "action": "create_appointment",
                "department": department,
                "employee": employee,
                "selected_date": selected_date,
                "selected_time": selected_time,
                "customer_name": customer_name,
                "mobile_number": customer_mobile_number,
            },
        }

        response = requests.post(url, headers=headers, json=payload, timeout=15)
    
        if response.status_code == 200:
            body = response.json()
            data = body.get("message")
            success = data.get("success")
            
            if success:
                frappe.response.update({
                    "success": True,
                    "payment_url": data.get("url"),
                })
                return
            
            else:
                frappe.response.update({
                    "success": False,
                    "message": data.get("error"),
                })
                return
            
        frappe.response.update({
            "success": False,
            "message": response.text,
        })
        return

    
    except Exception as e:
        frappe.response.update({
            "success": False,
            "message": f"Failed get payment link: {e}"
        })
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
            frappe.response.update({
                "success": False,
                "message": f"({customer_name}) customer with mobile number ({customer_mobile_number}) is not registered."
            })
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
            frappe.response.update({
                "success": False,
                "message": f"The employee is not available on {selected_date} {selected_time}"
            })
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

        frappe.db.commit()
        frappe.response.update({
            "success": True,
            "appointment_id": appointment.name,
        })
        return
    
    except Exception as e:
        frappe.response.update({
            "success": False,
            "message": f"Failed to create a new appointment: {e}"
        })
        return



@frappe.whitelist(methods=["POST"])
def update_appointment(
    appointment_id: str,
    department: str=None,
    employee: str=None,
    selected_date: str=None,
    selected_time: str=None,
):
    try:
        if not frappe.db.exists("Appointment", appointment_id):
            frappe.response.update({
                "success": False,
                "message": f"The appointment with id **{appointment_id}** was not found"
            })
            return
    
        if selected_date and selected_time:
            date = datetime.strptime(selected_date, "%Y-%m-%d")
            weekday = date.weekday()

            appointment_settings = frappe.get_list(
                "Appointment Setting",
                filters = {
                    "employee": employee,
                    "department": department,
                    "weekday": str(weekday),
                },
                fields=["name", "customers_capacity", "duration", "from", "to"]
            )

            if not appointment_settings:
                frappe.response.update({
                    "success": False,
                    "message": f"The employee is not available on {selected_date} {selected_time}"
                })
                return
        
        duration_seconds = appointment_settings[0].duration
        start_datetime = datetime.strptime(f"{selected_date} {selected_time}", "%Y-%m-%d %H:%M:%S")
        end_datetime = start_datetime + timedelta(seconds=duration_seconds)

        appointment = frappe.get_doc("Appointment", appointment_id)

        if department:
            appointment.department = department
        if employee:
            appointment.employee = employee

        if selected_date and selected_time:
            appointment.selected_date = selected_date
            appointment.scheduled_time = f"{selected_date} {selected_time}"
            appointment.scheduled_end_time = end_datetime

        appointment.save()

        frappe.response.update({
            "success": True,
            "message": f"Appointment **{appointment.name}** updated successfully"
        })
        return
    
    except Exception as e:
        frappe.response.update({
            "success": False,
            "message": f"Failed to create a new appointment: {e}"
        })
        return


@frappe.whitelist(methods=["POST"])
def cancel_appointment(appointment_id: str):
    try:
        if not frappe.db.exists("Appointment", appointment_id):
            frappe.response.update({
                "success": False,
                "message": f"The appointment with id **{appointment_id}** was not found"
            })
            return
        
        appointment = frappe.get_doc("Appointment", appointment_id)
        appointment.status = "Cancelled"
        appointment.save()
        frappe.db.commit()

        frappe.response.update({
            "success": True,
            "message": f"Appointment **{appointment.name}** was cancelled"
        })
        return

    except Exception as e:
        frappe.response.update({
            "success": False,
            "message": f"Failed to cancel appointment: {e}"
        })
        return