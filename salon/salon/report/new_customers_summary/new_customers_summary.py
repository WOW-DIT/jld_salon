# Copyright (c) 2026, salon and contributors
# For license information, please see license.txt

import calendar

import frappe
from frappe import _

MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def execute(filters=None):
    if not filters:
        filters = {}

    if not filters.get("year"):
        frappe.throw(_("Please select a Year"))

    year = int(filters.get("year"))
    month_name = filters.get("month")
    month_num = MONTH_NAMES.index(month_name) + 1 if month_name else None

    from_date, to_date = get_period(year, month_num)

    if filters.get("show_customers"):
        return get_customer_list(filters, from_date, to_date)

    if month_num:
        return get_daily_report(filters, year, month_num, from_date, to_date)

    return get_monthly_report(filters, year, from_date, to_date)


def get_period(year, month_num):
    if month_num:
        last_day = calendar.monthrange(year, month_num)[1]
        return f"{year}-{month_num:02d}-01", f"{year}-{month_num:02d}-{last_day:02d}"
    return f"{year}-01-01", f"{year}-12-31"


def get_first_visit_source(filters):
    """Subquery returning one row per customer: (customer, first_date).

    "Customer Creation Date" counts a customer as new on the day the record was
    registered, "First Invoice" counts them as new on the day of their first
    submitted (non-return) POS Invoice.
    """
    if filters.get("based_on") == "First Invoice":
        return """(
            SELECT pi.customer AS customer, MIN(pi.posting_date) AS first_date
            FROM `tabPOS Invoice` pi
            WHERE pi.docstatus = 1
              AND IFNULL(pi.is_return, 0) = 0
              AND IFNULL(pi.customer, '') != ''
            GROUP BY pi.customer
        )"""

    return """(
        SELECT c.name AS customer, DATE(c.creation) AS first_date
        FROM `tabCustomer` c
    )"""


def get_metric_columns():
    return [
        {"fieldname": "new_customers", "label": _("New Customers"), "fieldtype": "Int", "width": 130},
        {"fieldname": "new_served", "label": _("New Billed"), "fieldtype": "Int", "width": 110},
        {"fieldname": "returning_customers", "label": _("Returning Customers"), "fieldtype": "Int", "width": 160},
        {"fieldname": "total_customers", "label": _("Customers Served"), "fieldtype": "Int", "width": 145},
        {"fieldname": "new_pct", "label": _("New %"), "fieldtype": "Percent", "width": 100},
        {"fieldname": "new_revenue", "label": _("New Customer Revenue"), "fieldtype": "Currency", "width": 175},
        {"fieldname": "avg_new_revenue", "label": _("Avg / New Customer"), "fieldtype": "Currency", "width": 160},
        {"fieldname": "total_revenue", "label": _("Total Revenue"), "fieldtype": "Currency", "width": 150},
    ]


def fetch_buckets(filters, from_date, to_date, group_expr):
    """Return {bucket_key: row_values} for new customers, activity and revenue."""
    source = get_first_visit_source(filters)
    params = {"from_date": from_date, "to_date": to_date}

    new_rows = frappe.db.sql(f"""
        SELECT {group_expr.format(col="f.first_date")} AS bucket,
               COUNT(*) AS new_customers
        FROM {source} f
        WHERE f.first_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY {group_expr.format(col="f.first_date")}
    """, params, as_dict=1)

    activity_rows = frappe.db.sql(f"""
        SELECT {group_expr.format(col="p.posting_date")} AS bucket,
               COUNT(DISTINCT p.customer) AS total_customers,
               SUM(p.grand_total) AS total_revenue
        FROM `tabPOS Invoice` p
        WHERE p.docstatus = 1
          AND IFNULL(p.is_return, 0) = 0
          AND IFNULL(p.customer, '') != ''
          AND p.posting_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY {group_expr.format(col="p.posting_date")}
    """, params, as_dict=1)

    # Customers billed inside the same bucket in which they became new, and what they spent.
    # Not every new customer is billed (a record can be registered without a sale), so this
    # is counted separately from new_customers and keeps New % <= 100.
    new_activity_rows = frappe.db.sql(f"""
        SELECT {group_expr.format(col="p.posting_date")} AS bucket,
               COUNT(DISTINCT p.customer) AS new_served,
               SUM(p.grand_total) AS new_revenue
        FROM `tabPOS Invoice` p
        INNER JOIN {source} f
            ON f.customer = p.customer
           AND {group_expr.format(col="f.first_date")} = {group_expr.format(col="p.posting_date")}
        WHERE p.docstatus = 1
          AND IFNULL(p.is_return, 0) = 0
          AND f.first_date BETWEEN %(from_date)s AND %(to_date)s
          AND p.posting_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY {group_expr.format(col="p.posting_date")}
    """, params, as_dict=1)

    buckets = {}
    for row in new_rows:
        buckets.setdefault(row.bucket, {})["new_customers"] = row.new_customers or 0
    for row in activity_rows:
        bucket = buckets.setdefault(row.bucket, {})
        bucket["total_customers"] = row.total_customers or 0
        bucket["total_revenue"] = row.total_revenue or 0
    for row in new_activity_rows:
        bucket = buckets.setdefault(row.bucket, {})
        bucket["new_served"] = row.new_served or 0
        bucket["new_revenue"] = row.new_revenue or 0

    return buckets


