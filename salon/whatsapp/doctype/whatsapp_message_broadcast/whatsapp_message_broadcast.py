# Copyright (c) 2025, salon and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import requests


class WhatsAppMessageBroadcast(Document):
	def validate(self):
		self.fill_template()

	def after_insert(self):
		pass
		# self.init_broadcast()

	def on_submit(self):
		send_messages(self.name)


	def fill_template(self):
		if not self.broadcast_template:
			return
		
		temp = frappe.get_doc("WhatsApp Message Broadcast Template", self.broadcast_template)
		self.update(temp.as_dict(no_default_fields=True))


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
			"numbers": numbers,
			"message_type": message_type,
			"numbers_source": self.numbers_source,
			"text": text,
			"template_name": template_name,
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
		if self.numbers_source == "Manually":
			for row in self.numbers:
				numbers.append(unify_mobile_number(row.number))

		elif self.numbers_source == "Customers":
			unclean_numbers = str(self.customers_numbers).splitlines()

			for n in unclean_numbers:
				clean_number = unify_mobile_number(n)
				numbers.append(clean_number)

		elif self.numbers_source == "Excel/CSV":
			pass

		return numbers

	def compose_components(self):
		components = []

		## Header Parameters
		header_components = frappe.get_all(
			"Message Components Table",
			filters={"parent": self.name, "section_name": "header"},
			fields=["type", "text", "file_url", "file_name"],
			order_by="param_order",
		)
		if header_components:
			components.append({"type": "header", "parameters": []})
			header_params = components[0]["parameters"]
			
			for c in header_components:
				param = {"type": c.type}

				if c.type == "text":
					param["text"] = c.text

				elif c.type == "image":
					param["image"] = {"link": c.file_url}

				elif c.type == "document":
					param["document"] = {
						"link": c.file_url,
						"filename": c.file_name,
					}

				else:
					frappe.throw("Header parameter type must be one of: text, image, document")

				header_params.append(param)


		## Body parameters
		body_components = frappe.get_all(
			"Message Components Table",
			filters={"parent": self.name, "section_name": "body"},
			fields=["type", "text"],
			order_by="param_order",
		)
		if body_components:
			body_comp = {"type": "body", "parameters": []}
			body_params = body_comp["parameters"]

			for c in body_components:
				if c.type != "text":
					frappe.throw("Body parameters must be type 'text' to match {{n}} placeholders.")

				body_params.append({
					"type": c.type,
					"text": c.text,
				})
			components.append(body_comp)


		## Buttons parameters
		button_components = frappe.get_all(
			"Message Components Table",
			filters={"parent": self.name, "section_name": "button"},
			fields=["type", "sub_type", "file_url"],
			order_by="param_order",
		)
		for idx, c in enumerate(button_components):
			button_comp = {
				"type": "button",
				"sub_type": c.sub_type,
				"index": str(idx),
				"parameters": [],
			}
			button_params = button_comp["parameters"]

			if c.sub_type == "url":
				button_params.append({
					"type": "text",
					"text": c.file_url,
				})

			components.append(button_comp)

		return components


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


@frappe.whitelist()
def cancel_broadcast(docname):
	try:
		doc = frappe.get_doc("WhatsApp Message Broadcast", docname)
		doc.cancel_requested = 1
		doc.sending_status = "Partially Sent"
		doc.save()
		frappe.db.commit()

		return {"success": True}
	except:
		return {"success": False}


@frappe.whitelist()
def start_broadcast(docname):	
	frappe.enqueue(
		method="salon.whatsapp.doctype.whatsapp_message_broadcast.whatsapp_message_broadcast.send_messages",
		queue="long",
		timeout=60 * 60 * 6,  # 6 hours
		docname=docname
	)
	return {"status": "started"}


