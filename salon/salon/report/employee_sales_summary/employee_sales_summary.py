# Copyright (c) 2026, salon and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from datetime import datetime


def execute(filters=None):
    if not filters:
        filters = {}

    if not filters.get("year"):
        frappe.throw(_("Please select a Year"))

    if filters.get("employee"):
        columns, data, message, chart = get_single_employee_report(filters)
    else:
        columns, data, message, chart = get_all_employees_report(filters)

    return columns, data, message, chart


def get_all_employees_report(filters):
    columns = [
        {"fieldname": "employee", "label": _("Employee"), "fieldtype": "Link", "options": "Employee", "width": 100},
        # {"fieldname": "employee_name", "label": _("Employee Name"), "fieldtype": "Data", "width": 200},
        {"fieldname": "total_sales", "label": _("Total Sales"), "fieldtype": "Currency", "width": 150},
        {"fieldname": "total_customers", "label": _("No. of Customers"), "fieldtype": "Int", "width": 140},
        {"fieldname": "total_services", "label": _("No. of Services"), "fieldtype": "Int", "width": 140}
    ]

    month_names = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]

    conditions = "WHERE YEAR(p.posting_date) = %(year)s AND p.docstatus = 1 AND pitem.employee IS NOT NULL AND pitem.employee != ''"

    if filters.get("month"):
        filters["month_num"] = month_names.index(filters.get("month")) + 1
        conditions += " AND MONTH(p.posting_date) = %(month_num)s"

    data = frappe.db.sql(f"""
        SELECT
            pitem.employee,
            emp.employee_name,
            SUM(pitem.amount) as total_sales,
            COUNT(DISTINCT p.customer) as total_customers,
            COUNT(DISTINCT CASE WHEN itm.is_service = 1 AND pitem.amount > 0 THEN pitem.item_code END) as total_services
        FROM `tabPOS Invoice Item` pitem
        INNER JOIN `tabPOS Invoice` p ON pitem.parent = p.name
        LEFT JOIN `tabEmployee` emp ON pitem.employee = emp.name
        LEFT JOIN `tabItem` itm ON pitem.item_code = itm.name
        {conditions}
        GROUP BY pitem.employee, emp.employee_name
        ORDER BY total_sales DESC
    """, filters, as_dict=1)

    chart = {
        "data": {
            "labels": [d.get("employee_name") or d.get("employee") for d in data],
            "datasets": [{"name": _("Total Sales"), "values": [d.get("total_sales") for d in data]}]
        },
        "type": "bar",
        "colors": ["#7cd6fd"]
    }

    return columns, data, None, chart


