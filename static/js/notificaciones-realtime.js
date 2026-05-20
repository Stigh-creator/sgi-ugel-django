(function () {
    const bell = document.getElementById("notif-badge-container");
    if (!bell || !window.WebSocket) return;

    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const socketUrl = `${protocol}://${window.location.host}/ws/notificaciones/`;
    let socket = null;
    let retryTimer = null;

    function escapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = value || "";
        return div.innerHTML;
    }

    function updateBadge(count) {
        const button = bell.querySelector(".notification-bell-btn");
        if (!button) return;
        let badge = bell.querySelector(".notification-badge");
        if (count > 0) {
            if (!badge) {
                badge = document.createElement("span");
                badge.className = "notification-badge";
                button.appendChild(badge);
            }
            badge.textContent = count;
        } else if (badge) {
            badge.remove();
        }
        const unreadLabel = bell.querySelector(".notification-menu-header small");
        if (unreadLabel) unreadLabel.textContent = `${count} sin leer`;
    }

    function ensureReadAllButton(count) {
        const header = bell.querySelector(".notification-menu-header");
        if (!header) return;
        let form = header.querySelector("form");
        if (count > 0 && !form) {
            form = document.createElement("form");
            form.method = "post";
            form.action = bell.dataset.markReadUrl || "/notificaciones/marcar-leidas/";
            form.className = "m-0";
            form.innerHTML = `
                <input type="hidden" name="csrfmiddlewaretoken" value="${escapeHtml(bell.dataset.csrfToken || "")}">
                <button type="submit" class="notification-read-all no-loading">Leer todas</button>
            `;
            header.appendChild(form);
        } else if (count <= 0 && form) {
            form.remove();
        }
    }

    function prependNotification(data) {
        const list = bell.querySelector(".notification-list");
        if (!list) return;
        const empty = list.querySelector(".notification-empty");
        if (empty) empty.remove();

        const item = document.createElement("a");
        item.href = data.notification_user_id
            ? `/notificaciones/${data.notification_user_id}/leer/`
            : (data.link || "#");
        item.className = `notification-item is-unread priority-${data.prioridad || "media"}`;
        item.innerHTML = `
            <span class="notification-icon">
                <i class="bi ${escapeHtml(data.icon_class || "bi-bell")}"></i>
            </span>
            <span class="notification-content">
                <span class="notification-meta">
                    <span class="notification-priority">${escapeHtml(data.prioridad_label || "Media")}</span>
                    <span>Ahora</span>
                </span>
                <span class="notification-message">${escapeHtml(data.message || "")}</span>
            </span>
        `;
        list.prepend(item);

        while (list.querySelectorAll(".notification-item").length > 8) {
            list.querySelector(".notification-item:last-of-type")?.remove();
        }
    }

    function scheduleReconnect() {
        if (retryTimer) return;
        retryTimer = window.setTimeout(function () {
            retryTimer = null;
            connect();
        }, 3000);
    }

    function connect() {
        socket = new WebSocket(socketUrl);
        socket.onmessage = function (event) {
            const data = JSON.parse(event.data || "{}");
            const count = Number(data.unread_count || 0);
            updateBadge(count);
            ensureReadAllButton(count);
            prependNotification(data);
        };
        socket.onclose = scheduleReconnect;
        socket.onerror = function () {
            socket.close();
        };
    }

    connect();
})();
