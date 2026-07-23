# Copyright (c) 2026, salon and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _

class EmployeeAppointmentTimes(Document):
	def validate(self):
		self.validate_duplicate_appointment_times()
		self.reschedule_appointments()

	def validate_duplicate_appointment_times(doc):
		duplicates = frappe.get_all(
			"Employee Appointment Times",
			filters={
				"employee": doc.employee,
				"name": ["!=", doc.name],
				"start_date": ["<=", doc.end_date],
				"end_date": [">=", doc.start_date],
			}
		)
		if duplicates:
			dup = frappe.get_value(
				"Employee Appointment Times",
				duplicates[0].name,
				["start_date", "end_date"],
				as_dict=True,
			)
			frappe.throw(
				_("Employee {} already has an overlapping record from {} to {}. ").format(
					doc.employee,
					dup.start_date,
					dup.end_date,
				) + f'<a href="/app/employee-appointment-times/{duplicates[0].name}">{duplicates[0].name}</a>'
			)

	def reschedule_appointments(self):
		if self.is_unavailable == 0:
			return
		
		frappe.db.set_value(
			"Appointment",
			{
				"employee": self.employee,
				"status": ["in", ["Open", "Unverified", "Waiting"]],
				"selected_date": ["between", [self.start_date, self.end_date]]
			},
			"status",
			"Reschedule",
		)