@frappe.whitelist()
def send_messages(docname):
	try:
		self = frappe.get_doc("WhatsApp Message Broadcast", docname)
		self.cancel_requested = 0
		self.sending_status = "Sending"
		self.save()
		frappe.db.commit()

		wa_settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
		api_base_url = wa_settings.api_url
		api_key = wa_settings.get_password("api_key")

		wa_number = frappe.get_doc("WhatsApp Number", self.whatsapp_number)

		instance_id = wa_number.instance_id
		message_type = self.message_type
		text = self.text
		template = frappe.get_doc("WhatsApp Template", self.template)
		numbers = self.build_numbers_list()
		template_components = self.compose_components()

		# ---- Resume source of truth ----
		completed_numbers_list = []
		if self.completed_numbers:
			completed_numbers_list = [
			n.strip()
			for n in str(self.completed_numbers).splitlines()
			if n.strip()
			]

		completed_numbers_set = set(completed_numbers_list)

		# 3️⃣ session-only calculations (HERE 👇)
		already_completed = set(completed_numbers_list)

		numbers_to_send = [
			n for n in numbers
			if n not in already_completed
		]

		session_total = len(numbers_to_send)
		session_completed = 0
		
		for index, number in enumerate(numbers):
			self.reload()
			if self.cancel_requested:
				self.sending_status = "Partially Sent"
				self.save(ignore_permissions=True)
				frappe.db.commit()

				frappe.publish_realtime(
					event=f"whatsapp_broadcast_progress_{self.name}",
					message={
						"step": "cancelled",
						"message": "Broadcast cancelled by user",
						"completed": session_completed,
						"total": session_total,
						"remaining": session_total - session_completed,
					},
					user=frappe.session.user
				)
				return
			

			# Skip already sent
			if number in completed_numbers_set or number is None:
				continue
			
			url = f"{api_base_url}/whatsapp_integration.whatsapp_api.send_message_standalone"
			payload = {
				"instance_id": instance_id,
				"client_number": number,
				"type": message_type,
				"text": text,
				"template_name": template.name,
				"template_language": template.template_language,
				"template_components": template_components,
				"use_balance": True,
			}
			headers = {
				"Authorization": f"Basic {api_key}"
			}

			try:

				response = requests.post(url, headers=headers, json=payload, timeout=10)
				if response.status_code != 200:
					frappe.log_error(response.text, "WhatsApp Send Failed")

					# Fatal → stop
					if response.status_code in (401, 403, 429, 500):
						break
					
					continue

				data = response.json()["message"]
				if not data.get("success"):
					frappe.log_error(str(data.get("error")), "WhatsApp API Error")
					continue

				# success
				completed_numbers_list.append(number)
				completed_numbers_set.add(number)

				session_completed += 1

				self.completed_numbers = "\n".join(completed_numbers_list)
				self.current_number_index = len(completed_numbers_list)
				self.save(ignore_permissions=True)
				frappe.db.commit()

				# ---- realtime progress ----
				percent = int((session_completed / session_total) * 100) if session_total else 100

				frappe.publish_realtime(
					event=f"whatsapp_broadcast_progress_{self.name}",
					message={
						"completed": session_completed,
						"total": session_total,
						"remaining": session_total - session_completed,
						"percent": percent,
						"message": f"Sent {session_completed} of {session_total}"
					},
					user=frappe.session.user
				)

			except Exception as e:
				self.sending_status = "Partially Sent"
				self.save(ignore_permissions=True)
				frappe.db.commit()

				frappe.log_error(frappe.get_traceback(), "WhatsApp Send Exception")
				frappe.publish_realtime(
					event=f"whatsapp_broadcast_progress_{self.name}",
					message={
						"step": "error",
						"message": str(e),
						"completed": session_completed,
						"total": session_total,
						"remaining": session_total - session_completed,
						"percent": 0,
						"message": f"Sent {session_completed} of {session_total}"
					},
					user=frappe.session.user
				)
				break

		# frappe.db.commit()
		self.sending_status = "Sent"
		self.save(ignore_permissions=True)
		frappe.db.commit()

		frappe.publish_realtime(
			event=f"whatsapp_broadcast_progress_{self.name}",
			message={
				"step": "done",
				"completed": session_completed,
				"total": session_total,
				"remaining": session_total - session_completed,
				"percent": 100,
				"message": f"Sent {session_completed} of {session_total}"
			},
			user=frappe.session.user
		)
		return {"success": True}
	
	except Exception as e:
		frappe.publish_realtime(
			event=f"whatsapp_broadcast_progress_{self.name}",
			message={
				"step": "error",
				"message": str(e),
			},
			user=frappe.session.user
		)
		return {"success": False}


@frappe.whitelist()
def load_customers_numbers(by_group: bool = False, group: str=None):
	filters = {
		"disabled": 0
	}
	if by_group:
		filters["customer_group"] = group

	customers = frappe.get_list(
		"Customer",
		filters=filters,
		fields=["mobile_no"],
	)
	
	numbers = []
	for c in customers:
		if c.mobile_no:
			clean_number = unify_mobile_number(c.mobile_no)
			if clean_number and len(clean_number) == 12 and clean_number not in numbers:
				numbers.append(clean_number)

	return numbers


def unify_mobile_number(number):
	"""
	Takes common mobile number formats [05..., 5...]
	and unifies them into 9665...

	:return: 9665... mobile number format
	"""
	if len(number) == 12 and number[:4] == "9665":
		return number

	unified_number = None
	if len(number) == 10 and number[:2] == "05":
		short_number = str(number[1:]).replace(" ", "")

		unified_number = f"966{short_number}"

	elif len(number) < 10 and number[0] == "5":
		unified_number = f"966{number}"

	return unified_number