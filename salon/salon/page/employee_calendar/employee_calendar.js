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

	const COL_WIDTH = 200;
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
			min-height: 600px;
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

		/* ── Time axis ── */
		.fc-timegrid-axis,
		.fc-col-header-cell.fc-timegrid-axis {
			position: sticky !important;
			left: 0 !important;
			z-index: 5 !important;
			background: transparent !important;
			width: ${TIME_AXIS_W}px !important;
			min-width: ${TIME_AXIS_W}px !important;
		}
		.fc-event-resizable {
			height: 100% !important;
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
		/* ── RTL ── */
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
						<button class="btn btn-xs btn-primary" id="emp-cal-clear-filter">${__("Clear Filter")}</button>
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

	// ── State ─────────────────────────────────────────────────────────────────
	let dateControl, customerControl, deptControl, serviceControl;
	let selectedService = null;
	let selectedCustomer = null;
	let selectedDept = null;
	let calendarInstance = null;
	let resizeObserver = null;
	let allEmployees = [];
	let allSelected = true;
	let employeeShifts = {};
	let _suppressDateChange = false;
	let visibleEmployees = [];
	let employeeEventCounts = {};
	let employeeLeaves = {};
	let currentCalDate = frappe.datetime.get_today();


	// ── Frappe Controls ───────────────────────────────────────────────────────
	function makeControls() {
		dateControl = frappe.ui.form.make_control({
			df: {
				fieldtype: "Date",
				fieldname: "cal_date",
				label: "",
				onchange: () => {
					if (_suppressDateChange) return;
					const v = dateControl.get_value();
					if (v) { pushFiltersToUrl(); navigateToDate(v); }
				}
			},
			parent: document.getElementById("emp-cal-date-wrap"),
			render_input: true,
		});
		dateControl.set_value(frappe.datetime.get_today());

		customerControl = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				fieldname: "customer",
				label: "",
				options: "Customer",
				placeholder: __("Mobile Number, Customer Name, MRN"),
				onchange: () => {
					selectedCustomer = customerControl.get_value() || null;
					window.open(`/app/appointment/view/list?customer=${selectedCustomer}`, "_blank");
					
					// customerControl.set_value("")
				}
			},
			parent: document.getElementById("emp-cal-customer-wrap"),
			render_input: true,
		});

		deptControl = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				fieldname: "department",
				label: "",
				options: "Item Group",
				placeholder: __("All Departments"),
				get_query: () => {
					return {
						filters: {
							name: ["!=", "All Item Groups"],
							parent_item_group: ["not in", "All Item Groups"],
							is_group: 0,
						},
					};
				},
				onchange: () => {
					selectedDept = deptControl.get_value() || null;
					serviceControl.set_value("").then(() => { pushFiltersToUrl(); applyFilters(); });
				}
			},
			parent: document.getElementById("emp-cal-dept-wrap"),
			render_input: true,
		});

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
							...(dept ? { item_group: dept } : {}),
						},
					};
				},
				onchange: () => {
					selectedService = serviceControl.get_value() || null;
					pushFiltersToUrl();
					applyFilters();
				}
			},
			parent: document.getElementById("emp-cal-service-wrap"),
			render_input: true,
		});
	}

	// ── Populate employee select ──────────────────────────────────────────────
	function populateEmployeeSelect(employees, selectedIds = null) {
		const sel = document.getElementById("emp-cal-emp-select");
		sel.innerHTML = "";
		employees.forEach((emp) => {
			const opt = document.createElement("option");
			opt.value = emp.name;
			opt.textContent = `${emp.first_name} ${emp.last_name}`;
			opt.selected = selectedIds ? selectedIds.includes(emp.name) : true;
			sel.appendChild(opt);
		});
	}

	// ── Build employeeShifts map from employee list ───────────────────────────
	function buildShifts(emps, calDate) {
		employeeShifts = {};
		employeeLeaves = {};
		currentCalDate = calDate;
		emps.forEach(emp => {
			const leave    = emp.leave || null;
			const isActive = leave && leave.from_date <= calDate && calDate <= leave.to_date;
			employeeShifts[emp.name] = {
				unavailable: emp.unavailable || isActive,
				start: emp.shift_start,
				end:   emp.shift_end,
			};
			employeeLeaves[emp.name] = leave;
		});
	}

	// ── applyFilters — full rebuild (service / dept / employee-filter changed) ─
	function applyFilters() {
		const currentDate = dateControl?.get_value() || frappe.datetime.get_today();
		frappe.call({
			method: "salon.salon.page.employee_calendar.employee_calendar.get_employees",
			args: {
				service: selectedService || null,
				department: selectedDept || null,
				date: currentDate,
			},
			callback(r) {
				const emps = r.message || [];
				allEmployees = emps;
				populateEmployeeSelect(emps);
				initCalendar(emps, currentDate);
			},
		});
	}

	// ── navigateToDate — date changed; reuse existing calendar, just refetch ──
	//    Fetches fresh employee+shift data for the new date, updates shifts,
	//    then calls gotoDate + refetchEvents without destroying the calendar.
	function navigateToDate(newDate) {
		frappe.call({
			method: "salon.salon.page.employee_calendar.employee_calendar.get_employees",
			args: {
				service: selectedService || null,
				department: selectedDept || null,
				date: newDate,
			},
			callback(r) {
				const emps = r.message || [];
				allEmployees = emps;

				// Preserve whatever the user currently has selected in the list
				const sel = document.getElementById("emp-cal-emp-select");
				const currentlySelected = Array.from(sel.selectedOptions).map(o => o.value);
				populateEmployeeSelect(emps, currentlySelected.length ? currentlySelected : null);

				// IMPORTANT: update shifts BEFORE refetchEvents so the events
				// callback has the correct data when it runs
				buildShifts(emps, newDate);

				if (calendarInstance) {
					_suppressDateChange = true;
					calendarInstance.gotoDate(newDate);
					setTimeout(() => { _suppressDateChange = false; }, 0);
					calendarInstance.refetchEvents();
				}
			},
		});
	}

	// ── Employee search ───────────────────────────────────────────────────────
	document.addEventListener("input", (e) => {
		if (e.target.id !== "emp-cal-emp-search") return;
		const q = e.target.value.trim().toLowerCase();
		const sel = document.getElementById("emp-cal-emp-select");
		Array.from(sel.options).forEach((opt) => {
			opt.style.display = (!q || opt.textContent.toLowerCase().includes(q)) ? "" : "none";
		});
	});

	// ── Select / Deselect All toggle ──────────────────────────────────────────
	document.addEventListener("click", (e) => {
		if (e.target.id !== "emp-cal-toggle-all") return;
		allSelected = !allSelected;
		const sel = document.getElementById("emp-cal-emp-select");
		Array.from(sel.options).forEach(o => o.selected = allSelected);
		e.target.textContent = allSelected ? __("None") : __("All");
	});

	// ── initCalendar — full destroy + rebuild ─────────────────────────────────
	//    Only called by applyFilters (service/dept/employee-set changes).
	//    Date navigation uses navigateToDate instead.
	function initCalendar(emps, calDate) {
		visibleEmployees = emps;
		calDate = calDate || frappe.datetime.get_today();
		debugger

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
			title: `${emp.first_name} ${emp.last_name}`,
			image: emp.image || null,
			eventCounts: { total: 0, Open: 0, Closed: 0, Cancelled: 0 },
		}));

		calendarInstance = new FullCalendar.Calendar(calEl, {
			schedulerLicenseKey: "GPL-My-Project-Is-Open-Source",
			initialView: "resourceTimeGridDay",
			initialDate: calDate,
			direction: frappe.boot.lang === "ar" ? "rtl" : "ltr",
			height: outerEl.clientHeight,
			nowIndicator: true,
			allDaySlot: false,
			selectable: true,
			selectMirror: true,
			defaultTimedEventDuration: "01:00:00",
			slotMinTime: "11:00:00",
			slotMaxTime: "22:00:00",
			slotDuration: "00:15:00",
			slotLabelInterval: "00:30:00",
			slotLabelFormat: { hour: "numeric", minute: "2-digit", hour12: true },
			eventTimeFormat: { hour: "numeric", minute: "2-digit", hour12: true },
			headerToolbar: false,
			resourceAreaWidth: "0px",
			stickyHeaderDates: false,
			stickyFooterScrollbar: false,
			resources,

			resourceLabelContent(arg) {
				const name  = arg.resource.title;
				const image = arg.resource.extendedProps.image;
				const counts = employeeEventCounts[arg.resource.id] || { total: 0, Open: 0, Closed: 0, Cancelled: 0 };
				const leave = employeeLeaves[arg.resource.id] || null;
				const isActive = leave && leave.from_date <= currentCalDate && currentCalDate <= leave.to_date;

				let avatarHtml;
				if (image) {
					avatarHtml = `<img class="emp-avatar" src="${frappe.utils.escape_html(image)}" alt="" />`;
				} else {
					const initials = name.split(" ").slice(0, 2).map((w) => w[0]?.toUpperCase() || "").join("");
					avatarHtml = `<span class="emp-avatar-placeholder">${initials}</span>`;
				}

				const statusDots = [
					{ key: "Open",      color: "#ef4444", label: __("Open") },
					{ key: "Closed",    color: "#22c55e", label: __("Closed") },
					{ key: "Cancelled", color: "#636363", label: __("Cancelled") },
				].map(s => {
					const n = counts[s.key] || 0;
					return `<span title="${s.label}: ${n}" style="
						display:inline-flex;align-items:center;gap:2px;
						font-size:0.65rem;font-weight:600;
						background:${s.color}22;color:${s.color};
						border:1px solid ${s.color}55;
						border-radius:10px;padding:1px 5px;line-height:1.4;
					">${n}</span>`;
				}).join("");

				const totalBadge = `<span title="${__("Total")}: ${counts.total}" style="
					font-size:0.7rem;font-weight:700;
					background:var(--bg-blue);color:var(--text-on-blue,#fff);
					border-radius:10px;padding:1px 7px;line-height:1.4;
					background:#6366f1;color:#fff;
				">${counts.total}</span>`;

				let leaveBadge = "";
				if (leave) {
					const label = isActive
						? `🚫 ${__("On Leave until")} ${leave.to_date}`
						: `🏖️ ${__("Leave")} ${leave.from_date} → ${leave.to_date}`;
					const bg    = isActive ? "#fee2e2" : "#fef9c3";
					const color = isActive ? "#b91c1c" : "#92400e";
					leaveBadge = `<div title="${label}" style="
						font-size:0.62rem;font-weight:600;
						background:${bg};color:${color};
						border-radius:8px;padding:1px 6px;
						white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
						max-width:100%;margin-top:2px;
					">${label}</div>`;
				}

				const el = document.createElement("div");
				el.style.cssText = "display:flex;flex-direction:column;align-items:center;gap:4px;width:100%;padding:4px 2px;box-sizing:border-box;";
				el.innerHTML = `
					<div style="display:flex;align-items:center;gap:6px;justify-content:center;width:100%;overflow:hidden;">
						<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${frappe.utils.escape_html(name)}</span>
						${totalBadge}
					</div>
					<div style="display:flex;gap:4px;justify-content:center;flex-wrap:wrap;">
						${statusDots}
					</div>
					${leaveBadge}
				`;
				return { domNodes: [el] };
			},

			events(fetchInfo, successCallback, failureCallback) {
				const customer  = customerControl.get_value() || null;
				const department = deptControl?.get_value() || null;
				const service   = serviceControl?.get_value() || null;
				// Always derive the visible date from fetchInfo — never from dateControl
				const fetchDate = fetchInfo.startStr.split("T")[0];

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
						department: department,
						service: service,
					},
					callback(r) {
						const raw = r.message.events || [];
						const mapped = raw.map((e) => {
							const isBg = e.rendering === "background";
							return {
								id: e.name,
								resourceId: e.employee,
								title: e.title || e.customer_name || "",
								start: parseEventDate(e.scheduled_time),
								end: parseEventDate(e.scheduled_end_time),
								backgroundColor: e.color || "#5e64ff",
								borderColor:     e.color || "#5e64ff",
								textColor: getContrastColor(e.color),
								display:    isBg ? "background" : "block",
								classNames: isBg ? ["fc-bg-event"] : [],
								extendedProps: {
									url: e.url || null,
									status: e.status,
									customer: e.customer_name,
									service: e.service_name,
									phone: e.customer_phone_number,
									employee: e.employee,
									item_group: e.department,
									is_bride: e.is_bride,
									special_request: e.special_request || false,
									paid_deposit: e.paid_deposit || false,
									has_unpaid_invoice: e.has_unpaid_invoice || false,
									unpaid_amount: e.unpaid_amount || 0,
								},
							};
						});

						// ── Shift background events ───────────────────────
						// Built here using the live fetchDate so they are always
						// correct when navigating dates without a full rebuild.
						const slotMin = "11:00:00";
						const slotMax = "22:00:00";
						const shiftEvents = [];

						Object.entries(employeeShifts).forEach(([empId, shift]) => {
							if (shift.unavailable) {
								shiftEvents.push({
									id: `unavail-${empId}-${fetchDate}`,
									resourceId: empId,
									start: `${fetchDate}T${slotMin}`,
									end:   `${fetchDate}T${slotMax}`,
									display: "background",
									backgroundColor: "rgba(0,0,0,0.45)",
								});
							} else {
								if (shift.start && shift.start > slotMin) {
									shiftEvents.push({
										id: `pre-${empId}-${fetchDate}`,
										resourceId: empId,
										start: `${fetchDate}T${slotMin}`,
										end:   `${fetchDate}T${shift.start}`,
										display: "background",
										backgroundColor: "rgba(0,0,0,0.45)",
									});
								}
								if (shift.end && shift.end < slotMax) {
									shiftEvents.push({
										id: `post-${empId}-${fetchDate}`,
										resourceId: empId,
										start: `${fetchDate}T${shift.end}`,
										end:   `${fetchDate}T${slotMax}`,
										display: "background",
										backgroundColor: "rgba(0,0,0,0.45)",
									});
								}
							}
						});

						// successCallback([...mapped, ...shiftEvents]);

						const counts = {};
						mapped.forEach(ev => {
							if (ev.display === "background") return;
							const id = ev.resourceId;
							if (!id) return;
							if (!counts[id]) counts[id] = { total: 0, Open: 0, Closed: 0, Cancelled: 0 };
							counts[id].total++;
							const status = ev.extendedProps.status;
							if (status in counts[id]) counts[id][status]++;
						});

						employeeEventCounts = counts;
						successCallback([...mapped, ...shiftEvents]);

						// Re-render resource labels now that counts are known
						if (calendarInstance) {
							calendarInstance.refetchResources();
						}
					},
					error: failureCallback,
				});
			},

			eventDidMount(info) {
				const isRTL = frappe.boot.lang === "ar";

				if (info.event.display === "background") return;
				const p = info.event.extendedProps;

				if (p.is_bride === 1) {
					const stripColor = "#54008d"
					
					info.el.style.setProperty("border-left", `8px solid ${stripColor}`, "important");
				} else {
					const groupStrips = {
						"باقات العرائس": "#54008d"
					}
			
					const stripColor = groupStrips[p.item_group];
					if (stripColor) {
						info.el.style.setProperty("border-left", `8px solid ${stripColor}`, "important");
					}
				}

				if (p.paid_deposit) {					
					info.el.style.setProperty("border-right", `8px solid green`, "important");

				}
				if (p.special_request) {
					const badge = document.createElement("span");
					badge.textContent = "⭐";
					badge.style.cssText = `
						position: absolute;
						top: 2px;
						${isRTL ? "left" : "right"}: 3px;
						font-size: 16px;
						line-height: 1;
						pointer-events: none;
					`;
					info.el.style.position = "relative";
					info.el.appendChild(badge);
				}

				if (p.has_unpaid_invoice) {
					const unpaidBadge = document.createElement("span");
					unpaidBadge.textContent = "⚠";
					unpaidBadge.title = __("Unpaid Sales Invoice");
					unpaidBadge.style.cssText = `
						position: absolute;
						top: 2px;
						${isRTL ? "right" : "left"}: 3px;
						font-size: 13px;
						line-height: 1;
						background: #dc2626;
						color: #fff;
						border-radius: 50%;
						width: 15px;
						height: 15px;
						display: flex;
						align-items: center;
						justify-content: center;
						pointer-events: none;
					`;
					info.el.style.position = "relative";
					info.el.appendChild(unpaidBadge);
				}

				// ── Tooltip (unchanged) ────────────────────────────────
				$(info.el).tooltip({
					title: [
						p.customer ? `<b>${frappe.utils.escape_html(p.customer)}</b>` : "",
						p.service  ? frappe.utils.escape_html(p.service) : "",
						p.phone    ? `📞 ${frappe.utils.escape_html(p.phone)}` : "",
						p.status   ? `<span class="indicator ${statusIndicatorClass(p.status)}">${p.status}</span>` : "",
						p.special_request ? `<span style="color:#f59e0b">⭐ ${p.employee}</span>` : "",
						p.paid_deposit ? `<span>$ Paid</span>` : "",
						p.has_unpaid_invoice ? `<span style="color:#f87171">⚠ ${__("Unpaid")}: ${format_currency(p.unpaid_amount)}</span>` : "",
					].filter(Boolean).join("<br>"),
					html: true, placement: "top", container: "body", trigger: "hover",
				});
			},

			eventClick(info) {
				if (info.event.display === "background") return;
				info.jsEvent.preventDefault();
				const url = info.event.extendedProps.url;

				if (url) {
					window.open(url, "_blank");
				} else {
					const route = `/app/appointment/${info.event.id}`;
					window.open(route, "_blank");
				}
			},

			// datesSet fires when the calendar's visible date changes (prev/next/today).
			// We suppress it during programmatic gotoDate calls to avoid loops.
			datesSet(info) {
				document.getElementById("emp-cal-title").textContent = info.view.title;
				
				if (_suppressDateChange) return;
				
				pushFiltersToUrl();
				
				const newDate = info.startStr.split("T")[0];
				if (dateControl?.get_value() === newDate) return;

				// Update the date picker silently — the picker's onchange is
				// suppressed so it won't trigger another navigateToDate call.
				_suppressDateChange = true;
				dateControl.set_value(newDate);
				setTimeout(() => { _suppressDateChange = false; }, 0);

				// Fetch fresh shift data and refetch events for the new date.
				navigateToDate(newDate);
			},

			select(info) {
				const employee = info.resource?.id || null;
				const employeeName = info.resource?.title || null;
				const selected_date = info.startStr.split("T")[0];
				const start = info.startStr.replace("T", " ").slice(0, 19);
				frappe.route_options = {
					selected_date: selected_date,
					scheduled_time: start,
					department: selectedDept,
					customer: selectedCustomer,
					service: selectedService,
					...(employee ? { employee, employee_name: employeeName } : {}),
				};
				frappe.new_doc("Appointment");
			},

			selectAllow(selectInfo) {
				const employee = selectInfo.resource?.id;
				if (!employee || !employeeShifts[employee]) return true;
				const shift = employeeShifts[employee];
				if (shift.unavailable) return false;
				const timeStr = selectInfo.startStr.split("T")[1]?.slice(0, 8);
				const endStr  = selectInfo.endStr.split("T")[1]?.slice(0, 8);
				if (!shift.start || !shift.end) return false;
				return timeStr >= shift.start && endStr <= shift.end;
			},

			editable: true,
			eventResourceEditable: true, // allow dragging between employee columns

			// Prevent dropping into blocked (shift/unavailable) zones
			eventAllow(dropInfo, draggedEvent) {
				if (draggedEvent.display === "background") return false;
				const employee = dropInfo.resource?.id;
				if (!employee || !employeeShifts[employee]) return true;
				const shift = employeeShifts[employee];
				if (shift.unavailable) return false;
				const timeStr = dropInfo.startStr.split("T")[1]?.slice(0, 8);
				const endStr  = dropInfo.endStr.split("T")[1]?.slice(0, 8);
				if (!shift.start || !shift.end) return true;
				return timeStr >= shift.start && endStr <= shift.end;
			},

			eventDragStart(info) {
				// Destroy tooltip while dragging to avoid ghost tooltips
				$(info.el).tooltip("destroy");
				$(".tooltip").remove();
				const killTooltips = () => $(".tooltip").remove();
				document._calTooltipKiller = setInterval(killTooltips, 50);
			},

			eventDragStop(info) {
				clearInterval(document._calTooltipKiller);
				document._calTooltipKiller = null;
				$(".tooltip").remove();
			},

			eventDrop(info) {
				const event       = info.event;
				const newStart    = event.startStr.replace("T", " ").slice(0, 19);
				const newEnd      = event.endStr ? event.endStr.replace("T", " ").slice(0, 19) : null;
				const newEmployee = event.getResources()[0]?.id || null;

				frappe.confirm(
					__("Update appointment time{0}?", [newEmployee ? __(" and employee") : ""]),
					() => {
						const values = { scheduled_time: newStart };
						if (newEnd)      values.scheduled_end_time = newEnd;
						if (newEmployee) values.employee = newEmployee;

						frappe.call({
							method: "frappe.client.set_value",
							args: { doctype: "Appointment", name: event.id, fieldname: values },
							callback(r) {
								if (r.exc) {
									frappe.msgprint(__("Failed to update appointment."));
									info.revert();
								} else {
									calendarInstance.refetchEvents(); // ← add this
								}
							},
							error() { info.revert(); },
						});
					},
					() => info.revert() // cancelled — snap back
				);
			},

			eventResize(info) {
				const event  = info.event;
				const newEnd = event.endStr ? event.endStr.replace("T", " ").slice(0, 19) : null;
				if (!newEnd) { info.revert(); return; }

				frappe.confirm(
					__("Update appointment end time?"),
					() => {
						frappe.call({
							method: "frappe.client.set_value",
							args: { doctype: "Appointment", name: event.id, fieldname: { scheduled_end_time: newEnd } },
							callback(r) {
								if (r.exc) {
									frappe.msgprint(__("Failed to update appointment."));
									info.revert();
								} else {
									calendarInstance.refetchEvents();
								}
							},
							error() { info.revert(); },
						});
					},
					() => info.revert()
				);
			},
		});

		// Build shifts BEFORE render so the events callback has correct data
		// on the very first fetch.
		buildShifts(visibleEmployees, calDate);

		calendarInstance.render();

		// Navigate to the requested date without triggering datesSet → navigateToDate
		// _suppressDateChange = true;
		// calendarInstance.gotoDate(calDate);
		// setTimeout(() => { _suppressDateChange = false; }, 0);

		// ── Toolbar buttons ───────────────────────────────────────────────────
		// prev/next/today let the calendar move itself; datesSet handles the rest.
		document.getElementById("emp-cal-prev").onclick  = () => calendarInstance.prev();
		document.getElementById("emp-cal-next").onclick  = () => calendarInstance.next();
		document.getElementById("emp-cal-today").onclick = () => calendarInstance.today();

		// Employee filter apply
		document.getElementById("emp-cal-apply").onclick = () => {
			const sel = document.getElementById("emp-cal-emp-select");
			const ids = Array.from(sel.selectedOptions).map((o) => o.value);
			const filtered = ids.length
				? allEmployees.filter((emp) => ids.includes(emp.name))
				: allEmployees;
			const d = dateControl?.get_value() || frappe.datetime.get_today();
			initCalendar(filtered, d);
		};

		document.getElementById("emp-cal-clear-filter").onclick = () => {
			selectedCustomer = null;
			selectedDept     = null;
			selectedService  = null;

			Promise.all([
				customerControl.set_value(""),
				deptControl.set_value(""),
				serviceControl.set_value(""),
			]).then(() => {
				pushFiltersToUrl();
				applyFilters();
			});
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
		applyFilters();

		// // Restore filters from URL
		// const saved = getFiltersFromUrl();

		// // const setDate     = saved.date     ? dateControl.set_value(saved.date)         : Promise.resolve();
		// const setCustomer = saved.customer ? customerControl.set_value(saved.customer) : Promise.resolve();
		// const setDept     = saved.dept     ? deptControl.set_value(saved.dept)         : Promise.resolve();
		// const setService  = saved.service  ? serviceControl.set_value(saved.service)   : Promise.resolve();

		// if (saved.customer) selectedCustomer = saved.customer;
		// if (saved.dept)     selectedDept     = saved.dept;
		// if (saved.service)  selectedService  = saved.service;

		// Promise.all([setCustomer, setDept, setService]).then(() => {
		// 	applyFilters();
		// });

		document.getElementById("emp-cal-fc").addEventListener("mousedown", () => {
			$(".tooltip").remove();
		}, true);
	});

	// ── Helpers ───────────────────────────────────────────────────────────────
	function parseEventDate(raw) {
		if (!raw) return null;
		// Detect DD-MM-YYYY HH:MM:SS  →  convert to ISO
		const dmyMatch = raw.match(/^(\d{2})-(\d{2})-(\d{4})\s(\d{2}:\d{2}:\d{2})$/);
		if (dmyMatch) {
			const [, dd, mm, yyyy, time] = dmyMatch;
			return `${yyyy}-${mm}-${dd}T${time}`;
		}
		// Already YYYY-MM-DD HH:MM:SS
		return raw.replace(" ", "T");
	}

	// ── URL filter persistence ────────────────────────────────────────────────
	function pushFiltersToUrl() {
		const date     = dateControl?.get_value();
		const customer = customerControl?.get_value();
		const dept     = deptControl?.get_value();
		const service  = serviceControl?.get_value();

		const params = new URLSearchParams();
		if (date)     params.set("date",     date);
		if (customer) params.set("customer", customer);
		if (dept)     params.set("dept",     dept);
		if (service)  params.set("service",  service);

		const paramStr = params.toString();
		// Store everything inside the hash so Frappe's router never strips it
		const newHash  = "employee-calendar" + (paramStr ? "?" + paramStr : "");
		history.replaceState(null, "", window.location.pathname + "#" + newHash);
	}

	function getFiltersFromUrl() {
		// Hash looks like:  #employee-calendar?date=2025-01-01&dept=...
		const hash     = window.location.hash.slice(1); // strip leading #
		const qIdx     = hash.indexOf("?");
		const params   = new URLSearchParams(qIdx >= 0 ? hash.slice(qIdx + 1) : "");
		return {
			date:     params.get("date")     || null,
			customer: params.get("customer") || null,
			dept:     params.get("dept")     || null,
			service:  params.get("service")  || null,
		};
	}

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