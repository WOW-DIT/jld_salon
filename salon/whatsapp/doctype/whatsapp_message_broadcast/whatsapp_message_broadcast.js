// Copyright (c) 2025, salon and contributors
// For license information, please see license.txt

frappe.ui.form.on("WhatsApp Message Broadcast", {
	refresh(frm) {
        if(!frm.doc.name.startsWith("new")) {
            // Realtime listener
            frappe.realtime.on(`whatsapp_broadcast_progress_${frm.doc.name}`, function(data) {
                
                if(!data.step) {
                    frappe.show_progress(
                        __("Sending WhatsApp Messages"),
                        data.percent,
                        100,
                        data.message
                    );
                }

                if (data.step === "done") {
                    frappe.show_alert({message: __("Broadcast completed ✅"), indicator: 'green'});
                    frappe.hide_progress();
                    location.reload();
                }
                
                if (data.step === "error" || data.step === "failed") {
                    frappe.show_alert({message: data.message, indicator: 'red'});
                    frappe.hide_progress();
                }
            });

            if(frm.doc.sending_status === "Pending") {
                frm.add_custom_button(__("Send"), function () {
                    sendMessage(frm);
                }).addClass("btn-primary");

            } else if(frm.doc.sending_status === "Sending") {
                frm.add_custom_button(__("Cancel"), function () {
                    cancelSending(frm);
                }).addClass("btn-primary");

            } else if(frm.doc.sending_status === "Partially Sent") {
                frm.add_custom_button(__("Continue"), function () {
                    sendMessage(frm);
                }).addClass("btn-primary");
                
            } else if(frm.doc.sending_status === "Sent") {

            } else {
                // frm.add_custom_button(__("Retry"), function () {
                //     frappe.msgprint("Button clicked");
                // }).addClass("btn-primary");
            }
        }
	},
    load_customers_numbers(frm) {
        getCustomersNumbers(frm);
    },
    download_excel_template(frm) {
		const link = "/files/list_of_numbers.xlsx";
		window.open(link);
	}
});


function getCustomersNumbers(frm) {
    let args = {
        by_group: frm.doc.filter_by_group,
        group: frm.doc.customer_group,
    };

    frappe.call({
        method: "salon.whatsapp.doctype.whatsapp_message_broadcast.whatsapp_message_broadcast.load_customers_numbers",
        args: args,
        freeze: true,
        freeze_message: __("Fetching Numbers..."),
        callback: function(res) {
            if(res && res.message) {
                const numbers = res.message;
                frm.set_value("customers_numbers", numbers.join("\n"))
            }
        }
    })
}

function sendMessage(frm) {
    frappe.call({
        method: "salon.whatsapp.doctype.whatsapp_message_broadcast.whatsapp_message_broadcast.start_broadcast",
        args: {
            docname: frm.doc.name,
        },
        callback: function(res) {
            frm.refresh();
            // if(res && res.message) {
            //     const numbers = res.message;
            //     frm.set_value("customers_numbers", numbers.join("\n"))
            // }
        }
    })
}


function cancelSending(frm) {
    frappe.call({
        method: "salon.whatsapp.doctype.whatsapp_message_broadcast.whatsapp_message_broadcast.cancel_broadcast",
        args: { docname: frm.doc.name },
        callback: function(res) {
            frm.refresh();
        }
    });

    frappe.show_alert({
        message: __("Cancellation requested ⏹️"),
        indicator: "orange"
    });
}