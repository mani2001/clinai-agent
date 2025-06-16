// Get patient ID from URL
const patientId = window.location.pathname.split('/').pop();

async function fetchPatientData() {
  try {
    const response = await fetch(`/api/patient/${patientId}`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();

    // Log data for debugging
    console.log('[Patient Data]', data);

    // Use the extracted demographics directly from MongoDB
    document.getElementById('patientName').textContent = data.name || 'N/A';
    document.getElementById('patientAge').textContent = data.age || 'N/A';
    document.getElementById('patientGender').textContent = data.gender || 'N/A';

    // Summary
    document.getElementById('summaryContent').textContent = data.summary || 'No summary available.';

    // Prescriptions - handle as string since it's stored as text
    const prescriptionsTable = document.getElementById('prescriptionsTable');
    prescriptionsTable.innerHTML = '';
    if (data.prescriptions && data.prescriptions !== "No prescriptions found.") {
      prescriptionsTable.innerHTML = `<tr><td colspan="3">${data.prescriptions}</td></tr>`;
    } else {
      prescriptionsTable.innerHTML = '<tr><td colspan="3">No prescriptions available.</td></tr>';
    }

    // Timeline - handle as string since it's stored as text
    const timelineContent = document.getElementById('timelineContent');
    timelineContent.innerHTML = '';
    if (data.timeline && data.timeline !== "[]") {
      const card = document.createElement('div');
      card.className = 'timeline-card';
      card.textContent = data.timeline;
      timelineContent.appendChild(card);
    } else {
      timelineContent.innerHTML = '<div>No timeline events available.</div>';
    }

    // Keywords - handle as string since it's stored as comma-separated
    const keywordsInput = document.getElementById('keywordsInput');
    if (data.keywords && data.keywords !== "No main keywords found.") {
      keywordsInput.value = data.keywords;
    } else {
      keywordsInput.value = '';
    }
  } catch (error) {
    console.error('Error fetching patient data:', error);
    alert('Failed to load patient data: ' + error.message);
  }
}

// Save keywords
document.getElementById('saveKeywordsBtn')?.addEventListener('click', async () => {
  const keywords = document.getElementById('keywordsInput').value;
  try {
    const response = await fetch(`/patient/${patientId}/keywords`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keywords })
    });
    const result = await response.json();
    if (response.ok) {
      alert(result.message || 'Keywords saved successfully!');
    } else {
      alert(result.error || 'Failed to save keywords.');
    }
  } catch (error) {
    alert('Error saving keywords: ' + error.message);
  }
});

// Fetch data on load
fetchPatientData();