def build_row(base, bucket):
    new_customers = bucket.get("new_customers", 0)
    new_served = bucket.get("new_served", 0)
    total_customers = bucket.get("total_customers", 0)
    new_revenue = bucket.get("new_revenue", 0)

    row = dict(base)
    row.update({
        "new_customers": new_customers,
        "new_served": new_served,
        "returning_customers": max(total_customers - new_served, 0),
        "total_customers": total_customers,
        "new_pct": round(new_served / total_customers * 100, 2) if total_customers else 0,
        "new_revenue": new_revenue,
        "avg_new_revenue": round(new_revenue / new_served, 2) if new_served else 0,
        "total_revenue": bucket.get("total_revenue", 0),
    })
    return row


def add_totals_row(data, label_field, label):
    totals = {label_field: f"<b>{label}</b>"}
    for field in ("new_customers", "new_served", "returning_customers",
                  "total_customers", "new_revenue", "total_revenue"):
        totals[field] = sum(row.get(field) or 0 for row in data)

    totals["new_pct"] = round(
        totals["new_served"] / totals["total_customers"] * 100, 2
    ) if totals["total_customers"] else 0
    totals["avg_new_revenue"] = round(
        totals["new_revenue"] / totals["new_served"], 2
    ) if totals["new_served"] else 0

    data.append(totals)
    return totals


def get_report_summary(totals, periods, period_label):
    return [
        {"label": _("Total New Customers"), "value": totals["new_customers"],
         "indicator": "Green", "datatype": "Int"},
        {"label": _("Avg New / {0}").format(period_label),
         "value": round(totals["new_customers"] / periods, 2) if periods else 0,
         "indicator": "Blue", "datatype": "Float"},
        {"label": _("New Customer Revenue"), "value": totals["new_revenue"],
         "indicator": "Green", "datatype": "Currency"},
        {"label": _("New % of Customers Served"), "value": totals["new_pct"],
         "indicator": "Orange", "datatype": "Percent"},
    ]


# --- VIEW 1: MONTHLY SUMMARY FOR THE YEAR ---
def get_monthly_report(filters, year, from_date, to_date):
    columns = [{"fieldname": "month", "label": _("Month"), "fieldtype": "Data", "width": 130}]
    columns += get_metric_columns()

    buckets = fetch_buckets(filters, from_date, to_date, "MONTH({col})")

    data = []
    for month_num in range(1, 13):
        bucket = buckets.get(month_num, {})
        if not bucket:
            continue
        data.append(build_row({"month": _(MONTH_NAMES[month_num - 1])}, bucket))

    if not data:
        return columns, [], _("No customer activity found for {0}.").format(year), None, None

    totals = add_totals_row(data, "month", _("Total"))

    chart = {
        "data": {
            "labels": [row["month"] for row in data[:-1]],
            "datasets": [
                {"name": _("New Customers"), "values": [row["new_customers"] for row in data[:-1]]},
                {"name": _("Returning Customers"), "values": [row["returning_customers"] for row in data[:-1]]},
            ],
        },
        "type": "bar",
        "colors": ["#28a745", "#7cd6fd"],
    }

    message = _("Select a Month to see the daily breakdown of new customers.")

    return columns, data, message, chart, get_report_summary(totals, len(data) - 1, _("Month"))


