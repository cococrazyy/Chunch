// admin_captian_shared.js

export function formatCountLabel(count) {
    return count === 1 ? "1 volunteer" : `${count} volunteers`;
}

export function getVolunteerDisplayName(volunteer) {
    if (typeof volunteer === "string") return volunteer;
    return volunteer.name || `${volunteer.firstName || ""} ${volunteer.lastName || ""}`.trim();
}

export function isCaptain(volunteer) {
    if (!volunteer || typeof volunteer === "string") return false;

    const captainStatus = (volunteer.captain_status || volunteer.captainStatus || "").toString().toLowerCase();
    const role = (volunteer.role || "").toString().toLowerCase();

    return captainStatus === "captain" || role === "captain";
}

export function isAdmin(volunteer) {
    if (!volunteer || typeof volunteer === "string") return false;
    return (volunteer.role || "").toString().toLowerCase() === "admin";
}

export function renderStationBoard({
    stationData,
    stationClassMap,
    getVolunteerDisplayName,
    isCaptain,
    isAdmin,
    openVolunteerPanel
}) {
    const grid = document.getElementById("scheduleGrid");
    grid.innerHTML = "";

    const stationNames = Object.keys(stationData || {});

    stationNames.forEach(stationName => {
        if (stationName === "Other") return;

        const station = stationData[stationName];
        let volunteers = (station.volunteers || []).slice();

        volunteers.sort((a, b) => {
            const roleA = (a.role || "").toLowerCase();
            const roleB = (b.role || "").toLowerCase();

            const priority = r =>
                r === "admin" ? 0 :
                r === "captain" ? 1 : 2;

            const diff = priority(roleA) - priority(roleB);
            if (diff !== 0) return diff;

            return (a.name || "").localeCompare(b.name || "");
        });

        const cssClass = stationClassMap[stationName];
        if (!cssClass) return;

        const volunteerHTML = volunteers.length
            ? `<div class="volunteer-list">
                ${volunteers.map(v => {
                    const displayName = getVolunteerDisplayName(v);
                    const displayTime = v.display_time ? ` (${v.display_time})` : "";

                    const captainBadge = isCaptain(v) ? " (C)" : "";
                    const adminBadge = isAdmin(v) ? " (A)" : "";

                    return `
                        <button class="volunteer-pill"
                            type="button"
                            onclick='openVolunteerPanel(${JSON.stringify(JSON.stringify(v))})'>
                            ${displayName}${captainBadge}${adminBadge}${displayTime}
                        </button>
                    `;
                }).join("")}
               </div>`
            : `<div class="empty-state">No volunteers assigned</div>`;

        const card = document.createElement("div");
        card.className = `card ${cssClass}`;

        card.innerHTML = `
            <div class="card-top">
                <h3>${stationName}</h3>
                <div class="station-count">
                    ${volunteers.length === 1 ? "1 volunteer" : `${volunteers.length} volunteers`}
                </div>
            </div>
            ${volunteerHTML}
        `;

        grid.appendChild(card);
    });
}