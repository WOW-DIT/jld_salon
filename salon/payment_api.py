import frappe
import json
import requests
from frappe.utils.pdf import get_pdf
from frappe.utils.file_manager import save_file
from datetime import datetime, timedelta


@frappe.whitelist(allow_guest=True, methods=["POST"])
def payment_webhook():
	def log_transaction(
		transaction_id,
		amount,
		currency,
		status,
		type,
		sub_type,
		is_refunded,

	):
		try:
			trans = frappe.new_doc("Online Transaction")
			trans.id = transaction_id
			trans.amount = amount
			trans.currency = currency
			trans.status = status
			trans.type = type
			trans.sub_type = sub_type
			trans.is_refunded = is_refunded
			trans.insert(ignore_permissions=True)

		except Exception as e:
			pass

		
	try:
		"""
		Payment Webhook, to perform different tasks after a successful payment.
		"""
		bytes = frappe.request.data
		data = bytearray(bytes).decode('ascii')

		js = json.loads(data)
		intent = js["intention"]
		
		extras = intent["extras"]["creation_extras"]
		action = str(extras["action"])
		customer_name = str(extras["customer_name"])
		mobile_number = str(extras["mobile_number"])
		trans = js["transaction"]
		trans_id = trans["id"]
		trans_date = trans["created_at"]
		currency = trans.get("currency", "SAR")
		success = trans["success"]
		is_refunded = trans["is_refunded"]
		source_data = trans["source_data"]
		payment_type = source_data["type"]
		payment_sub_type = source_data["sub_type"]
		
		note = frappe.new_doc("Note")
		note.title = "payment LOG (11111111111111)"
		note.type = "External"
		note.public = 1
		note.content = str({"customer_name": customer_name, "mobile_no": mobile_number})
		note.insert(ignore_permissions=True)
		frappe.db.commit()

		customer = frappe.db.get_value("Customer", {"customer_name": customer_name, "mobile_no": mobile_number})

		card_tokens = intent["card_tokens"]
		if card_tokens:
			card_token = card_tokens[0]["token"]
		else:
			card_token = None
		
		
		if success:			
			if trans.get("amount"):
				trans_amount = trans.get("amount")
			elif trans.get("amount_cents"):
				trans_amount = trans["amount_cents"] / 100

			if action == "create_appointment":
				department = extras.get("department")
				employee = extras.get("employee")
				selected_date = extras.get("selected_date")
				selected_time = extras.get("selected_time")

				note = frappe.new_doc("Note")
				note.title = "payment LOG (222222222222222222)"
				note.type = "External"
				note.public = 1
				note.content = str(customer)
				note.insert(ignore_permissions=True)
				frappe.db.commit()

				payment_response = create_payment_entry(customer, trans_amount, trans_id, trans_date.split("T")[0])

				note = frappe.new_doc("Note")
				note.title = "payment LOG (33333333333333333333333)"
				note.type = "External"
				note.public = 1
				note.content = str(payment_response)
				note.insert(ignore_permissions=True)
				frappe.db.commit()

				if payment_response.get("success"):
					online_receipt = payment_response.get("online_receipt")
					appointment_response = create_appointment(
						department,
						employee,
						selected_date,
						selected_time,
						customer_name,
						mobile_number,
					)

					note = frappe.new_doc("Note")
					note.title = "payment LOG (44444444444444444444)"
					note.type = "External"
					note.public = 1
					note.content = str(appointment_response)
					note.insert(ignore_permissions=True)
					frappe.db.commit()

					if appointment_response.get("success"):
						note = frappe.new_doc("Note")
						note.title = "payment LOG (55555555555555)"
						note.type = "External"
						note.public = 1
						note.content = str(js)
						note.insert(ignore_permissions=True)
						frappe.db.commit()

						appointment_id = appointment_response.get("appointment_id")
						whatsapp_response = send_whatsapp_receipt(
							customer_name,
							mobile_number,
							department,
							selected_date,
							selected_time,
							appointment_id,
							online_receipt,
						)

						note = frappe.new_doc("Note")
						note.title = "payment LOG (66666666666666666666)"
						note.type = "External"
						note.public = 1
						note.content = f"{appointment_id}  :::  {whatsapp_response}"
						note.insert(ignore_permissions=True)
						frappe.db.commit()

		else:
			ref = None
		note = frappe.new_doc("Note")
		note.title = "payment LOG (77777777777777777)"
		note.type = "External"
		note.public = 1
		note.content = str(js)
		note.insert(ignore_permissions=True)
		frappe.db.commit()

		log_transaction(
			transaction_id=trans_id,
			amount=trans_amount,
			currency=currency,
			status="Succeeded" if success else "Failed",
			type=payment_type,
			sub_type=payment_sub_type,
			is_refunded= 1 if is_refunded else 0,
		)

		note = frappe.new_doc("Note")
		note.title = "payment LOG (CLEAN)"
		note.type = "External"
		note.public = 1
		note.content = str(js)
		note.insert(ignore_permissions=True)
		frappe.db.commit()

		return {"success": True}

	except Exception as e:
		note = frappe.new_doc("Note")
		note.title = "payment LOG (ERROR)"
		note.type = "External"
		note.public = 1
		note.content = str(e)
		note.insert(ignore_permissions=True)
		frappe.db.commit()

		return {"success": False, "message": str(e)}


