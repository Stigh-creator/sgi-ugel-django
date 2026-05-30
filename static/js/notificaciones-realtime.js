(function () {
    const bell = document.getElementById("notif-badge-container");
    if (!bell || !window.WebSocket) return;

    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const socketUrl = `${protocol}://${window.location.host}/ws/notificaciones/`;
    const soundStorageKey = "sgiNotificationSoundEnabled";
    const soundToggle = bell.querySelector(".notification-sound-toggle");
    let socket = null;
    let retryTimer = null;
    let audioContext = null;
    let soundEnabled = readStoredSoundPreference();

    function escapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = value || "";
        return div.innerHTML;
    }

    function readStoredSoundPreference() {
        try {
            return window.localStorage?.getItem(soundStorageKey) === "true";
        } catch (error) {
            return false;
        }
    }

    function getAudioContext() {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return null;
        if (!audioContext) audioContext = new AudioContext();
        return audioContext;
    }

    function setSoundEnabled(enabled) {
        soundEnabled = enabled;
        try {
            window.localStorage?.setItem(soundStorageKey, enabled ? "true" : "false");
        } catch (error) {
            // localStorage puede estar bloqueado en algunos navegadores.
        }

        if (!soundToggle) return;
        soundToggle.classList.toggle("is-enabled", enabled);
        soundToggle.setAttribute("aria-pressed", enabled ? "true" : "false");
        soundToggle.setAttribute(
            "title",
            enabled
                ? "Desactivar sonido de notificaciones"
                : "Activar sonido de prioridad alta y crítica"
        );
        const icon = soundToggle.querySelector("i");
        if (icon) {
            icon.className = enabled ? "bi bi-volume-up-fill" : "bi bi-volume-mute";
        }
    }

    function playTone(frequency, startTime, duration, volume) {
        const ctx = getAudioContext();
        if (!ctx) return;

        const oscillator = ctx.createOscillator();
        const gain = ctx.createGain();
        oscillator.type = "sine";
        oscillator.frequency.setValueAtTime(frequency, startTime);
        gain.gain.setValueAtTime(0.0001, startTime);
        gain.gain.exponentialRampToValueAtTime(volume, startTime + 0.015);
        gain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);
        oscillator.connect(gain);
        gain.connect(ctx.destination);
        oscillator.start(startTime);
        oscillator.stop(startTime + duration + 0.02);
    }

    function playNotificationSound(priority) {
        if (!soundEnabled) return;
        if (!["alta", "critica"].includes(priority)) return;

        const ctx = getAudioContext();
        if (!ctx) return;
        if (ctx.state === "suspended") {
            ctx.resume().catch(function () {});
        }

        const now = ctx.currentTime;
        if (priority === "critica") {
            playTone(880, now, 0.12, 0.08);
            playTone(1174, now + 0.16, 0.16, 0.08);
        } else {
            playTone(740, now, 0.12, 0.055);
        }
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
        const actions = bell.querySelector(".notification-actions") || header;
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
            actions.appendChild(form);
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
            playNotificationSound(data.prioridad || "media");
        };
        socket.onclose = scheduleReconnect;
        socket.onerror = function () {
            socket.close();
        };
    }

    if (soundToggle) {
        setSoundEnabled(soundEnabled);
        soundToggle.addEventListener("click", function (event) {
            event.preventDefault();
            event.stopPropagation();
            const nextState = !soundEnabled;
            if (nextState) {
                const ctx = getAudioContext();
                if (ctx && ctx.state === "suspended") {
                    ctx.resume().catch(function () {});
                }
                if (ctx) playTone(660, ctx.currentTime, 0.08, 0.045);
            }
            setSoundEnabled(nextState);
        });
    }

    connect();
})();
