// Copyright (c) 2026, salon and contributors
// For license information, please see license.txt

frappe.query_reports["Service Sales Analysis"] = {
	"filters": [
		{
            "fieldname": "year",
            "label": __("Year"),
            "fieldtype": "Link",
            "options": "Fiscal Year",
            "default": frappe.datetime.get_today().split("-")[0],
            "reqd": 1
        },
	]
};
