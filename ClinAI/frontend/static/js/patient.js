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

    // Timeline - parse the list string and create horizontal scrollable cards
    const timelineContent = document.getElementById('timelineContent');
    timelineContent.innerHTML = '';
    
    let timelineEvents = [];
    if (data.timeline && data.timeline !== "[]") {
      try {
        // Parse the string representation of the list
        timelineEvents = JSON.parse(data.timeline.replace(/'/g, '"'));
      } catch (e) {
        // If parsing fails, treat as single event
        timelineEvents = [data.timeline];
      }
    }

    if (timelineEvents.length > 0) {
      const cardsHtml = timelineEvents.map((event, index) => `
        <div class="timeline-card-wrapper">
          <div class="timeline-card-modern">
            <div class="timeline-card-header">
              <span class="timeline-badge">Event ${index + 1} of ${timelineEvents.length}</span>
            </div>
            <div class="timeline-card-content">
              ${event}
            </div>
          </div>
        </div>
      `).join('');
      
      timelineContent.innerHTML = `
        <div class="timeline-scroll-container">
          ${cardsHtml}
        </div>
        <style>
          .timeline-scroll-container {
            display: flex;
            overflow-x: auto;
            overflow-y: hidden;
            gap: 1rem;
            padding: 1rem 0;
            scroll-behavior: smooth;
          }
          
          .timeline-scroll-container::-webkit-scrollbar {
            height: 8px;
          }
          
          .timeline-scroll-container::-webkit-scrollbar-track {
            background: #f1f1f1;
            border-radius: 4px;
          }
          
          .timeline-scroll-container::-webkit-scrollbar-thumb {
            background: #4e73df;
            border-radius: 4px;
          }
          
          .timeline-card-wrapper {
            flex: 0 0 auto;
            min-width: 300px;
            max-width: 350px;
          }
          
          .timeline-card-modern {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 12px;
            padding: 0;
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
            overflow: hidden;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            height: 200px;
            display: flex;
            flex-direction: column;
          }
          
          .timeline-card-modern:hover {
            transform: translateY(-5px);
            box-shadow: 0 12px 35px rgba(0, 0, 0, 0.2);
          }
          
          .timeline-card-header {
            background: rgba(255, 255, 255, 0.2);
            padding: 12px 16px;
            backdrop-filter: blur(10px);
          }
          
          .timeline-badge {
            background: rgba(255, 255, 255, 0.9);
            color: #4e73df;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
          }
          
          .timeline-card-content {
            padding: 16px;
            color: white;
            font-size: 0.95rem;
            line-height: 1.5;
            flex: 1;
            display: flex;
            align-items: center;
            text-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
          }
        </style>
      `;
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