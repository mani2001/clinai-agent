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

    // Prescriptions - make it editable with add/delete functionality
    const prescriptionsTable = document.getElementById('prescriptionsTable');
    prescriptionsTable.innerHTML = '';
    
    // Create editable prescriptions interface
    const prescriptionsContainer = prescriptionsTable.parentElement;
    prescriptionsContainer.innerHTML = `
      <div class="prescriptions-header d-flex justify-content-between align-items-center mb-3">
        <h6 class="mb-0">Prescriptions</h6>
        <button class="btn btn-sm btn-success" id="addPrescriptionBtn">
          <i class="bi bi-plus-circle"></i> Add Prescription
        </button>
      </div>
      <div id="prescriptionsList">
        <!-- Prescriptions will be loaded here -->
      </div>
      <div class="prescriptions-actions mt-3">
        <button class="btn btn-primary" id="savePrescriptionsBtn">
          <i class="bi bi-save"></i> Save Prescriptions
        </button>
        <button class="btn btn-secondary ms-2" id="cancelPrescriptionsBtn">
          <i class="bi bi-x-circle"></i> Cancel
        </button>
      </div>
    `;

    // Load existing prescriptions
    let prescriptions = [];
    if (data.prescriptions && data.prescriptions !== "No prescriptions found.") {
      // Parse the formatted prescription string back into objects
      const prescriptionLines = data.prescriptions.split('\n').filter(line => line.trim());
      prescriptions = prescriptionLines.map(line => {
        const prescription = { drug: '', dose: '', route: '', status: 'active' };
        
        // Parse each line: "Drug: X, Dose: Y, Route: Z, Status: W"
        const parts = line.split(', ');
        parts.forEach(part => {
          const [key, value] = part.split(': ');
          if (key && value) {
            const cleanKey = key.toLowerCase().trim();
            const cleanValue = value.trim();
            if (cleanKey === 'drug') prescription.drug = cleanValue;
            else if (cleanKey === 'dose') prescription.dose = cleanValue;
            else if (cleanKey === 'route') prescription.route = cleanValue;
            else if (cleanKey === 'status') prescription.status = cleanValue;
          }
        });
        
        return prescription;
      });
    }

    function renderPrescriptions() {
      const prescriptionsList = document.getElementById('prescriptionsList');
      prescriptionsList.innerHTML = '';

      if (prescriptions.length === 0) {
        prescriptionsList.innerHTML = '<div class="text-muted">No prescriptions added yet.</div>';
        return;
      }

      prescriptions.forEach((prescription, index) => {
        const prescriptionCard = document.createElement('div');
        prescriptionCard.className = 'prescription-card mb-3 p-3 border rounded';
        prescriptionCard.innerHTML = `
          <div class="row">
            <div class="col-md-3">
              <label class="form-label">Drug Name</label>
              <input type="text" class="form-control" value="${prescription.drug || ''}" 
                     onchange="updatePrescription(${index}, 'drug', this.value)">
            </div>
            <div class="col-md-2">
              <label class="form-label">Dose</label>
              <input type="text" class="form-control" value="${prescription.dose || ''}" 
                     onchange="updatePrescription(${index}, 'dose', this.value)">
            </div>
            <div class="col-md-2">
              <label class="form-label">Route</label>
              <select class="form-control" onchange="updatePrescription(${index}, 'route', this.value)">
                <option value="">Select</option>
                <option value="oral" ${prescription.route === 'oral' ? 'selected' : ''}>Oral</option>
                <option value="injection" ${prescription.route === 'injection' ? 'selected' : ''}>Injection</option>
                <option value="topical" ${prescription.route === 'topical' ? 'selected' : ''}>Topical</option>
                <option value="inhalation" ${prescription.route === 'inhalation' ? 'selected' : ''}>Inhalation</option>
                <option value="other" ${prescription.route === 'other' ? 'selected' : ''}>Other</option>
              </select>
            </div>
            <div class="col-md-2">
              <label class="form-label">Status</label>
              <select class="form-control" onchange="updatePrescription(${index}, 'status', this.value)">
                <option value="active" ${prescription.status === 'active' ? 'selected' : ''}>Active</option>
                <option value="discontinued" ${prescription.status === 'discontinued' ? 'selected' : ''}>Discontinued</option>
                <option value="completed" ${prescription.status === 'completed' ? 'selected' : ''}>Completed</option>
              </select>
            </div>
            <div class="col-md-3 d-flex align-items-end">
              <button class="btn btn-danger btn-sm w-100" onclick="deletePrescription(${index})">
                <i class="bi bi-trash"></i> Delete
              </button>
            </div>
          </div>
        `;
        prescriptionsList.appendChild(prescriptionCard);
      });
    }

    // Global functions for prescription management
    window.updatePrescription = function(index, field, value) {
      prescriptions[index][field] = value;
    };

    window.deletePrescription = function(index) {
      if (confirm('Are you sure you want to delete this prescription?')) {
        prescriptions.splice(index, 1);
        renderPrescriptions();
        
        // Auto-save after deletion
        savePrescriptions();
      }
    };

    // Extract save functionality into a separate function
    async function savePrescriptions() {
      try {
        // Convert prescriptions array to formatted string
        const prescriptionsText = prescriptions.length > 0 ? 
          prescriptions.map(p => 
            `Drug: ${p.drug || 'N/A'}, Dose: ${p.dose || 'N/A'}, Route: ${p.route || 'N/A'}, Status: ${p.status || 'active'}`
          ).join('\n') : 
          'No prescriptions found.';

        const response = await fetch(`/patient/${patientId}/prescriptions`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prescriptions: prescriptionsText })
        });

        const result = await response.json();
        if (response.ok) {
          console.log('Prescriptions saved successfully');
          return true;
        } else {
          alert(result.error || 'Failed to save prescriptions.');
          return false;
        }
      } catch (error) {
        alert('Error saving prescriptions: ' + error.message);
        return false;
      }
    }

    // Add prescription button
    document.getElementById('addPrescriptionBtn').addEventListener('click', () => {
      prescriptions.push({ drug: '', dose: '', route: '', status: 'active' });
      renderPrescriptions();
    });

    // Save prescriptions button
    document.getElementById('savePrescriptionsBtn').addEventListener('click', async () => {
      const success = await savePrescriptions();
      if (success) {
        alert('Prescriptions saved successfully!');
      }
    });

    // Cancel button
    document.getElementById('cancelPrescriptionsBtn').addEventListener('click', () => {
      // Reload the page to cancel changes
      location.reload();
    });

    // Initial render
    renderPrescriptions();

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