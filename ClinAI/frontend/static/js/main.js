// Local storage setup
const recentSearches = JSON.parse(localStorage.getItem('recentSearches')) || [];
const userPreferences = JSON.parse(localStorage.getItem('userPreferences')) || {
    useAgent: true
};

// DOM elements
const patientSearch = document.getElementById('patientSearch');
const searchButton = document.getElementById('searchButton');
const patientSearchDropdown = document.getElementById('patientSearchDropdown');
const displayPatientId = document.getElementById('displayPatientId');
const loadingSpinner = document.getElementById('loadingSpinner');
const historyContent = document.getElementById('historyContent');
const prescriptionsContent = document.getElementById('prescriptionsContent');
const meetingsContent = document.getElementById('meetingsContent');
const agentToggle = document.getElementById('agentToggle');

// Toggle
if (agentToggle) {
    agentToggle.checked = userPreferences.useAgent;
    agentToggle.addEventListener('change', () => {
        userPreferences.useAgent = agentToggle.checked;
        localStorage.setItem('userPreferences', JSON.stringify(userPreferences));
    });
}

function updateRecentSearchesDropdown() {
    while (patientSearchDropdown.children.length > 1) {
        patientSearchDropdown.removeChild(patientSearchDropdown.lastChild);
    }

    if (recentSearches.length === 0) {
        const li = document.createElement('li');
        const span = document.createElement('span');
        span.className = 'dropdown-item disabled';
        span.textContent = 'No recent searches';
        li.appendChild(span);
        patientSearchDropdown.appendChild(li);
    } else {
        recentSearches.forEach(patientId => {
            const li = document.createElement('li');
            const a = document.createElement('a');
            a.className = 'dropdown-item';
            a.href = '#';
            a.textContent = patientId;
            a.addEventListener('click', e => {
                e.preventDefault();
                patientSearch.value = patientId;
                fetchPatientData(patientId);
            });
            li.appendChild(a);
            patientSearchDropdown.appendChild(li);
        });
    }
}

function addToRecentSearches(patientId) {
    const index = recentSearches.indexOf(patientId);
    if (index !== -1) {
        recentSearches.splice(index, 1);
    }
    recentSearches.unshift(patientId);
    if (recentSearches.length > 5) {
        recentSearches.pop();
    }
    localStorage.setItem('recentSearches', JSON.stringify(recentSearches));
    updateRecentSearchesDropdown();
}

function createTimelineItem(eventText) {
    const card = document.createElement('div');
    card.className = 'item-card';
    card.innerHTML = `<div class="item-event">${eventText}</div>`;
    return card;
}

function createPrescriptionItem(item) {
    const card = document.createElement('div');
    card.className = 'item-card';
    let content = '';
    if (item.drug) content += `<div class="item-title">${item.drug}</div>`;
    if (item.route) content += `<div><strong>Route:</strong> ${item.route}</div>`;
    if (item.dose) content += `<div><strong>Dosage:</strong> ${item.dose}</div>`;
    if (item.status) content += `<div><strong>Status:</strong> ${item.status}</div>`;
    card.innerHTML = content || 'No details available';
    return card;
}

function createKeywordItem(keyword) {
    const card = document.createElement('div');
    card.className = 'item-card';
    card.innerHTML = `<div class="item-event">${keyword}</div>`;
    return card;
}

function displayPatientData(data) {
    historyContent.innerHTML = '';
    prescriptionsContent.innerHTML = '';
    meetingsContent.innerHTML = '';

    // Timeline → History - REMOVED, just show empty
    historyContent.innerHTML = '<div class="empty-tab-message">No history available</div>';

    // Prescriptions - REMOVED, just show empty
    prescriptionsContent.innerHTML = '<div class="empty-tab-message">No prescriptions available</div>';

    // Keywords (used as stand-in for "meetings")
    if (data.keywords && data.keywords.length > 0) {
        data.keywords.forEach(keyword => {
            meetingsContent.appendChild(createKeywordItem(keyword));
        });
    } else {
        meetingsContent.innerHTML = '<div class="empty-tab-message">No keywords available</div>';
    }
}

async function fetchPatientData(patientId) {
    if (!patientId) {
        alert('Please enter a Patient ID');
        return;
    }

    displayPatientId.textContent = patientId;
    loadingSpinner.style.display = 'block';

    try {
        const url = `/patient/${patientId}/details`;
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        displayPatientData(data);
        addToRecentSearches(patientId);
        localStorage.setItem('lastSelectedPatient', patientId);
    } catch (error) {
        console.error('Error fetching patient data:', error);
        ['historyContent', 'prescriptionsContent', 'meetingsContent'].forEach(id => {
            document.getElementById(id).innerHTML = '<div class="empty-tab-message">Error loading patient data</div>';
        });
    } finally {
        loadingSpinner.style.display = 'none';
    }
}

// Initial UI setup
updateRecentSearchesDropdown();
const lastSelectedPatient = localStorage.getItem('lastSelectedPatient');
if (lastSelectedPatient) {
    patientSearch.value = lastSelectedPatient;
    fetchPatientData(lastSelectedPatient);
}

searchButton.addEventListener('click', () => {
    const patientId = patientSearch.value.trim();
    if (patientId) {
        fetchPatientData(patientId);
    }
});

patientSearch.addEventListener('keypress', e => {
    if (e.key === 'Enter') {
        const patientId = patientSearch.value.trim();
        if (patientId) {
            fetchPatientData(patientId);
        }
    }
});