frappe.provide("salon");

$(document).on("page-change", function () {
    if (!salon._notif_bound) {
        salon._notif_bound = true;

        frappe.realtime.on("notification", function (data) {
            // frappe.utils.play_sound("email");
            new Audio("/assets/salon/audio/notification.mp3").play();
        });
    }
});