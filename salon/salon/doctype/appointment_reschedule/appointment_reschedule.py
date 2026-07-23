# Copyright (c) 2026, salon and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class AppointmentReschedule(Document):
	def on_submit(self):
		self.reschedule_appointment()

	def reschedule_appointment(self):
		if not self.status:
			frappe.throw(_("Change the status before submitting."))

		appointment = frappe.get_doc("Appointment", self.appointment)
		if self.status == "Open":
			pass

		
