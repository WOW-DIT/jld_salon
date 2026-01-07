import frappe
import datetime

@frappe.whitelist(allow_guest=True, methods=["POST"])
def webhook(
    user_id: str,
    timestamp: str,
    status: int,
    punch: int,
    type: str,
    device_id: str=None,
):
    employee = frappe.get_value("Employee", {"attendance_device_id": user_id})

    if not employee:
        frappe.throw(f"Employee with User ID ({user_id}) not found")

    check_in_out = frappe.new_doc("Employee Checkin")
    check_in_out.employee = employee
    check_in_out.time = timestamp
    check_in_out.log_type = "IN" if punch == 1 else "OUT"
    check_in_out.device_id = device_id
    check_in_out.insert(ignore_permissions=True)
    frappe.db.commit()

    frappe.response.update({
        "success": True
    })
    return