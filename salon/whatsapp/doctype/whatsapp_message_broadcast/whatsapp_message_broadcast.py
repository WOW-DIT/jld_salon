# Copyright (c) 2025, salon and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import requests


class WhatsAppMessageBroadcast(Document):
	def after_insert(self):
		self.init_broadcast()

	def on_submit(self):
		self.submit_broadcast()

	def init_broadcast(self):
		wa_settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
		api_base_url = wa_settings.api_url
		api_key = wa_settings.get_password("api_key")

		wa_number = frappe.get_doc("WhatsApp Number", self.whatsapp_number)

		instance_id = wa_number.instance_id
		message_type = self.message_type
		text = self.text
		template_name = self.template
		numbers = self.build_numbers_list()
		components = self.build_components_dict()


		url = f"{api_base_url}/whatsapp_integration.whatsapp_integration.doctype.whatsapp_broadcast_message.whatsapp_broadcast_message.init_broadcast"
		request_body = {
			"instance_id": instance_id,
			"message_type": message_type,
			"text": text,
			"template_name": template_name,
			"numbers": numbers,
			"components": components,
		}
		headers = {
			"Authorization": f"Basic {api_key}"
		}

		response = requests.post(url, headers=headers, json=request_body)
		if response.status_code == 200:
			data = response.json()["message"]

			success = data["success"]
			if success:
				reference_id = data["reference_id"]
				message = data["message"]

				self.reference_id = reference_id
				self.save()
				frappe.msgprint(message)
			
			else:
				error = data["error"]
				frappe.throw(str(error))

		else:
			frappe.throw(response.text)
		

			


	def submit_broadcast(self):
		wa_settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
		api_base_url = wa_settings.api_url
		api_key = wa_settings.get_password("api_key")

		url = f"{api_base_url}/whatsapp_integration.whatsapp_integration.doctype.whatsapp_broadcast_message.whatsapp_broadcast_message.submit_broadcast"
		request_body = {
			"reference_id": self.reference_id,
		}
		headers = {
			"Authorization": f"Basic {api_key}"
		}

		response = requests.post(url, headers=headers, json=request_body)
		if response.status_code == 200:
			data = response.json()["message"]

			success = data["success"]
			if success:
				frappe.msgprint("Sent")
			
			else:
				error = data["error"]
				frappe.throw(str(error))
		else:
			frappe.throw(response.text)


	def build_numbers_list(self):
		numbers = []
		for row in self.numbers:
			numbers.append(row.number)

		return numbers


	def build_components_dict(self):
		def get_params(broadcast_id, section):
			return frappe.db.sql("""
				SELECT c.section_name, c.param_order, c.type, c.sub_type, 
					c.text, c.file_url, c.file_name
				FROM `tabMessage Components Table` AS c
				WHERE c.parent=%s AND c.section_name=%s
				ORDER BY c.param_order
			""", (broadcast_id, section), as_dict=True)

		components = []

		# Sections in order
		sections = ["header", "body", "button"]

		for section in sections:
			rows = get_params(self.name, section)
			params_list = []

			for row in rows:
				# HEADER / BODY handling
				if section in ("header", "body"):
					if row.type == "text":
						params_list.append({
							"type": "text",
							"text": row.text
						})
					elif row.type == "document":
						params_list.append({
							"type": "document",
							"file_url": row.file_url,
							"file_name": row.file_name
						})

				# BUTTON handling
				elif section == "button":
					if row.sub_type == "url":
						params_list.append({
							"type": "button",
							"sub_type": "url",
							"file_url": row.file_url,
							# "file_name": row.file_name
						})
					else:
						# phone_number OR code
						params_list.append({
							"type": "button",
							"sub_type": row.sub_type,
							"text": row.text
						})

			if params_list:
				components.append({
					"section_name": section,
					"params": params_list
				})

		return components
