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
    console.log('[Update Patient Data]', data);

    // Use the extracted demographics directly from MongoDB
    document.getElementById('patientName').textContent = data.name || 'N/A';
    document.getElementById('patientAge').textContent = data.age || 'N/A';
    document.getElementById('patientGender').textContent = data.gender || 'N/A';

    // Summary - make it editable
    const summaryContainer = document.getElementById('summaryContent').parentElement;
    summaryContainer.innerHTML = `
      <div class="summary-header d-flex justify-content-between align-items-center mb-3">
        <h6 class="mb-0">Summary</h6>
        <button class="btn btn-sm btn-outline-primary" id="editSummaryBtn">
          <i class="bi bi-pencil"></i> Edit Summary
        </button>
      </div>
      <div id="summaryDisplay" class="summary-display">
        ${data.summary || 'No summary available.'}
      </div>
      <div id="summaryEdit" class="summary-edit" style="display: none;">
        <textarea class="form-control mb-2" id="summaryTextarea" rows="6">${data.summary || ''}</textarea>
        <div class="summary-actions">
          <button class="btn btn-sm btn-success" id="saveSummaryBtn">
            <i class="bi bi-save"></i> Save Changes
          </button>
          <button class="btn btn-sm btn-secondary" id="cancelSummaryBtn">
            <i class="bi bi-x-circle"></i> Cancel
          </button>
        </div>
      </div>
    `;

    // Summary editing functionality
    document.getElementById('editSummaryBtn').addEventListener('click', () => {
      document.getElementById('summaryDisplay').style.display = 'none';
      document.getElementById('summaryEdit').style.display = 'block';
      document.getElementById('editSummaryBtn').style.display = 'none';
      document.getElementById('summaryTextarea').focus();
    });

    document.getElementById('cancelSummaryBtn').addEventListener('click', () => {
      document.getElementById('summaryDisplay').style.display = 'block';
      document.getElementById('summaryEdit').style.display = 'none';
      document.getElementById('editSummaryBtn').style.display = 'block';
      document.getElementById('summaryTextarea').value = data.summary || '';
    });

    document.getElementById('saveSummaryBtn').addEventListener('click', async () => {
      const newSummary = document.getElementById('summaryTextarea').value;
      try {
        const response = await fetch(`/patient/${patientId}/summary`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ summary: newSummary })
        });

        const result = await response.json();
        if (response.ok) {
          document.getElementById('summaryDisplay').textContent = newSummary;
          document.getElementById('summaryDisplay').style.display = 'block';
          document.getElementById('summaryEdit').style.display = 'none';
          document.getElementById('editSummaryBtn').style.display = 'block';
          alert('Summary updated successfully!');
        } else {
          alert(result.error || 'Failed to update summary.');
        }
      } catch (error) {
        alert('Error updating summary: ' + error.message);
      }
    });

    // Prescriptions - make it editable with add/delete functionality
    const prescriptionsTable = document.getElementById('prescriptionsTable');
    prescriptionsTable.innerHTML = '';
    
    // Create editable prescriptions interface
    const prescriptionsContainer = prescriptionsTable.parentElement;
    prescriptionsContainer.innerHTML = `
      <div class="prescriptions-header d-flex justify-content-between align-items-center mb-3">
        <h6 class="mb-0">Update Prescriptions</h6>
        <button class="btn btn-sm btn-success" id="addPrescriptionBtn">
          <i class="bi bi-plus-circle"></i> Add New Prescription
        </button>
      </div>
      <div id="prescriptionsList">
        <!-- Prescriptions will be loaded here -->
      </div>
      <div class="prescriptions-actions mt-3">
        <button class="btn btn-primary" id="savePrescriptionsBtn">
          <i class="bi bi-save"></i> Save All Changes
        </button>
        <button class="btn btn-secondary ms-2" id="cancelPrescriptionsBtn">
          <i class="bi bi-x-circle"></i> Cancel Changes
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
        prescriptionsList.innerHTML = '<div class="text-muted">No prescriptions added yet. Click "Add New Prescription" to get started.</div>';
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
                <i class="bi bi-trash"></i> Remove
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
      if (confirm('Are you sure you want to remove this prescription?')) {
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
          console.log('Prescriptions updated successfully');
          return true;
        } else {
          alert(result.error || 'Failed to update prescriptions.');
          return false;
        }
      } catch (error) {
        alert('Error updating prescriptions: ' + error.message);
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
        alert('Prescriptions updated successfully!');
      }
    });

    // Cancel button
    document.getElementById('cancelPrescriptionsBtn').addEventListener('click', () => {
      // Reload the page to cancel changes
      if (confirm('Are you sure you want to cancel all changes? This will reload the page.')) {
        location.reload();
      }
    });

    // Initial render
    renderPrescriptions();

    // Timeline - parse the list string and create horizontal scrollable cards with full editing
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

    // Timeline editing state
    let editingIndex = -1;

    function renderTimeline() {
      if (timelineEvents.length === 0) {
        timelineContent.innerHTML = `
          <div class="timeline-empty">
            <div>No timeline events available.</div>
            <button class="btn btn-primary mt-2" onclick="addTimelineEvent(0)">
              <i class="bi bi-plus-circle"></i> Add First Event
            </button>
          </div>
        `;
        return;
      }

      const cardsHtml = timelineEvents.map((event, index) => `
        <div class="timeline-card-wrapper" data-index="${index}">
          <div class="timeline-card-modern">
            <div class="timeline-card-header">
              <span class="timeline-badge">Event ${index + 1} of ${timelineEvents.length}</span>
              <div class="timeline-actions">
                <button class="btn-icon" onclick="editTimelineEvent(${index})" title="Edit Event">
                  <i class="bi bi-pencil"></i>
                </button>
                <button class="btn-icon" onclick="deleteTimelineEvent(${index})" title="Delete Event">
                  <i class="bi bi-trash"></i>
                </button>
              </div>
            </div>
            <div class="timeline-card-content" id="content-${index}">
              ${editingIndex === index ? `
                <textarea class="timeline-edit-textarea" id="edit-${index}">${event}</textarea>
                <div class="timeline-edit-actions">
                  <button class="btn btn-sm btn-success" onclick="saveTimelineEdit(${index})">Save</button>
                  <button class="btn btn-sm btn-secondary" onclick="cancelTimelineEdit()">Cancel</button>
                </div>
              ` : event}
            </div>
          </div>
        </div>
        ${index < timelineEvents.length - 1 ? `
          <div class="timeline-add-between">
            <button class="btn-add-between" onclick="addTimelineEvent(${index + 1})" title="Add Event">
              <i class="bi bi-plus"></i>
            </button>
          </div>
        ` : ''}
      `).join('');
      
      timelineContent.innerHTML = `
        <div class="timeline-controls-header">
          <button class="btn btn-primary btn-sm" onclick="saveAllTimelineChanges()">
            <i class="bi bi-save"></i> Save Timeline Changes
          </button>
          <button class="btn btn-secondary btn-sm" onclick="cancelAllTimelineChanges()">
            <i class="bi bi-x-circle"></i> Cancel Changes
          </button>
        </div>
        <div class="timeline-scroll-container">
          <div class="timeline-add-start">
            <button class="btn-add-start" onclick="addTimelineEvent(0)" title="Add First Event">
              <i class="bi bi-plus"></i>
            </button>
          </div>
          ${cardsHtml}
          <div class="timeline-add-end">
            <button class="btn-add-end" onclick="addTimelineEvent(${timelineEvents.length})" title="Add Event at End">
              <i class="bi bi-plus"></i>
            </button>
          </div>
        </div>
        <style>
          .timeline-controls-header {
            display: flex;
            gap: 10px;
            margin-bottom: 1rem;
            justify-content: flex-end;
          }
          
          .timeline-scroll-container {
            display: flex;
            overflow-x: auto;
            overflow-y: hidden;
            align-items: center;
            gap: 0;
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
            background: #f6c23e;
            border-radius: 4px;
          }
          
          .timeline-card-wrapper {
            flex: 0 0 auto;
            min-width: 300px;
            max-width: 350px;
          }
          
          .timeline-card-modern {
            background: linear-gradient(135deg, #f6c23e 0%, #e0aa3e 100%);
            border-radius: 12px;
            padding: 0;
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
            overflow: hidden;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            height: 250px;
            display: flex;
            flex-direction: column;
            margin: 0 10px;
          }
          
          .timeline-card-modern:hover {
            transform: translateY(-5px);
            box-shadow: 0 12px 35px rgba(0, 0, 0, 0.2);
          }
          
          .timeline-card-header {
            background: rgba(255, 255, 255, 0.2);
            padding: 12px 16px;
            backdrop-filter: blur(10px);
            display: flex;
            justify-content: space-between;
            align-items: center;
          }
          
          .timeline-badge {
            background: rgba(255, 255, 255, 0.9);
            color: #f6c23e;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
          }
          
          .timeline-actions {
            display: flex;
            gap: 5px;
          }
          
          .btn-icon {
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: white;
            padding: 5px 8px;
            border-radius: 6px;
            cursor: pointer;
            transition: background 0.2s;
          }
          
          .btn-icon:hover {
            background: rgba(255, 255, 255, 0.3);
          }
          
          .timeline-card-content {
            padding: 16px;
            color: white;
            font-size: 0.95rem;
            line-height: 1.5;
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            text-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
          }
          
          .timeline-edit-textarea {
            width: 100%;
            min-height: 80px;
            background: rgba(255, 255, 255, 0.9);
            color: #333;
            border: none;
            border-radius: 6px;
            padding: 10px;
            font-size: 0.9rem;
            resize: vertical;
          }
          
          .timeline-edit-actions {
            display: flex;
            gap: 5px;
            margin-top: 10px;
          }
          
          .timeline-add-between {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0 10px;
          }
          
          .timeline-add-start,
          .timeline-add-end {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0 15px;
          }
          
          .btn-add-between,
          .btn-add-start,
          .btn-add-end {
            background: rgba(246, 194, 62, 0.1);
            border: 2px dashed #f6c23e;
            color: #f6c23e;
            padding: 15px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.2rem;
            transition: all 0.3s ease;
            width: 50px;
            height: 50px;
            display: flex;
            align-items: center;
            justify-content: center;
          }
          
          .btn-add-between:hover,
          .btn-add-start:hover,
          .btn-add-end:hover {
            background: #f6c23e;
            color: white;
            transform: scale(1.1);
            box-shadow: 0 4px 15px rgba(246, 194, 62, 0.3);
          }
          
          .timeline-empty {
            text-align: center;
            padding: 2rem;
            color: #6c757d;
          }
        </style>
      `;
    }

    // Global timeline management functions
    window.editTimelineEvent = function(index) {
      editingIndex = index;
      renderTimeline();
      // Focus on textarea
      setTimeout(() => {
        const textarea = document.getElementById(`edit-${index}`);
        if (textarea) {
          textarea.focus();
          textarea.select();
        }
      }, 100);
    };

    window.saveTimelineEdit = function(index) {
      const textarea = document.getElementById(`edit-${index}`);
      if (textarea && textarea.value.trim()) {
        timelineEvents[index] = textarea.value.trim();
        editingIndex = -1;
        renderTimeline();
      }
    };

    window.cancelTimelineEdit = function() {
      editingIndex = -1;
      renderTimeline();
    };

    window.deleteTimelineEvent = function(index) {
      if (confirm('Are you sure you want to delete this timeline event?')) {
        timelineEvents.splice(index, 1);
        editingIndex = -1;
        renderTimeline();
      }
    };

    window.addTimelineEvent = function(index) {
      const newEvent = prompt('Enter new timeline event:');
      if (newEvent && newEvent.trim()) {
        timelineEvents.splice(index, 0, newEvent.trim());
        renderTimeline();
      }
    };

    window.saveAllTimelineChanges = async function() {
      try {
        const timelineString = JSON.stringify(timelineEvents);
        const response = await fetch(`/patient/${patientId}/timeline`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ timeline: timelineString })
        });

        const result = await response.json();
        if (response.ok) {
          alert('Timeline updated successfully!');
        } else {
          alert(result.error || 'Failed to update timeline.');
        }
      } catch (error) {
        alert('Error updating timeline: ' + error.message);
      }
    };

    window.cancelAllTimelineChanges = function() {
      if (confirm('Are you sure you want to cancel all changes? This will reload the page.')) {
        location.reload();
      }
    };

    // Initial render
    renderTimeline();

    // Keywords - make it editable
    const keywordsContainer = document.getElementById('keywordsInput').parentElement;
    keywordsContainer.innerHTML = `
      <div class="keywords-header d-flex justify-content-between align-items-center mb-3">
        <h4>Update Keywords</h4>
        <button class="btn btn-sm btn-outline-primary" id="editKeywordsBtn">
          <i class="bi bi-pencil"></i> Edit Keywords
        </button>
      </div>
      <div id="keywordsDisplay" class="keywords-display p-3 border rounded">
        ${data.keywords && data.keywords !== "No main keywords found." ? data.keywords : 'No keywords available.'}
      </div>
      <div id="keywordsEdit" class="keywords-edit" style="display: none;">
        <textarea class="form-control mb-2" id="keywordsTextarea" rows="4" placeholder="Enter keywords...">${data.keywords && data.keywords !== "No main keywords found." ? data.keywords : ''}</textarea>
        <div class="keywords-actions">
          <button class="btn btn-sm btn-success" id="saveKeywordsBtn">
            <i class="bi bi-save"></i> Save Keywords
          </button>
          <button class="btn btn-sm btn-secondary" id="cancelKeywordsBtn">
            <i class="bi bi-x-circle"></i> Cancel
          </button>
        </div>
      </div>
    `;

    // Keywords editing functionality
    document.getElementById('editKeywordsBtn').addEventListener('click', () => {
      document.getElementById('keywordsDisplay').style.display = 'none';
      document.getElementById('keywordsEdit').style.display = 'block';
      document.getElementById('editKeywordsBtn').style.display = 'none';
      document.getElementById('keywordsTextarea').focus();
    });

    document.getElementById('cancelKeywordsBtn').addEventListener('click', () => {
      document.getElementById('keywordsDisplay').style.display = 'block';
      document.getElementById('keywordsEdit').style.display = 'none';
      document.getElementById('editKeywordsBtn').style.display = 'block';
      const originalKeywords = data.keywords && data.keywords !== "No main keywords found." ? data.keywords : '';
      document.getElementById('keywordsTextarea').value = originalKeywords;
    });

    document.getElementById('saveKeywordsBtn').addEventListener('click', async () => {
      const newKeywords = document.getElementById('keywordsTextarea').value;
      console.log('Updating keywords:', newKeywords);
      console.log('Patient ID:', patientId);
      
      try {
        const response = await fetch(`/patient/${patientId}/keywords`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ keywords: newKeywords })
        });

        console.log('Response status:', response.status);
        const result = await response.json();
        console.log('Response result:', result);
        
        if (response.ok) {
          document.getElementById('keywordsDisplay').textContent = newKeywords || 'No keywords available.';
          document.getElementById('keywordsDisplay').style.display = 'block';
          document.getElementById('keywordsEdit').style.display = 'none';
          document.getElementById('editKeywordsBtn').style.display = 'block';
          alert('Keywords updated successfully!');
        } else {
          console.error('Update failed:', result);
          alert(result.error || 'Failed to update keywords.');
        }
      } catch (error) {
        console.error('Error updating keywords:', error);
        alert('Error updating keywords: ' + error.message);
      }
    });

  } catch (error) {
    console.error('Error fetching patient data:', error);
    alert('Failed to load patient data: ' + error.message);
  }
}

// Fetch data on load
fetchPatientData();