def create_payment_entry(customer, amount, transaction_id, transaction_date):
	original_user = frappe.session.user
	try:
		frappe.set_user("Administrator")

		payment = frappe.new_doc("Payment Entry")
		payment.company = "Jean Louis David Salon"
		payment.party_type = "Customer"
		payment.party = customer
		payment.payment_type = "Receive"
		payment.mode_of_payment = "Credit/Debit Card"
		payment.paid_to = "120100003 - Inma Bank 22001 - JLDS"
		payment.paid_from = "Debtors - JLDS"
		payment.paid_amount = amount
		payment.received_amount = amount
		payment.is_customer_deposit = 1
		payment.reference_no = transaction_id
		payment.reference_date = transaction_date

		payment.insert(ignore_permissions=True)
		payment.submit()

		html = frappe.get_print(
			doctype=payment.doctype,
			name=payment.name,
			print_format="Bank and Cash Payment Voucher",
			doc=payment,
			as_pdf=False
		)

		# Convert HTML to PDF
		pdf_content = get_pdf(html)

		# File name
		file_name = f"{payment.name}.pdf"

		file_doc = save_file(
			fname=file_name,
			content=pdf_content,
			dt=payment.doctype,
			dn=payment.name,
			df="online_receipt",
			is_private=0
		)

		# Set file URL in the Attach field
		payment.online_receipt = file_doc.file_url
		payment.save(ignore_permissions=True)
		frappe.db.commit()

		return {
			"success": True,
			"online_receipt": file_doc.file_url,
		}
	except frappe.PermissionError as e:
		return {
			"success": False,
			"error": "No Permissions"
		}
	except Exception as e:
		return {
			"success": False,
			"error": str(e)
		}
	finally:
		frappe.set_user(original_user)


def create_appointment(
    department: str,
    employee: str,
    selected_date: str,
    selected_time: str,
    customer_name: str,
    customer_mobile_number: str,
):
	original_user = frappe.session.user
	try:
		frappe.set_user("Administrator")

		customer_id = frappe.get_value(
			"Customer",
			{"customer_name": customer_name, "mobile_no": customer_mobile_number},
		)
		if not customer_id:
			return {
				"success": False,
				"message": f"({customer_name}) customer with mobile number ({customer_mobile_number}) is not registered."
			}

		date = datetime.strptime(selected_date, "%Y-%m-%d")
		weekday = date.weekday()

		app_settings = frappe.get_list(
			"Appointment Setting",
			filters = {
				"employee": employee,
				"department": department,
				"weekday": str(weekday),
			},
			fields=["name", "customers_capacity", "duration", "from", "to"]
		)

		if not app_settings:
			return {
				"success": False,
				"message": f"The employee is not available on {selected_date} {selected_time}"
			}

		duration_seconds = app_settings[0].duration
		start_datetime = datetime.strptime(f"{selected_date} {selected_time}", "%Y-%m-%d %H:%M:%S")
		end_datetime = start_datetime + timedelta(seconds=duration_seconds)

		appointment = frappe.new_doc("Appointment")
		appointment.department = department
		appointment.employee = employee
		appointment.selected_date = selected_date
		appointment.scheduled_time = f"{selected_date} {selected_time}"
		appointment.scheduled_end_time = end_datetime
		appointment.customer = customer_id
		appointment.customer_name = customer_name
		appointment.customer_phone_number = customer_mobile_number
		appointment.appointment_with = "Customer"
		appointment.party = customer_id
		appointment.insert(ignore_permissions=True)

		frappe.db.commit()
		return {
			"success": True,
			"appointment_id": appointment.name,
		}

	except frappe.PermissionError as e:
		return {
			"success": False,
			"error": f"Don't have permission to create appointment"
		}
	except Exception as e:
		return {
			"success": False,
			"error": f"Failed to create a new appointment: {e}"
		}
	finally:
		frappe.set_user(original_user)


def send_whatsapp_receipt(
	customer_name: str,
	customer_number: str,
	department: str,
	appointment_id: str,
	appointment_date: str,
	appointment_time: str,
	payment_file_link: str,
):
	try:
		whatsapp_settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
		api_base_url = whatsapp_settings.api_url
		api_key = whatsapp_settings.get_password("api_key")

		template_name = whatsapp_settings.default_appointment_template
		template = frappe.get_doc("WhatsApp Template", template_name)
		whatsapp_number = frappe.get_doc("WhatsApp Number", template.whatsapp_number)

		url = f"{api_base_url}/whatsapp_integration.whatsapp_integration.doctype.whatsapp_broadcast_message.whatsapp_broadcast_message.init_broadcast"

		payload = {
			"instance_id": whatsapp_number.instance_id,
			"message_type": "template",
			"text": None,
			"template_name": template_name,
			"numbers": [
				customer_number
			],
			"components": [
				{
					"section_name": "body",
					"params": [
						{
							"type": "text",
							"text": customer_name
						},
						{
							"type": "text",
							"text": department
						},
						{
							"type": "text",
							"text": appointment_date
						},
						{
							"type": "text",
							"text": appointment_time
						},
						{
							"type": "text",
							"text": appointment_id
						},
					]
				},
				{
					"section_name": "button",
					"params": [
						{
							"type": "button",
							"sub_type": "url",
							"file_url": payment_file_link
						}
					]
				}
			]
		}
		headers = {"Authorization": f"Basic {api_key}"}
		response = requests.post(url, headers=headers, json=payload, timeout=15)

		if response.status_code == 200:
			data = response.json()["message"]

			if data.get("success"):
				reference_id = data.get("reference_id")

				url = f"{api_base_url}/whatsapp_integration.whatsapp_integration.doctype.whatsapp_broadcast_message.whatsapp_broadcast_message.submit_broadcast"
				payload = {
					"reference_id": reference_id
				}
				response = requests.post(url, headers=headers, json=payload, timeout=15)

		return {
			"success": response.status_code == 200,
			"data": response.text,
		}
	except Exception as e:
		return {
			"success": False,
			"error": str(e)
		}