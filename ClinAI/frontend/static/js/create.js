let mediaRecorder;
let audioChunks = [];
let isPaused = false;
let liveTranscript = "";

const startBtn = document.getElementById('startRecording');
const stopBtn = document.getElementById('stopRecording');
const finalStopBtn = document.getElementById('finalStopBtn');
const notesInput = document.getElementById('notesInput');
const conversationText = document.getElementById('conversationText');
const editedNotes = document.getElementById('editedNotes');
const transcriptionOutput = document.getElementById('transcriptionOutput');
const modal = new bootstrap.Modal(document.getElementById('labeledModal'));

startBtn?.addEventListener('click', async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];
    liveTranscript = "";
    transcriptionOutput.innerText = "Waiting for transcription...";

    mediaRecorder.ondataavailable = async (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data);

        const audioBlob = new Blob([event.data], { type: 'audio/webm' });
        const formData = new FormData();
        formData.append('file', audioBlob, 'chunk.webm');

        try {
          const response = await fetch('/transcribe', {
            method: 'POST',
            body: formData
          });

          const { transcription } = await response.json();
          if (transcription) {
            liveTranscript += transcription + " ";
            transcriptionOutput.innerText = liveTranscript.trim();
          }
        } catch (err) {
          console.error("[ClinAI] ❌ Transcription error:", err);
        }
      }
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
        body: JSON.stringify({ conversation: transcription, previous: conversationText.value })
      });

      const labeled = await labelRes.json();
      conversationText.value = labeled.labeled_conversation || transcription;
      editedNotes.value = notesInput.value;
      modal.show();
    };

    mediaRecorder.start(2000);
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
    transcriptionOutput.innerText = "";
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
