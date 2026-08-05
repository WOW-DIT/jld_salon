// Copyright (c) 2026, salon and contributors
// For license information, please see license.txt

frappe.query_reports["New Customers Summary"] = {
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
			"fieldname": "based_on",
			"label": __("New Customer Based On"),
			"fieldtype": "Select",
			"options": "Customer Creation Date\nFirst Invoice",
			"default": "Customer Creation Date",
			"reqd": 1
		},
		{
			"fieldname": "show_customers",
			"label": __("Show Customer List"),
			"fieldtype": "Check",
			"default": 0
		}
	],

	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		// Highlight the manually appended Total row
		const label = (data && (data.month || data.day)) || "";
		if (typeof label === "string" && label.indexOf("<b>") !== -1) {
			value = `<span style="font-weight:600">${value}</span>`;
		}

		if (column.fieldname === "new_customers" && data && data.new_customers) {
			value = `<span style="color:#28a745;font-weight:600">${value}</span>`;
		}

		return value;
	}
};
