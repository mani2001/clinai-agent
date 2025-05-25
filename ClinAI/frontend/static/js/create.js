let mediaRecorder;
let audioChunks = [];
let isPaused = false;

const startBtn = document.getElementById('startRecording');
const stopBtn = document.getElementById('stopRecording');
const finalStopBtn = document.getElementById('finalStopBtn');
const notesInput = document.getElementById('notesInput');
const conversationText = document.getElementById('conversationText');
const editedNotes = document.getElementById('editedNotes');
const modal = new bootstrap.Modal(document.getElementById('labeledModal'));
const patientIdInput = document.getElementById('patientIdInput');
const modalPatientId = document.getElementById('modalPatientId');

function generateRandomId() {
  return Math.floor(Math.random() * 1e6).toString().padStart(6, '0');
}

window.addEventListener('DOMContentLoaded', () => {
  if (patientIdInput) {
    patientIdInput.value = generateRandomId();
  }
});

startBtn?.addEventListener('click', async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.ondataavailable = event => {
      if (event.data.size > 0) audioChunks.push(event.data);
    };

    mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
      const formData = new FormData();
      formData.append('file', audioBlob, 'recording.webm');

      const transcriptionRes = await fetch('/transcribe', {
        method: 'POST',
        body: formData
      });

      const { transcription } = await transcriptionRes.json();
      if (!transcription) return alert('Transcription failed.');

      const labelRes = await fetch('/label_conversation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation: transcription
        })
      });

      const labeled = await labelRes.json();
      conversationText.value = labeled.labeled_conversation || transcription;
      editedNotes.value = notesInput.value;
      modalPatientId.value = patientIdInput.value;
      modal.show();
    };

    mediaRecorder.start();
    isPaused = false;
    stopBtn.innerText = 'Pause Recording';
    startBtn.disabled = true;
    stopBtn.disabled = false;
    finalStopBtn.disabled = false;

    const indicator = document.getElementById('recordingIndicator');
    indicator.style.display = 'block';
    indicator.style.opacity = '1';
    const bars = indicator.querySelectorAll('.bar');
    bars.forEach(bar => bar.style.animationPlayState = 'running');

    document.getElementById('transcriptionContainer').style.display = 'block';
    console.log("[ClinAI] 🎬 Recording started");
  } catch (err) {
    alert('Microphone access denied or unavailable.');
    console.error("[ClinAI] ❌", err);
  }
});

stopBtn?.addEventListener('click', () => {
  const indicator = document.getElementById('recordingIndicator');
  if (mediaRecorder) {
    if (!isPaused && mediaRecorder.state === 'recording') {
      mediaRecorder.pause();
      stopBtn.innerText = 'Resume Recording';
      isPaused = true;
      indicator.style.opacity = '0.5';
      const bars = indicator.querySelectorAll('.bar');
      bars.forEach(bar => bar.style.animationPlayState = 'paused');
      console.log("[ClinAI] ⏸ Recording paused");
    } else if (isPaused && mediaRecorder.state === 'paused') {
      mediaRecorder.resume();
      stopBtn.innerText = 'Pause Recording';
      isPaused = false;
      indicator.style.opacity = '1';
      const bars = indicator.querySelectorAll('.bar');
      bars.forEach(bar => bar.style.animationPlayState = 'running');
      console.log("[ClinAI] ▶️ Recording resumed");
    }
  }
});

finalStopBtn?.addEventListener('click', () => {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
    document.getElementById('recordingIndicator').style.display = 'none';
    console.log("[ClinAI] 🛑 Recording stopped");
  }
  startBtn.disabled = false;
  stopBtn.disabled = true;
  finalStopBtn.disabled = true;
  stopBtn.innerText = 'Pause Recording';
  isPaused = false;
});

document.getElementById('continueRecording')?.addEventListener('click', () => {
  modal.hide();
});

document.getElementById('saveRecord')?.addEventListener('click', async () => {
  const payload = {
    idx: modalPatientId.value,
    conversation: conversationText.value,
    notes: editedNotes.value
  };

  const response = await fetch('/save_record', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (response.ok) {
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'patient_record.txt';
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
    modal.hide();
  } else {
    alert('Failed to save record.');
  }
});

document.getElementById('manualCreateBtn')?.addEventListener('click', async () => {
  const confirmed = confirm('Are you sure you want to create and pause the recording if active?');
  if (!confirmed) return;

  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop(); // will trigger onstop
  } else {
    const conversation = conversationText.value.trim();

    if (!conversation) {
      alert('No conversation found to label. Please record or write something first.');
      return;
    }

    editedNotes.value = notesInput.value;
    modalPatientId.value = patientIdInput.value;
    modal.show();
  }
});
