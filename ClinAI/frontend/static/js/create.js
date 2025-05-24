let mediaRecorder;
let audioChunks = [];
let isPaused = false;
let fullTranscript = "";

const startBtn = document.getElementById('startRecording');
const stopBtn = document.getElementById('stopRecording');
const finalStopBtn = document.getElementById('finalStopBtn');
const notesInput = document.getElementById('notesInput');
const conversationText = document.getElementById('conversationText');
const editedNotes = document.getElementById('editedNotes');
const modal = new bootstrap.Modal(document.getElementById('labeledModal'));
const transcriptionOutput = document.getElementById('transcriptionOutput');

startBtn?.addEventListener('click', async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.ondataavailable = event => {
      if (event.data.size > 0) audioChunks.push(event.data);
    };

    mediaRecorder.onstop = async () => {
      if (audioChunks.length === 0) {
        alert("No audio recorded.");
        return;
      }
      const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
      const formData = new FormData();
      formData.append('file', audioBlob, 'recording.webm');

      const transcriptionRes = await fetch('/transcribe', {
        method: 'POST',
        body: formData
      });

      const { transcription } = await transcriptionRes.json();
      if (!transcription) return alert('Transcription failed.');

      fullTranscript += (fullTranscript ? "\n" : "") + transcription;

      const labelRes = await fetch('/label_conversation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversation: fullTranscript })
      });

      const labeled = await labelRes.json();
      conversationText.value = labeled.labeled_conversation || fullTranscript;
      editedNotes.value = notesInput.value;
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

    transcriptionOutput.innerText = "Pause recording to see transcript";
    document.getElementById('transcriptionContainer').style.display = 'block';
    console.log("[ClinAI] 🎬 Recording started");
  } catch (err) {
    alert('Microphone access denied or unavailable.');
    console.error("[ClinAI] ❌", err);
  }
});

stopBtn?.addEventListener('click', async () => {
  const indicator = document.getElementById('recordingIndicator');
  if (mediaRecorder) {
    mediaRecorder.requestData();

    if (!isPaused && mediaRecorder.state === 'recording') {
      mediaRecorder.pause();
      stopBtn.innerText = 'Resume Recording';
      isPaused = true;
      indicator.style.opacity = '0.5';
      const bars = indicator.querySelectorAll('.bar');
      bars.forEach(bar => bar.style.animationPlayState = 'paused');
      console.log("[ClinAI] ⏸ Recording paused");

      // Show live transcription
      const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
      const formData = new FormData();
      formData.append('file', audioBlob, 'recording.webm');

      const transcriptionRes = await fetch('/transcribe', {
        method: 'POST',
        body: formData
      });
      const { transcription } = await transcriptionRes.json();

      if (transcription) {
        transcriptionOutput.innerText = transcription;
        fullTranscript += (fullTranscript ? "\n" : "") + transcription;
      }

    } else if (isPaused && mediaRecorder.state === 'paused') {
      mediaRecorder.resume();
      stopBtn.innerText = 'Pause Recording';
      isPaused = false;
      indicator.style.opacity = '1';
      const bars = indicator.querySelectorAll('.bar');
      bars.forEach(bar => bar.style.animationPlayState = 'running');
      console.log("[ClinAI] ▶️ Recording resumed");
    } else {
      console.warn("[ClinAI] 🚫 MediaRecorder not in a recordable state");
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
