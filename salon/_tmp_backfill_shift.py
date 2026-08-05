import frappe
from frappe.utils import get_datetime
from hrms.hr.doctype.shift_assignment.shift_assignment import get_actual_start_end_datetime_of_shift


def run():
    rows = frappe.db.sql(
        """select name, employee, time, attendance
           from `tabEmployee Checkin`
           where shift is null or shift = ''""",
        as_dict=True,
    )
    total = len(rows)
    fixed = 0
    skipped_no_shift = 0
    skipped_has_attendance = 0
    errors = 0

    for i, row in enumerate(rows):
        if row.attendance:
            skipped_has_attendance += 1
            continue
        try:
            shift_actual_timings = get_actual_start_end_datetime_of_shift(
                row.employee, get_datetime(row.time), True
            )
        except Exception:
            errors += 1
            continue

        if not shift_actual_timings:
            skipped_no_shift += 1
            continue

        frappe.db.set_value(
            "Employee Checkin",
            row.name,
            {
                "shift": shift_actual_timings.shift_type.name,
                "shift_actual_start": shift_actual_timings.actual_start,
                "shift_actual_end": shift_actual_timings.actual_end,
                "shift_start": shift_actual_timings.start_datetime,
                "shift_end": shift_actual_timings.end_datetime,
            },
            update_modified=False,
        )
        fixed += 1

        if (i + 1) % 500 == 0:
            frappe.db.commit()
            print(
                f"progress: {i + 1}/{total} fixed={fixed} "
                f"skipped_no_shift={skipped_no_shift} "
                f"skipped_has_attendance={skipped_has_attendance} errors={errors}"
            )

    frappe.db.commit()
    print(
        f"done: total={total} fixed={fixed} "
        f"skipped_no_shift={skipped_no_shift} "
        f"skipped_has_attendance={skipped_has_attendance} errors={errors}"
    )
