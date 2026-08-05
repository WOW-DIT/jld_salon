// Copyright (c) 2026, salon and contributors
// For license information, please see license.txt

const SALON_MONTHS = ["January", "February", "March", "April", "May", "June",
	"July", "August", "September", "October", "November", "December"];

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
	],

	// Make the "No. of Services" cell clickable so the user can see the
	// session count per service.
	"formatter": function (value, row, column, data, default_formatter) {
		// Employee is a Link and Employee has show_title_field_in_link enabled,
		// which would render the long full name. Show the plain ID instead.
		if (column.fieldname === "employee" && value) {
			const id = frappe.utils.escape_html(value);
			return `<a href="/app/employee/${encodeURIComponent(value)}">${id}</a>`;
		}

		const formatted = default_formatter(value, row, column, data);

		if (column.fieldname !== "total_services" || !data || !data.employee || !value) {
			return formatted;
		}

		let from_month = "";
		let to_month = "";
		let label = data.employee_name || data.employee;

		if (data.month_num !== undefined) {
			// Single employee view: one row per month (month_num = 0 on the Total row)
			if (data.month_num) {
				from_month = data.month_num;
				to_month = data.month_num;
				label = __(SALON_MONTHS[data.month_num - 1]);
			}
		} else {
			// All employees view: follow the month filter
			const month = frappe.query_report.get_filter_value("month");
			if (month) {
				from_month = SALON_MONTHS.indexOf(month) + 1;
				to_month = from_month;
			} else {
				from_month = 1;
				to_month = 12;
			}
		}

		return `<a class="salon-services-drilldown" style="cursor:pointer; text-decoration:underline;"
			data-employee="${frappe.utils.escape_html(data.employee)}"
			data-label="${frappe.utils.escape_html(label)}"
			data-from-month="${from_month}"
			data-to-month="${to_month}">${formatted}</a>`;
	},

	"onload": function (report) {
		// Delegate on the page container: the datatable is re-rendered on every
		// refresh, so binding directly on the links would not survive.
		const $container = report.page ? report.page.main : $(report.parent);

		$container.off("click.salonDrilldown").on(
			"click.salonDrilldown",
			".salon-services-drilldown",
			function (e) {
				e.preventDefault();
				e.stopPropagation();
				const $link = $(this);
				salon_show_service_sessions({
					employee: $link.attr("data-employee"),
					label: $link.attr("data-label"),
					from_month: $link.attr("data-from-month"),
					to_month: $link.attr("data-to-month")
				});
			}
		);
	}
};

function salon_show_service_sessions(opts) {
	const year = frappe.query_report.get_filter_value("year");

	frappe.call({
		method: "salon.salon.report.employee_sales_summary.employee_sales_summary.get_employee_service_details",
		args: {
			employee: opts.employee,
			year: year,
			from_month: opts.from_month || "",
			to_month: opts.to_month || ""
		},
		freeze: true,
		freeze_message: __("Loading service details..."),
		callback: function (r) {
			const rows = r.message || [];

			if (!rows.length) {
				frappe.msgprint({
					title: __("Service Details"),
					message: __("No services found for this selection.")
				});
				return;
			}

			let total_sessions = 0;
			let total_amount = 0;

			const body = rows.map(function (d) {
				total_sessions += flt(d.sessions);
				total_amount += flt(d.amount);
				return `<tr>
					<td>${frappe.utils.escape_html(d.item_name || d.item_code)}</td>
					<td class="text-right">${flt(d.sessions)}</td>
					<td class="text-right">${cint(d.invoices)}</td>
					<td class="text-right">${cint(d.customers)}</td>
					<td class="text-right">${frappe.format(d.amount, { fieldtype: "Currency" })}</td>
				</tr>`;
			}).join("");

			const html = `<div class="table-responsive">
				<table class="table table-bordered table-sm">
					<thead>
						<tr>
							<th>${__("Service")}</th>
							<th class="text-right">${__("Sessions")}</th>
							<th class="text-right">${__("Invoices")}</th>
							<th class="text-right">${__("Customers")}</th>
							<th class="text-right">${__("Amount")}</th>
						</tr>
					</thead>
					<tbody>
						${body}
						<tr>
							<td><b>${__("Total")}</b></td>
							<td class="text-right"><b>${total_sessions}</b></td>
							<td class="text-right"></td>
							<td class="text-right"></td>
							<td class="text-right"><b>${frappe.format(total_amount, { fieldtype: "Currency" })}</b></td>
						</tr>
					</tbody>
				</table>
			</div>`;

			const d = new frappe.ui.Dialog({
				title: __("Sessions per Service") + " - " + (opts.label || opts.employee),
				size: "large",
				fields: [{ fieldtype: "HTML", fieldname: "details", options: html }]
			});
			d.show();
		}
	});
}
