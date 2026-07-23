import frappe
from frappe import _

def execute(filters=None):
    if not filters:
        filters = {}

    if not filters.get("year"):
        frappe.throw(_("Please select a Year"))

    year = filters.get("year")

    # 1. Fetch all unique service items sold this year (code AND name)
    services_data = frappe.db.sql("""
        SELECT DISTINCT pitem.item_code, itm.item_name
        FROM `tabPOS Invoice Item` pitem
        INNER JOIN `tabPOS Invoice` p ON pitem.parent = p.name
        LEFT JOIN `tabItem` itm ON pitem.item_code = itm.name
        WHERE YEAR(p.posting_date) = %s 
          AND p.docstatus = 1
          AND itm.is_service = 1
          AND pitem.amount > 0
    """, (year), as_dict=1)

    # Base Table Columns
    columns = [
        {"fieldname": "month", "label": _("Month"), "fieldtype": "Data", "width": 120},
        {"fieldname": "total_sales", "label": _("Total Revenue"), "fieldtype": "Currency", "width": 140}
    ]

    # Dynamically append item_name as the Label, item_code as fieldname
    for s in services_data:
        columns.append({
            "fieldname": frappe.scrub(s.item_code),
            "label": s.item_name or s.item_code,  # Shows friendly name
            "fieldtype": "Currency",
            "width": 150
        })

    # 2. Fetch aggregated sales amounts
    raw_data = frappe.db.sql("""
        SELECT 
            MONTH(p.posting_date) as month_num,
            pitem.item_code,
            SUM(pitem.amount) as amount
        FROM `tabPOS Invoice Item` pitem
        INNER JOIN `tabPOS Invoice` p ON pitem.parent = p.name
        LEFT JOIN `tabItem` itm ON pitem.item_code = itm.name
        WHERE YEAR(p.posting_date) = %s 
          AND p.docstatus = 1
          AND itm.is_service = 1
          AND pitem.amount > 0
        GROUP BY MONTH(p.posting_date), pitem.item_code
    """, (year), as_dict=1)

    month_names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    
    matrix = {}
    for i in range(1, 13):
        matrix[i] = {"month": _(month_names[i-1]), "total_sales": 0}
        for s in services_data:
            matrix[i][frappe.scrub(s.item_code)] = 0

    for row in raw_data:
        m = row['month_num']
        scrubbed_code = frappe.scrub(row['item_code'])
        if scrubbed_code in matrix[m]:
            matrix[m][scrubbed_code] = row['amount']
            matrix[m]["total_sales"] += row['amount']

    data = []
    totals_row = {"month": f"<b>{_('Total')}</b>", "total_sales": 0}
    for s in services_data:
        totals_row[frappe.scrub(s.item_code)] = 0

    for m in range(1, 13):
        row_data = matrix[m]
        data.append(row_data)
        totals_row["total_sales"] += row_data["total_sales"]
        for s in services_data:
            scrubbed = frappe.scrub(s.item_code)
            totals_row[scrubbed] += row_data[scrubbed]

    data.append(totals_row)

    chart = {
        "data": {
            "labels": month_names,
            "datasets": [{"name": _("Overall Service Sales"), "values": [matrix[m]["total_sales"] for m in range(1, 13)]}]
        },
        "type": "line",
        "colors": ["#2fc0a5"]
    }

    return columns, data, None, chart