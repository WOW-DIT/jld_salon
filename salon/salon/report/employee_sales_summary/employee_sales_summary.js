// Copyright (c) 2026, salon and contributors
// For license information, please see license.txt

frappe.query_reports["Employee Sales Summary"] = {
	"filters": [
		{
            "fieldname": "year",
            "label": __("Year"),
            "fieldtype": "Link",
            "options": "Fiscal Year",
            "default": frappe.datetime.get_today().split("-")[0],
            "reqd": 1
        },
		{
            "fieldname": "month",
            "label": __("Month"),
            "fieldtype": "Select",
            "options": "\nJanuary\nFebruary\nMarch\nApril\nMay\nJune\nJuly\nAugust\nSeptember\nOctober\nNovember\nDecember",
            "reqd": 0
        },
        {
            "fieldname": "employee",
            "label": __("Employee"),
            "fieldtype": "Link",
            "options": "Employee",
            "reqd": 0,
			"get_query": function() {
				return {
					filters: {
						"designation": ["in", ["فنية تجميل", "مصففة شعر", "مساعدة اخصائية"]]
					}
				};
            }
        }
	]
};