# --- VIEW 2: SINGLE EMPLOYEE MONTHLY + SERVICE BREAKDOWN ---
def get_single_employee_report(filters):
    year = int(filters.get("year"))
    employee = filters.get("employee")
    selected_month_name = filters.get("month")

    now = datetime.now()
    current_year = now.year
    current_month = now.month

    all_month_names = ["January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November", "December"]

    # Calculate month evaluation window boundaries
    if selected_month_name:
        start_m = all_month_names.index(selected_month_name) + 1
        end_m = start_m
    else:
        start_m = 1
        end_m = current_month if year == current_year else 12

    # 1. Fetch valid services sold by this employee within this month timeframe
    services_data = frappe.db.sql("""
        SELECT DISTINCT pitem.item_code, itm.item_name
        FROM `tabPOS Invoice Item` pitem
        INNER JOIN `tabPOS Invoice` p ON pitem.parent = p.name
        LEFT JOIN `tabItem` itm ON pitem.item_code = itm.name
        WHERE pitem.employee = %s 
          AND YEAR(p.posting_date) = %s 
          AND MONTH(p.posting_date) >= %s AND MONTH(p.posting_date) <= %s
          AND p.docstatus = 1
          AND itm.is_service = 1
          AND pitem.amount > 0
    """, (employee, year, start_m, end_m), as_dict=1)

    columns = [
        {"fieldname": "month", "label": _("Month"), "fieldtype": "Data", "width": 120},
        {"fieldname": "total_sales", "label": _("Total Sales"), "fieldtype": "Currency", "width": 130},
        {"fieldname": "total_customers", "label": _("No. of Customers"), "fieldtype": "Int", "width": 140},
        {"fieldname": "total_services", "label": _("No. of Services"), "fieldtype": "Int", "width": 140}
    ]

    for s in services_data:
        columns.append({
            "fieldname": frappe.scrub(s.item_code),
            "label": s.item_name or s.item_code,
            "fieldtype": "Currency",
            "width": 150
        })

    # 2. Fetch raw transactions within the defined boundaries
    raw_data = frappe.db.sql("""
        SELECT 
            MONTH(p.posting_date) as month_num,
            pitem.item_code,
            SUM(pitem.amount) as amount
        FROM `tabPOS Invoice Item` pitem
        INNER JOIN `tabPOS Invoice` p ON pitem.parent = p.name
        LEFT JOIN `tabItem` itm ON pitem.item_code = itm.name
        WHERE pitem.employee = %s 
          AND YEAR(p.posting_date) = %s 
          AND MONTH(p.posting_date) >= %s AND MONTH(p.posting_date) <= %s
          AND p.docstatus = 1
          AND itm.is_service = 1
          AND pitem.amount > 0
        GROUP BY MONTH(p.posting_date), pitem.item_code
    """, (employee, year, start_m, end_m), as_dict=1)

    # 3. Per month counts of distinct customers and distinct services
    monthly_counts = frappe.db.sql("""
        SELECT
            MONTH(p.posting_date) as month_num,
            COUNT(DISTINCT p.customer) as total_customers,
            COUNT(DISTINCT pitem.item_code) as total_services
        FROM `tabPOS Invoice Item` pitem
        INNER JOIN `tabPOS Invoice` p ON pitem.parent = p.name
        LEFT JOIN `tabItem` itm ON pitem.item_code = itm.name
        WHERE pitem.employee = %s
          AND YEAR(p.posting_date) = %s
          AND MONTH(p.posting_date) >= %s AND MONTH(p.posting_date) <= %s
          AND p.docstatus = 1
          AND itm.is_service = 1
          AND pitem.amount > 0
        GROUP BY MONTH(p.posting_date)
    """, (employee, year, start_m, end_m), as_dict=1)

    counts_by_month = {c.month_num: c for c in monthly_counts}

    # Distinct customers over the whole window (cannot be summed from monthly counts)
    period_customers = frappe.db.sql("""
        SELECT COUNT(DISTINCT p.customer) as total_customers
        FROM `tabPOS Invoice Item` pitem
        INNER JOIN `tabPOS Invoice` p ON pitem.parent = p.name
        LEFT JOIN `tabItem` itm ON pitem.item_code = itm.name
        WHERE pitem.employee = %s
          AND YEAR(p.posting_date) = %s
          AND MONTH(p.posting_date) >= %s AND MONTH(p.posting_date) <= %s
          AND p.docstatus = 1
          AND itm.is_service = 1
          AND pitem.amount > 0
    """, (employee, year, start_m, end_m), as_dict=1)

    total_customers = period_customers[0].total_customers if period_customers else 0

    # Initialize matrix only for the active months in the scope
    matrix = {}
    for i in range(start_m, end_m + 1):
        counts = counts_by_month.get(i)
        matrix[i] = {
            "month": _(all_month_names[i - 1]),
            "total_sales": 0,
            "total_customers": counts.total_customers if counts else 0,
            "total_services": counts.total_services if counts else 0,
            # carried for the drill down on the "No. of Services" cell
            "employee": employee,
            "month_num": i
        }
        for s in services_data:
            matrix[i][frappe.scrub(s.item_code)] = 0

    for row in raw_data:
        m = row['month_num']
        scrubbed_code = frappe.scrub(row['item_code'])
        if m in matrix and scrubbed_code in matrix[m]:
            matrix[m][scrubbed_code] = row['amount']
            matrix[m]["total_sales"] += row['amount']

    # --- Fetch monthly salary from Salary Structure (earnings - deductions) ---
    salary_structure_row = frappe.db.sql("""
        SELECT ssa.salary_structure
        FROM `tabSalary Structure Assignment` ssa
        WHERE ssa.employee = %s
          AND ssa.from_date <= %s
          AND ssa.docstatus = 1
        ORDER BY ssa.from_date DESC
        LIMIT 1
    """, (employee, f"{year}-12-31"), as_dict=1)

    monthly_salary = 0

    if salary_structure_row:
        salary_structure = salary_structure_row[0].salary_structure

        total_earnings = frappe.db.sql("""
            SELECT COALESCE(SUM(sd.amount), 0) as total
            FROM `tabSalary Detail` sd
            WHERE sd.parent = %s
              AND sd.parenttype = 'Salary Structure'
              AND sd.parentfield = 'earnings'
        """, (salary_structure,), as_dict=1)

        total_deductions = frappe.db.sql("""
            SELECT COALESCE(SUM(sd.amount), 0) as total
            FROM `tabSalary Detail` sd
            WHERE sd.parent = %s
              AND sd.parenttype = 'Salary Structure'
              AND sd.parentfield = 'deductions'
        """, (salary_structure,), as_dict=1)

        earnings = total_earnings[0].total if total_earnings else 0
        deductions = total_deductions[0].total if total_deductions else 0
        monthly_salary = earnings - deductions

    # --- Fetch annual target ---
    # Adjust doctype/field names to wherever you store employee targets.
    target_row = frappe.db.sql("""
        SELECT annual_target
        FROM `tabEmployee Sales Target`
        WHERE employee = %s
          AND fiscal_year = %s
        LIMIT 1
    """, (employee, year), as_dict=1)

    annual_target = target_row[0].annual_target if target_row else 0

    # If a single month is selected, prorate the target to that month
    num_months = end_m - start_m + 1
    prorated_target = (annual_target / 12) * num_months if annual_target else 0

    # --- Build data rows ---
    data = []
    totals_row = {
        "month": f"<b>{_('Total')}</b>",
        "total_sales": 0,
        "total_customers": total_customers,
        "total_services": len(services_data),
        "employee": employee,
        "month_num": 0  # 0 = whole selected window
    }
    for s in services_data:
        totals_row[frappe.scrub(s.item_code)] = 0

    for m in range(start_m, end_m + 1):
        row_data = matrix[m]
        data.append(row_data)
        totals_row["total_sales"] += row_data["total_sales"]
        for s in services_data:
            scrubbed = frappe.scrub(s.item_code)
            totals_row[scrubbed] += row_data[scrubbed]

    data.append(totals_row)

    # --- Summary rows ---
    total_sales = totals_row["total_sales"]
    net_target = total_sales - prorated_target
    net_target_pct = (total_sales / prorated_target * 100) if prorated_target else 0

    data.append({
        "month": f"<b>{_('Monthly Salary')}</b>",
        "total_sales": monthly_salary * num_months
    })

    data.append({
        "month": f"<b>{_('Target')}</b>",
        "total_sales": prorated_target
    })

    data.append({
        "month": f"<b>{_('Net Target')}</b>",
        "total_sales": net_target
    })

    data.append({
        "month": f"<b>{_('Net Target %')}</b>",
        "total_sales": round(net_target_pct, 2)
    })

    # Prepare chart
    chart_labels = [all_month_names[i - 1] for i in range(start_m, end_m + 1)]

    chart = {
        "data": {
            "labels": chart_labels,
            "datasets": [{"name": _("Total Monthly Sales"),
                          "values": [matrix[m]["total_sales"] for m in range(start_m, end_m + 1)]}]
        },
        "type": "line" if len(chart_labels) > 1 else "bar",
        "colors": ["#ff5858"]
    }

    return columns, data, None, chart


