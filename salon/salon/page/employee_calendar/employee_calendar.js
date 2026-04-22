frappe.pages["employee-calendar"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Employee Calendar"),
		single_column: true,
	});

	function loadScript(src) {
		return new Promise((resolve, reject) => {
			if (document.querySelector(`script[src="${src}"]`)) return resolve();
			const el = document.createElement("script");
			el.src = src;
			el.onload = resolve;
			el.onerror = reject;
			document.head.appendChild(el);
		});
	}
	function loadStyle(href) {
		if (document.querySelector(`link[href="${href}"]`)) return;
		const el = document.createElement("link");
		el.rel = "stylesheet";
		el.href = href;
		document.head.appendChild(el);
	}

	const FC_VERSION = "6.1.15";
	const FC_CDN = `https://cdn.jsdelivr.net/npm/fullcalendar-scheduler@${FC_VERSION}`;
	loadStyle(`${FC_CDN}/index.global.min.css`);

	const COL_WIDTH = 180;
	const TIME_AXIS_W = 80;

	const style = document.createElement("style");
	style.textContent = `
		#emp-cal-root {
			display: flex;
			flex-direction: column;
			height: calc(100vh - 120px);
			padding: 0 16px 16px;
			box-sizing: border-box;
			font-family: var(--font-stack);
		}
		/* ── Toolbar ── */
		#emp-cal-toolbar {
			display: flex;
			align-items: flex-end;
			gap: 10px;
			padding: 10px 0;
			flex-wrap: wrap;
		}
		.date-cal-filter-group {
			display: flex;
			flex-direction: column;
			align-items: center;
			justify-content: center;
			gap: 10px;
		}
		.emp-cal-filter-group {
			display: flex;
			flex-direction: column;
			gap: 3px;
		}
		.emp-cal-filter-group label {
			font-size: 0.75rem;
			color: var(--text-muted);
			font-weight: 500;
			margin: 0;
		}
		/* Frappe control overrides to fit toolbar */
		.emp-cal-filter-group .frappe-control {
			margin-bottom: 0 !important;
		}
		.emp-cal-filter-group .frappe-control .form-group {
			margin-bottom: 0 !important;
		}
		.emp-cal-filter-group .frappe-control input.input-with-feedback,
		.emp-cal-filter-group .frappe-control .link-btn {
			height: 30px !important;
			min-height: 30px !important;
			font-size: 0.82rem !important;
			padding: 3px 8px !important;
		}
		.emp-cal-filter-group .frappe-control[data-fieldtype="Date"] input {
			width: 140px !important;
		}
		.emp-cal-filter-group .frappe-control[data-fieldtype="Link"] input {
			width: 160px !important;
		}
		#emp-cal-title {
			font-size: 1rem;
			font-weight: 600;
			min-width: 160px;
			text-align: center;
			color: var(--heading-color);
			align-self: center;
		}
		/* ── Employee multi-select panel ── */
		#emp-cal-emp-panel {
			display: flex;
			flex-direction: column;
			gap: 3px;
		}
		#emp-cal-emp-panel label {
			font-size: 0.75rem;
			color: var(--text-muted);
			font-weight: 500;
			margin: 0;
		}
		#emp-cal-emp-row {
			display: flex;
			gap: 4px;
			align-items: center;
		}
		#emp-cal-emp-select {
			min-width: 200px;
			max-width: 280px;
			font-size: 0.82rem;
			height: 30px;
			border: 1px solid var(--border-color);
			border-radius: var(--border-radius);
			background: var(--control-bg);
			color: var(--text-color);
			padding: 0 6px;
		}
		#emp-cal-emp-select[multiple] { height: auto; max-height: 80px; }
		#emp-cal-emp-search {
			width: 100%;
			height: 26px;
			font-size: 0.82rem;
			border: 1px solid var(--border-color);
			border-radius: var(--border-radius);
			background: var(--control-bg);
			color: var(--text-color);
			padding: 0 6px;
			box-sizing: border-box;
		}
		#emp-cal-emp-search::placeholder { color: var(--text-muted); }
		/* ── Outer border wrapper ── */
		#emp-cal-outer {
			flex: 1;
			min-height: 0;
			border: 1px solid var(--border-color);
			border-radius: var(--border-radius-lg);
			overflow: hidden;
			background: var(--card-bg);
		}
		/* ── Outer border wrapper ── */
		#emp-cal-outer {
			flex: 1;
			min-height: 0;
			border: 1px solid var(--border-color);
			border-radius: var(--border-radius-lg);
			overflow: hidden;
			background: var(--card-bg);
		}
		#emp-cal-scroll {
			width: 100%;
			height: 100%;
			overflow-x: auto;
			overflow-y: auto;
		}
		#emp-cal-scroll::-webkit-scrollbar        { width: 8px; height: 8px; }
		#emp-cal-scroll::-webkit-scrollbar-thumb  { background: var(--border-color); border-radius: 4px; }
		#emp-cal-scroll::-webkit-scrollbar-corner { background: transparent; }
		#emp-cal-fc { min-width: 100%; }

		/* ── Time axis — MUST be visible ── */
		.fc-timegrid-axis,
		.fc-col-header-cell.fc-timegrid-axis {
			position: sticky !important;
			left: 0 !important;
			z-index: 5 !important;
			background: transparent !important;
			width: ${TIME_AXIS_W}px !important;
			min-width: ${TIME_AXIS_W}px !important;
		}
		.fc-timegrid-slot-label {
			font-size: 0.72rem !important;
			color: var(--text-muted) !important;
			white-space: nowrap !important;
		}
		.fc-timegrid-slot-label-frame {
			display: flex !important;
			align-items: center !important;
			justify-content: flex-end !important;
			padding-right: 6px !important;
			height: 100% !important;
		}
		.fc-timegrid-slot-label-cushion {
			display: inline-block !important;
			font-size: 0.72rem !important;
			color: black !important;
			visibility: visible !important;
			opacity: 1 !important;
		}
		/* ── RTL: move time axis to the right for Arabic ── */
		.fc[dir="rtl"] .fc-timegrid-axis,
		.fc[dir="rtl"] .fc-col-header-cell.fc-timegrid-axis {
			left: auto !important;
			right: 0 !important;
		}
		.fc[dir="rtl"] .fc-timegrid-slot-label-frame {
			justify-content: flex-start !important;
			padding-right: 0 !important;
			padding-left: 6px !important;
		}
		/* ── Fixed column widths ── */
		.fc-timegrid-col,
		.fc-col-header-cell.fc-resource {
			width: ${COL_WIDTH}px !important;
			min-width: ${COL_WIDTH}px !important;
			max-width: ${COL_WIDTH}px !important;
		}
		/* ── Employee column headers ── */
		.fc-col-header-cell.fc-resource {
			background: var(--subtle-accent, #f4f5f7);
		}
		.fc-col-header-cell.fc-resource .fc-col-header-cell-cushion {
			font-weight: 600;
			font-size: 0.8rem;
			color: var(--heading-color);
			padding: 8px 6px;
			display: flex;
			align-items: center;
			justify-content: center;
			gap: 6px;
			white-space: nowrap;
		}
		/* ── Avatars ── */
		.emp-avatar {
			width: 26px; height: 26px;
			border-radius: 50%; object-fit: cover; flex-shrink: 0;
		}
		.emp-avatar-placeholder {
			width: 26px; height: 26px;
			border-radius: 50%;
			background: var(--primary);
			color: #fff; font-size: 10px; font-weight: 700;
			display: inline-flex; align-items: center; justify-content: center;
			flex-shrink: 0;
		}
		/* ── Events ── */
		.fc-timegrid-event {
			border-radius: 4px !important;
			border: none !important;
			font-size: 0.72rem;
			padding: 2px 4px;
			box-shadow: 0 1px 3px rgba(0,0,0,.18);
			cursor: pointer;
		}
		.fc-timegrid-event .fc-event-title { white-space: pre-wrap; line-height: 1.35; }
		.fc-timegrid-event .fc-event-time  { font-size: 0.65rem; opacity: 0.85; }
		.fc-bg-event { opacity: 0.22 !important; }
	`;
	document.head.appendChild(style);

	// ── DOM ───────────────────────────────────────────────────────────────────
	$(wrapper).find(".page-content").html(`
		<div id="emp-cal-root">
			<div id="emp-cal-toolbar">
				<div class="date-cal-filter-group" style="align-self:flex-end">
					<span id="emp-cal-title">${__("Loading…")}</span>
					<div class="btn-group" style="align-self:flex-end">
						<button class="btn btn-default btn-sm" id="emp-cal-prev">‹ ${__("Prev")}</button>
						<button class="btn btn-default btn-sm" id="emp-cal-today">${__("Today")}</button>
						<button class="btn btn-default btn-sm" id="emp-cal-next">${__("Next")} ›</button>
					</div>
				</div>
				<div class="emp-cal-filter-group" id="emp-cal-date-wrap">
					<label>${__("Date")}</label>
				</div>
				<div class="emp-cal-filter-group" id="emp-cal-customer-wrap">
					<label>${__("Customer")}</label>
				</div>
				<div class="emp-cal-filter-group" id="emp-cal-dept-wrap">
					<label>${__("Department")}</label>
				</div>
				<div class="emp-cal-filter-group" id="emp-cal-service-wrap">
					<label>${__("Service")}</label>
				</div>
				<div id="emp-cal-emp-panel">
					<label>${__("Employees")}</label>
					<input id="emp-cal-emp-search" type="text" placeholder="${__("Search employees…")}" />
					<div id="emp-cal-emp-row">
						<select id="emp-cal-emp-select" multiple></select>
						<button class="btn btn-xs btn-default" id="emp-cal-toggle-all">${__("All")}</button>
						<button class="btn btn-xs btn-primary" id="emp-cal-apply">${__("Apply")}</button>
					</div>
				</div>
			</div>
			<div id="emp-cal-outer">
				<div id="emp-cal-scroll">
					<div id="emp-cal-fc"></div>
				</div>
			</div>
		</div>
	`);

	// ── Frappe Controls ───────────────────────────────────────────────────────
	let dateControl, deptControl, serviceControl;

	function makeControls() {
		// Date picker
		dateControl = frappe.ui.form.make_control({
			df: { fieldtype: "Date", fieldname: "cal_date", label: "" },
			parent: document.getElementById("emp-cal-date-wrap"),
			render_input: true,
		});
		dateControl.set_value(frappe.datetime.get_today());
		dateControl.$input.on("change", () => {
			const v = dateControl.get_value();
			if (v && calendarInstance) calendarInstance.gotoDate(v);
		});

		customerControl = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				fieldname: "customer",
				label: "",
				options: "Customer",
				placeholder: __("Mobile Number, Customer Name, MRN"),
			},
			parent: document.getElementById("emp-cal-customer-wrap"),
			render_input: true,
		});
		customerControl.$input.on("change", () => {
			if (calendarInstance) calendarInstance.refetchEvents();
			// serviceControl.set_value("");
			// applyFilters();
		});
		// mobileControl = frappe.ui.form.make_control({
		// 	df: {
		// 		fieldtype: "Link",
		// 		fieldname: "mobile_number",
		// 		label: "",
		// 		placeholder: __("Search by mobile…"),
		// 	},
		// 	parent: document.getElementById("emp-cal-mobile-wrap"),
		// 	render_input: true,
		// });
		// mobileControl.$input.on("input", () => {
		// 	if (calendarInstance) calendarInstance.refetchEvents();
		// });

		// Department link
		deptControl = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				fieldname: "department",
				label: "",
				options: "Item Group",
				placeholder: __("All Departments"),
			},
			parent: document.getElementById("emp-cal-dept-wrap"),
			render_input: true,
		});
		deptControl.$input.on("change", () => {
			serviceControl.set_value("");
			applyFilters();
		});

		// Service multi-select using Frappe MultiSelectDialog or simple Link
		serviceControl = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				fieldname: "service",
				label: "",
				options: "Item",
				placeholder: __("All Services"),
				get_query: () => {
					const dept = deptControl?.get_value();
					return {
						filters: {
							is_service: 1,
							disabled: 0,
							...(dept ? { item_group: dept } : {}),   // filter by Item Group
						},
					};
				},
			},
			parent: document.getElementById("emp-cal-service-wrap"),
			render_input: true,
		});
		serviceControl.$input.on("change", applyFilters);
	}

	// ── Populate employee select ──────────────────────────────────────────────
	function populateEmployeeSelect(employees, selectedIds = null) {
		const sel = document.getElementById("emp-cal-emp-select");
		sel.innerHTML = "";
		employees.forEach((emp) => {
			const opt = document.createElement("option");
			opt.value = emp.name;
			opt.textContent = emp.employee_name;
			opt.selected = selectedIds ? selectedIds.includes(emp.name) : true;
			sel.appendChild(opt);
		});
	}

	// ── Apply filters — fetch matching employees then re-init ─────────────────
	let allEmployees = [];

	function applyFilters() {
		const dept    = deptControl?.get_value() || null;
		const service = serviceControl?.get_value() || null;
		
		let filters = {};
		if (dept)    filters.department = dept;

		if (service) {
			debugger;
			// Fetch employees who can perform this service
			frappe.call({
				method: "frappe.client.get_list",
				args: {
					doctype: "Employee",
					filters: { ...filters, status: "Active" },
					fields: ["name", "employee_name", "image"],
					limit_page_length: 200,
				},
				callback(r) {
					// Further filter by service linkage if needed
					// For now show department-filtered employees
					// You can add service→employee mapping via your own method
					const emps = r.message || [];
					populateEmployeeSelect(emps);
					const sel = document.getElementById("emp-cal-emp-select");
					const ids = Array.from(sel.options).map(o => o.value);
					const visible = allEmployees.filter(e => ids.includes(e.name));
					// merge back any extra props not in frappe list
					initCalendar(emps.length ? emps : allEmployees);
				},
			});
		} else {
			// No service selected — filter allEmployees by dept only
			const filtered = dept
				? allEmployees.filter(e => e.department === dept)
				: allEmployees;
			populateEmployeeSelect(filtered);
			initCalendar(filtered);
		}
	}

	// ── Employee search — filters the <select> options in real time ───────────
	document.addEventListener("input", (e) => {
		if (e.target.id !== "emp-cal-emp-search") return;
		const q = e.target.value.trim().toLowerCase();
		const sel = document.getElementById("emp-cal-emp-select");
		Array.from(sel.options).forEach((opt) => {
			const match = !q || opt.textContent.toLowerCase().includes(q);
			opt.style.display = match ? "" : "none";
			// Keep previously selected state; don't auto-deselect hidden options
		});
	});

	// ── Select / Deselect All toggle ──────────────────────────────────────────
	let allSelected = true;
	document.addEventListener("click", (e) => {
		if (e.target.id !== "emp-cal-toggle-all") return;
		allSelected = !allSelected;
		const sel = document.getElementById("emp-cal-emp-select");
		Array.from(sel.options).forEach(o => o.selected = allSelected);
		e.target.textContent = allSelected ? __("None") : __("All");
	});

	// ── Calendar ──────────────────────────────────────────────────────────────
	let calendarInstance = null;
	let resizeObserver   = null;

	function initCalendar(visibleEmployees) {
		const calEl    = document.getElementById("emp-cal-fc");
		const outerEl  = document.getElementById("emp-cal-outer");
		const scrollEl = document.getElementById("emp-cal-scroll");

		if (resizeObserver)   { resizeObserver.disconnect();  resizeObserver = null; }
		if (calendarInstance) { calendarInstance.destroy();   calendarInstance = null; }

		const totalW = TIME_AXIS_W + visibleEmployees.length * COL_WIDTH;
		calEl.style.width  = Math.max(totalW, scrollEl.clientWidth) + "px";
		calEl.style.height = outerEl.clientHeight + "px";

		const resources = visibleEmployees.map((emp) => ({
			id: emp.name,
			title: emp.employee_name,
			image: emp.image || null,
		}));

		calendarInstance = new FullCalendar.Calendar(calEl, {
			schedulerLicenseKey: "GPL-My-Project-Is-Open-Source",
			initialView: "resourceTimeGridDay",
			direction: frappe.boot.lang === "ar" ? "rtl" : "ltr",
			height: outerEl.clientHeight,
			nowIndicator: true,
			allDaySlot: false,
			slotMinTime: "11:00:00",
			slotMaxTime: "22:00:00",
			slotDuration: "00:15:00",
			slotLabelInterval: "00:30:00",
			slotLabelFormat: { hour: "numeric", minute: "2-digit", hour12: true },
			eventTimeFormat: { hour: "numeric", minute: "2-digit", hour12: true },
			// slotLabelFormat: { hour: "2-digit", minute: "2-digit", hour12: false },
			headerToolbar: false,
			resourceAreaWidth: "0px",
			stickyHeaderDates: false,
			stickyFooterScrollbar: false,
			resources,

			resourceLabelContent(arg) {
				const name  = arg.resource.title;
				const image = arg.resource.extendedProps.image;
				let avatarHtml;
				if (image) {
					avatarHtml = `<img class="emp-avatar" src="${frappe.utils.escape_html(image)}" alt="" />`;
				} else {
					const initials = name.split(" ").slice(0, 2).map((w) => w[0]?.toUpperCase() || "").join("");
					avatarHtml = `<span class="emp-avatar-placeholder">${initials}</span>`;
				}
				const el = document.createElement("div");
				el.style.cssText = "display:flex;align-items:center;gap:6px;justify-content:center;width:100%;overflow:hidden;";
				el.innerHTML = `${avatarHtml}<span style="overflow:hidden;text-overflow:ellipsis;">${frappe.utils.escape_html(name)}</span>`;
				return { domNodes: [el] };
			},

			events(fetchInfo, successCallback, failureCallback) {
				const customer = customerControl.get_value();

				frappe.call({
					method: "salon.salon.page.employee_calendar.employee_calendar.get_appointment_events",
					args: {
						doctype: "Appointment",
						start: fetchInfo.startStr,
						end: fetchInfo.endStr,
						field_map: JSON.stringify({
							start: "scheduled_time",
							end: "scheduled_end_time",
							id: "name",
							title: "customer_name",
						}),
						filters: JSON.stringify([]),
						customer: customer,
					},
					callback(r) {
						const raw = r.message || [];
						console.log("SUCCESS COUNT:", raw.length);
						const mapped = raw.map((e) => {
							const isBg = e.rendering === "background";
							return {
								id: e.name,
								resourceId: e.employee,
								title: e.title || e.customer_name || "",
								start: (e.scheduled_time || "").replace(" ", "T"),
								end:   (e.scheduled_end_time || "").replace(" ", "T"),
								backgroundColor: e.color || "#5e64ff",
								borderColor:     e.color || "#5e64ff",
								textColor: getContrastColor(e.color),
								display:    isBg ? "background" : "block",
								classNames: isBg ? ["fc-bg-event"] : [],
								extendedProps: {
									url:      e.url || null,
									status:   e.status,
									customer: e.customer_name,
									service:  e.service,
									phone:    e.customer_phone_number,
								},
							};
						});
						console.log("MAPPED:", mapped);
						successCallback(mapped);				
					},
					error: failureCallback,
				});
			},

			eventDidMount(info) {
				if (info.event.display === "background") return;
				const p = info.event.extendedProps;
				$(info.el).tooltip({
					title: [
						p.customer ? `<b>${frappe.utils.escape_html(p.customer)}</b>` : "",
						p.service  ? frappe.utils.escape_html(p.service) : "",
						p.phone    ? `📞 ${frappe.utils.escape_html(p.phone)}` : "",
						p.status   ? `<span class="indicator ${statusIndicatorClass(p.status)}">${p.status}</span>` : "",
					].filter(Boolean).join("<br>"),
					html: true, placement: "top", container: "body", trigger: "hover",
				});
			},

			eventClick(info) {
				if (info.event.display === "background") return;
				info.jsEvent.preventDefault();
				const url = info.event.extendedProps.url;
				if (url) window.location.href = url;
				else frappe.set_route("Form", "Appointment", info.event.id);
			},

			datesSet(info) {
				document.getElementById("emp-cal-title").textContent = info.view.title;
			},
		});
		calendarInstance.render();

		// ── Toolbar buttons ───────────────────────────────────────────────────
		document.getElementById("emp-cal-prev").onclick  = () => calendarInstance.prev();
		document.getElementById("emp-cal-next").onclick  = () => calendarInstance.next();
		document.getElementById("emp-cal-today").onclick = () => calendarInstance.today();

		// Apply employee filter
		document.getElementById("emp-cal-apply").onclick = () => {
			const sel = document.getElementById("emp-cal-emp-select");
			const ids = Array.from(sel.selectedOptions).map((o) => o.value);
			const filtered = ids.length
				? allEmployees.filter((emp) => ids.includes(emp.name))
				: allEmployees;
			initCalendar(filtered);
		};

		// ResizeObserver
		resizeObserver = new ResizeObserver(() => {
			const h = outerEl.clientHeight;
			const w = Math.max(TIME_AXIS_W + visibleEmployees.length * COL_WIDTH, scrollEl.clientWidth);
			calEl.style.height = h + "px";
			calEl.style.width  = w + "px";
			if (calendarInstance) calendarInstance.setOption("height", h);
		});
		resizeObserver.observe(outerEl);
	}

	// ── Boot ──────────────────────────────────────────────────────────────────
	loadScript(`${FC_CDN}/index.global.min.js`).then(() => {
		makeControls();
		frappe.call({
			method: "salon.salon.page.employee_calendar.employee_calendar.get_employees",
			callback(r) {
				allEmployees = r.message || [];
				populateEmployeeSelect(allEmployees);
				initCalendar(allEmployees);
			},
		});
	});

	// ── Helpers ───────────────────────────────────────────────────────────────
	function getContrastColor(hex) {
		if (!hex) return "#fff";
		const c = hex.replace("#", "");
		if (c.length !== 6) return "#fff";
		const r = parseInt(c.slice(0, 2), 16);
		const g = parseInt(c.slice(2, 4), 16);
		const b = parseInt(c.slice(4, 6), 16);
		return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.55 ? "#1a1a1a" : "var(--card-bg)";
	}

	function statusIndicatorClass(status) {
		const map = {
			Open: "blue", Scheduled: "blue",
			Confirmed: "green", Completed: "green", Closed: "green",
			Cancelled: "red", "No Show": "orange", Pending: "yellow",
		};
		return map[status] || "grey";
	}
};