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

    // Parse note for Name, Age, Gender with flexible regex
    const note = data.note || '';
    // Match Name: X or any word(s) before a comma or newline
    const nameMatch = note.match(/Name:\s*([^\n,]+)|^\s*([^\n,]+)/i);
    // Match Age: X or any number after a comma or label
    const ageMatch = note.match(/Age:\s*(\d+)|,\s*(\d+)/i);
    // Match Gender: X or M/F/Male/Female after a comma or label
    const genderMatch = note.match(/Gender:\s*([^\n,]+)|,\s*(Male|Female|M|F)/i);

    document.getElementById('patientName').textContent = nameMatch ? (nameMatch[1] || nameMatch[2] || '').trim() : 'N/A';
    document.getElementById('patientAge').textContent = ageMatch ? (ageMatch[1] || ageMatch[2] || 'N/A') : 'N/A';
    document.getElementById('patientGender').textContent = genderMatch ? (genderMatch[1] || genderMatch[2] || '').trim() : 'N/A';

    // Summary
    document.getElementById('summaryContent').textContent = data.summary || 'No summary available.';

    // Prescriptions
    const prescriptionsTable = document.getElementById('prescriptionsTable');
    prescriptionsTable.innerHTML = '';
    if (data.prescriptions && data.prescriptions.length > 0) {
      data.prescriptions.forEach(p => {
        const row = document.createElement('tr');
        row.innerHTML = `
          <td>${p.drug || 'N/A'}</td>
          <td>${p.dose || 'N/A'}</td>
          <td>${p.route || 'N/A'}</td>
        `;
        prescriptionsTable.appendChild(row);
      });
    } else {
      prescriptionsTable.innerHTML = '<tr><td colspan="3">No prescriptions available.</td></tr>';
    }

    // Timeline
    const timelineContent = document.getElementById('timelineContent');
    timelineContent.innerHTML = '';
    if (data.timeline && data.timeline.length > 0) {
      data.timeline.forEach(event => {
        const card = document.createElement('div');
        card.className = 'timeline-card';
        card.textContent = event || 'N/A';
        timelineContent.appendChild(card);
      });
    } else {
      timelineContent.innerHTML = '<div>No timeline events available.</div>';
    }

    // Keywords
    const keywordsInput = document.getElementById('keywordsInput');
    keywordsInput.value = data.keywords ? data.keywords.join(', ') : '';
  } catch (error) {
    console.error('Error fetching patient data:', error);
    alert('Failed to load patient data: ' + error.message);
  }
}

// Save keywords
document.getElementById('saveKeywordsBtn')?.addEventListener('click', async () => {
  const keywords = document.getElementById('keywordsInput').value.split(',').map(k => k.trim()).filter(k => k);
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