# --- VIEW 2: DAILY BREAKDOWN FOR A SELECTED MONTH ---
def get_daily_report(filters, year, month_num, from_date, to_date):
    columns = [
        {"fieldname": "date", "label": _("Date"), "fieldtype": "Date", "width": 110},
        {"fieldname": "day", "label": _("Day"), "fieldtype": "Data", "width": 110},
    ]
    columns += get_metric_columns()

    buckets = fetch_buckets(filters, from_date, to_date, "DATE({col})")

    days_in_month = calendar.monthrange(year, month_num)[1]

    data = []
    for day in range(1, days_in_month + 1):
        date = f"{year}-{month_num:02d}-{day:02d}"
        bucket = buckets.get(date) or buckets.get(frappe.utils.getdate(date), {})
        if not bucket:
            continue
        weekday = calendar.weekday(year, month_num, day)
        data.append(build_row({"date": date, "day": _(DAY_NAMES[weekday])}, bucket))

    if not data:
        return columns, [], _("No customer activity found for {0} {1}.").format(
            _(MONTH_NAMES[month_num - 1]), year), None, None

    totals = add_totals_row(data, "day", _("Total"))

    chart = {
        "data": {
            "labels": [frappe.utils.formatdate(row["date"], "dd MMM") for row in data[:-1]],
            "datasets": [
                {"name": _("New Customers"), "values": [row["new_customers"] for row in data[:-1]]},
            ],
        },
        "type": "line" if len(data) > 2 else "bar",
        "colors": ["#28a745"],
        "lineOptions": {"regionFill": 1},
    }

    message = _("Tick <b>Show Customer List</b> to see every new customer registered in this period.")

    return columns, data, message, chart, get_report_summary(totals, len(data) - 1, _("Day"))


# --- VIEW 3: THE ACTUAL NEW CUSTOMERS ---
def get_customer_list(filters, from_date, to_date):
    columns = [
        {"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Customer", "width": 130},
        {"fieldname": "customer_name", "label": _("Customer Name"), "fieldtype": "Data", "width": 200},
        {"fieldname": "mobile_no", "label": _("Mobile No"), "fieldtype": "Data", "width": 130},
        {"fieldname": "first_visit", "label": _("New On"), "fieldtype": "Date", "width": 110},
        {"fieldname": "customer_group", "label": _("Customer Group"), "fieldtype": "Link",
         "options": "Customer Group", "width": 150},
        {"fieldname": "territory", "label": _("Territory"), "fieldtype": "Link", "options": "Territory", "width": 130},
        {"fieldname": "invoices", "label": _("Invoices"), "fieldtype": "Int", "width": 90},
        {"fieldname": "amount", "label": _("First Day Revenue"), "fieldtype": "Currency", "width": 160},
    ]

    source = get_first_visit_source(filters)

    data = frappe.db.sql(f"""
        SELECT
            f.customer AS customer,
            c.customer_name,
            c.mobile_no,
            f.first_date AS first_visit,
            c.customer_group,
            c.territory,
            COUNT(DISTINCT p.name) AS invoices,
            COALESCE(SUM(p.grand_total), 0) AS amount
        FROM {source} f
        LEFT JOIN `tabCustomer` c ON c.name = f.customer
        LEFT JOIN `tabPOS Invoice` p
            ON p.customer = f.customer
           AND p.posting_date = f.first_date
           AND p.docstatus = 1
           AND IFNULL(p.is_return, 0) = 0
        WHERE f.first_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY f.customer, c.customer_name, c.mobile_no, f.first_date, c.customer_group, c.territory
        ORDER BY f.first_date, f.customer
    """, {"from_date": from_date, "to_date": to_date}, as_dict=1)

    if not data:
        return columns, [], _("No new customers found in this period."), None, None

    report_summary = [
        {"label": _("New Customers"), "value": len(data), "indicator": "Green", "datatype": "Int"},
        {"label": _("With a First Day Invoice"),
         "value": len([row for row in data if row.invoices]), "indicator": "Blue", "datatype": "Int"},
        {"label": _("First Day Revenue"),
         "value": sum(row.amount or 0 for row in data), "indicator": "Green", "datatype": "Currency"},
    ]

    return columns, data, None, None, report_summary
