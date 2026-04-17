// admin_captain_shared.js

function formatCountLabel(count) {
    return count === 1 ? "1 volunteer" : `${count} volunteers`;
}

function getVolunteerDisplayName(volunteer) {
    if (typeof volunteer === "string") return volunteer;
    return volunteer.name || `${volunteer.firstName || ""} ${volunteer.lastName || ""}`.trim();
}

function isCaptain(volunteer) {
    if (!volunteer || typeof volunteer === "string") return false;

    const captainStatus = (volunteer.captain_status || volunteer.captainStatus || "").toString().toLowerCase();
    const role = (volunteer.role || "").toLowerCase();

    return captainStatus === "captain" || role === "captain";
}

function isAdmin(volunteer) {
    if (!volunteer || typeof volunteer === "string") return false;
    return (volunteer.role || "").toLowerCase() === "admin";
}

function openVolunteerPanel(volunteerJson) {
    const volunteer = JSON.parse(volunteerJson);

    document.getElementById("detailName").textContent = volunteer.name || "Volunteer";
    document.getElementById("detailEmail").textContent = volunteer.email || "None listed";
    document.getElementById("detailPhone").textContent = volunteer.phone || "None listed";

    document.getElementById("detailPanel").classList.add("open");
    document.getElementById("detailOverlay").classList.add("open");
}

const stationClassMap = {
    "Setup Team": "setup",
    "Teardown Team": "teardown",
    "Line Servers": "servers",
    "Kitchen": "kitchen",
    "Drink Station": "drinks",
    "Desserts": "desserts",
    "Busboys/sanitation": "busboys",
    "Dishwashers": "dishes",
    "Reserve": "reserve",
    "General Manager": "manager",
    "Greeters": "greeters",
    "Baked Potato Bar": "potato",
    "Salad Bar": "salad",
    "Vegan Station": "vegan",
    "Absent": "absent",
    "Other": "other"
};

function renderStationBoard(
    stationData,
    stationClassMap
) {
    const grid = document.getElementById("scheduleGrid");
    grid.innerHTML = "";

    Object.keys(stationData || {}).forEach(stationName => {
        if (stationName === "Other") return;

        const station = stationData[stationName];
        let volunteers = (station.volunteers || []).slice();

        volunteers.sort((a, b) => {
            const priority = r =>
                r === "admin" ? 0 :
                r === "captain" ? 1 : 2;

            const diff = priority((a.role || "").toLowerCase()) -
                         priority((b.role || "").toLowerCase());

            if (diff !== 0) return diff;

            return (a.name || "").localeCompare(b.name || "");
        });

        const cssClass = stationClassMap[stationName];
        if (!cssClass) return;

        const volunteerHTML = volunteers.length
            ? `<div class="volunteer-list">
                ${volunteers.map(v => `
                    <button class="volunteer-pill"
                        onclick='openVolunteerPanel(${JSON.stringify(JSON.stringify(v))})'>
                        ${getVolunteerDisplayName(v)}
                        ${isCaptain(v) ? " (C)" : ""}
                        ${isAdmin(v) ? " (A)" : ""}
                    </button>
                `).join("")}
               </div>`
            : `<div class="empty-state">No volunteers assigned</div>`;

        const card = document.createElement("div");
        card.className = `card ${cssClass}`;

        card.innerHTML = `
            <div class="card-top">
                <h3>${stationName}</h3>
                <div class="station-count">
                    ${formatCountLabel(volunteers.length)}
                </div>
            </div>
            ${volunteerHTML}
        `;

        grid.appendChild(card);
    });
}

/* 🔥 Make them global */
window.renderStationBoard = renderStationBoard;
window.openVolunteerPanel = openVolunteerPanel;