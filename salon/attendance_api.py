import frappe
import datetime

# @frappe.whitelist(allow_guest=True, methods=["POST"])
# def webhook(
#     user_id: str,
#     timestamp: str,
#     status: int,
#     punch: int,
#     type: str,
#     device_id: str=None,
# ):
#     employee = frappe.get_value("Employee", {"attendance_device_id": user_id})

#     if not employee:
#         frappe.throw(f"Employee with User ID ({user_id}) not found")

#     check_in_out = frappe.new_doc("Employee Checkin")
#     check_in_out.employee = employee
#     check_in_out.time = timestamp
#     check_in_out.log_type = "IN" if punch == 1 else "OUT"
#     check_in_out.device_id = device_id
#     check_in_out.insert(ignore_permissions=True)
#     frappe.db.commit()

#     frappe.response.update({
#         "success": True
#     })
#     return

def _update_shift_last_checkin(shift_type, timestamp):
    if not shift_type:
        return
    current = frappe.db.get_value("Shift Type", shift_type, "last_sync_of_checkin")
    frappe.db.set_value(
        "Shift Type",
        shift_type,
        "last_sync_of_checkin",
        timestamp,
        update_modified=False,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def webhook(
    attendance: list,
    device_id: str=None,
):
    result = []
    
    for att in attendance:
        user_id = att.get("user_id")
        timestamp = att.get("timestamp")
        status = att.get("status")
        punch = att.get("punch")
        type = att.get("type")
        
        employee = frappe.get_value("Employee", {"attendance_device_id": user_id})

        if not employee:
            result.append({
                "success": False,
                "user_id": user_id,
                "timestamp": timestamp,
                "error": f"Employee with User ID ({user_id}) not found",
            })
            continue
        try:
            log_type = "IN" if punch == 0 else "OUT"
            if frappe.db.exists(
                "Employee Checkin",
                {
                    "employee": employee,
                    "time": timestamp,
                    "device_id": device_id,
                    "log_type": log_type,
                },
            ):
                result.append({
                    "success": True,
                    "user_id": user_id,
                    "timestamp": timestamp,
                    "duplicate": True
                })
                continue

            check_in_out = frappe.new_doc("Employee Checkin")
            check_in_out.employee = employee
            check_in_out.time = timestamp
            check_in_out.log_type = log_type
            check_in_out.device_id = device_id
            check_in_out.insert(ignore_permissions=True)

            _update_shift_last_checkin(check_in_out.shift, timestamp)

            result.append({
                "success": True,
                "user_id": user_id,
                "timestamp": timestamp,
            })

        except Exception as e:
            result.append({
                "success": False,
                "user_id": user_id,
                "timestamp": timestamp,
                "error": str(e),
            })
            continue

        frappe.db.commit()

    frappe.response.update({
        "result": result
    })
    return