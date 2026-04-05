// Set the date display format to month day with
function formatDatePretty(dateStr) {
    if (!dateStr) return "";
    const d = new Date(dateStr);
    return d.toLocaleDateString(undefined, {
        month: "long",
        day: "numeric"
    });
}

// Set the hour display format to hour with AM or PM
function formatHourLabel(value) {
    if (value === 12) return "12PM";
    if (value < 12) return value + "AM";
    return (value - 12) + "PM";
}

// Make the phone number more readable e.g. (123) 456-7890 or +1 (123) 456-7890
function formatPhonePretty(phone) {
    if (phone.length === 10) {
        return `(${phone.slice(0,3)}) ${phone.slice(3,6)}-${phone.slice(6)}`;
    } else if (phone.length === 11 && phone[0] === '1') {
        return `+1 (${phone.slice(1,4)}) ${phone.slice(4,7)}-${phone.slice(7)}`;
    }
    return phone;
}