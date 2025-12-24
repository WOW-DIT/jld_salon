app_name = "salon"
app_title = "Salon"
app_publisher = "salon"
app_description = "salon"
app_email = "info@wowit.sa"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "salon",
# 		"logo": "/assets/salon/logo.png",
# 		"title": "Salon",
# 		"route": "/salon",
# 		"has_permission": "salon.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/salon/css/salon.css"
# app_include_js = "/assets/salon/js/salon.js"

# include js, css files in header of web template
# web_include_css = "/assets/salon/css/salon.css"
# web_include_js = "/assets/salon/js/salon.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "salon/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "salon/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "salon.utils.jinja_methods",
# 	"filters": "salon.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "salon.install.before_install"
# after_install = "salon.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "salon.uninstall.before_uninstall"
# after_uninstall = "salon.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "salon.utils.before_app_install"
# after_app_install = "salon.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "salon.utils.before_app_uninstall"
# after_app_uninstall = "salon.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "salon.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	# "*": {
	# 	"on_update": "method",
	# 	"on_cancel": "method",
	# 	"on_trash": "method"
	# }
    "Payment Entry": {
        "on_submit": "salon.events.add_customer_deposit"
    },
    "POS Invoice": {
        "after_insert": "salon.events.get_advances",
        "on_submit": "salon.events.deduct_deposit_balance",
    },
    "Sales Invoice": {
        "on_submit": "salon.events.deduct_deposit_balance"
    },
    "Appointment": {
        "validate": "salon.events.validate_availability"
    },
    "Customer Cart": {
        "on_submit": "salon.events.send_review_messages"
	}
}

# Scheduled Tasks
# ---------------

scheduler_events = {
    "cron": {
		"0 */12 * * *": [
			"salon.utilities.scheduler.send_appointment_reminder",
		],
		# "0/30 * * * *": [
		# 	"erpnext.utilities.doctype.video.video.update_youtube_data",
		# ],
		# # Hourly but offset by 30 minutes
		# "30 * * * *": [
		# 	"erpnext.accounts.doctype.gl_entry.gl_entry.rename_gle_sle_docs",
		# ],
		# # Daily at 12PM
		# "0 12 * * *": [
		# 	"erpnext.stock.reorder_item.reorder_item",
		# ],
	},
	# "all": [
	# 	"salon.tasks.all"
	# ],
	# "daily": [
	# 	"salon.tasks.daily"
	# ],
	# "hourly": [
	# 	"salon.tasks.hourly"
	# ],
	# "weekly": [
	# 	"salon.tasks.weekly"
	# ],
	# "monthly": [
	# 	"salon.tasks.monthly"
	# ],
}

# Testing
# -------

# before_tests = "salon.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "salon.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "salon.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["salon.utils.before_request"]
# after_request = ["salon.utils.after_request"]

# Job Events
# ----------
# before_job = ["salon.utils.before_job"]
# after_job = ["salon.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"salon.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