# --- DRILL DOWN: SESSIONS PER SERVICE FOR ONE EMPLOYEE ---
@frappe.whitelist()
def get_employee_service_details(employee, year, from_month=None, to_month=None):
    """Sessions done by an employee, broken down per service.

    Called when the "No. of Services" cell is clicked in the report.
    from_month / to_month are month numbers (1-12); when omitted the whole
    year is used (clamped to the current month for the running year).
    """
    if not frappe.has_permission("POS Invoice", "read"):
        frappe.throw(_("Not permitted to read POS Invoice"), frappe.PermissionError)

    year = int(year)
    now = datetime.now()

    from_month = int(from_month) if from_month else 1
    if to_month:
        to_month = int(to_month)
    else:
        to_month = now.month if year == now.year else 12

    return frappe.db.sql("""
        SELECT
            pitem.item_code,
            itm.item_name,
            SUM(pitem.qty) as sessions,
            COUNT(DISTINCT p.name) as invoices,
            COUNT(DISTINCT p.customer) as customers,
            SUM(pitem.amount) as amount
        FROM `tabPOS Invoice Item` pitem
        INNER JOIN `tabPOS Invoice` p ON pitem.parent = p.name
        LEFT JOIN `tabItem` itm ON pitem.item_code = itm.name
        WHERE pitem.employee = %s
          AND YEAR(p.posting_date) = %s
          AND MONTH(p.posting_date) >= %s AND MONTH(p.posting_date) <= %s
          AND p.docstatus = 1
          AND itm.is_service = 1
          AND pitem.amount > 0
        GROUP BY pitem.item_code, itm.item_name
        ORDER BY sessions DESC, amount DESC
    """, (employee, year, from_month, to_month), as_dict=1)