const recordButton = document.getElementById('record');
const stopButton = document.getElementById('stop');
const audioElement = document.getElementById('audio');
const timerDisplay = document.getElementById('timer');
const ttsForm = document.getElementById('tts-form');
const ttsAudio = document.getElementById('tts-audio');
const ttsText = document.getElementById('tts-text');

let mediaRecorder;
let audioChunks = [];
let startTime;
let timerInterval;

// Debug logging function
function logDebug(message) {
  console.log(`[DEBUG] ${message}`);
}

logDebug('Script initialized');

function formatTime(time) {
  const minutes = Math.floor(time / 60).toString().padStart(2, '0');
  const seconds = Math.floor(time % 60).toString().padStart(2, '0');
  return `${minutes}:${seconds}`;
}

// Recording functionality
if (recordButton) {
  logDebug('Record button found');
  
  recordButton.addEventListener('click', () => {
    logDebug('Record button clicked');
    
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(stream => {
        logDebug('Microphone access granted');
        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.start();
        
        audioChunks = [];
        startTime = Date.now();
        timerInterval = setInterval(() => {
          const elapsedTime = Math.floor((Date.now() - startTime) / 1000);
          timerDisplay.textContent = formatTime(elapsedTime);
        }, 1000);
        
        mediaRecorder.addEventListener('dataavailable', e => {
          logDebug('Audio data available');
          audioChunks.push(e.data);
        });
        
        mediaRecorder.addEventListener('stop', () => {
          logDebug('Recording stopped');
          clearInterval(timerInterval);
          
          const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
          const audioUrl = URL.createObjectURL(audioBlob);
          audioElement.src = audioUrl;
          
          logDebug('Creating form data for upload');
          // Create FormData and send to server
          const formData = new FormData();
          formData.append('audio_data', audioBlob, 'recorded_audio.wav');
          
          logDebug('Sending audio to server');
          fetch('/upload', {
            method: 'POST',
            body: formData
          })
          .then(response => {
            if (!response.ok) {
              throw new Error('Network response was not ok');
            }
            logDebug('Server response received');
            return response.text();
          })
          .then(data => {
            logDebug('Audio uploaded successfully');
            setTimeout(() => {
              location.reload(); // Refresh page to show new recording
            }, 1000);
          })
          .catch(error => {
            console.error('Error uploading audio:', error);
            alert('Error uploading audio. Please try again.');
          });
          
          // Stop all tracks in the stream
          mediaRecorder.stream.getTracks().forEach(track => track.stop());
        });
      })
      .catch(error => {
        console.error('Error accessing microphone:', error);
        alert('Could not access microphone. Please check permissions and ensure you are using HTTPS in a supported browser.');
        logDebug(`Microphone access error: ${error.name}: ${error.message}`);
      });
    
    recordButton.disabled = true;
    stopButton.disabled = false;
  });
} else {
  console.error('Record button not found in the DOM');
}

if (stopButton) {
  logDebug('Stop button found');
  
  stopButton.addEventListener('click', () => {
    logDebug('Stop button clicked');
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
    
    recordButton.disabled = false;
    stopButton.disabled = true;
  });
} else {
  console.error('Stop button not found in the DOM');
}

// Text-to-Speech functionality - FIXED VERSION
if (ttsForm) {
  logDebug('TTS form found');
  
  ttsForm.addEventListener('submit', function(e) {
    e.preventDefault(); // Prevent the default form submission
    logDebug('TTS form submitted');
    
    const submitButton = this.querySelector('button[type="submit"]');
    const text = ttsText.value.trim();
    
    if (!text) {
      alert('Please enter some text to convert to speech');
      return;
    }
    
    if (submitButton) {
      submitButton.textContent = 'Processing...';
      submitButton.disabled = true;
      
      // Create form data
      const formData = new FormData();
      formData.append('text', text);
      
      logDebug('Sending text to server for TTS processing');
      // Send AJAX request instead of form submission
      fetch('/upload_text', {
        method: 'POST',
        body: formData
      })
      .then(response => {
        logDebug(`TTS server response status: ${response.status}`);
        if (!response.ok) {
          throw new Error(`Network response was not ok: ${response.status}`);
        }
        return response.text(); // Changed from .json() to .text()
      })
      .then(data => {
        logDebug('TTS generated successfully');
        
        // Refresh the page to show the new file in the list
        setTimeout(() => {
          location.reload();
        }, 1000);
      })
      .catch(error => {
        console.error('Error generating TTS:', error);
        alert('Error generating speech. Please check the server logs.');
        logDebug(`TTS error: ${error.message}`);
      })
      .finally(() => {
        submitButton.textContent = 'Generate Audio';
        submitButton.disabled = false;
      });
    }
  });
} else {
  console.error('TTS form not found in the DOM');
}

// Function to load most recent TTS audio
function loadRecentTTS() {
  if (!ttsAudio) {
    logDebug('ttsAudio element not found');
    return;
  }
  
  logDebug('Attempting to load recent TTS audio');
  fetch('/latest_tts')
    .then(response => response.json())
    .then(data => {
      if (data.found && data.url) {
        ttsAudio.src = data.url;
        logDebug('Loaded most recent TTS audio:', data.audioFile);
      } else {
        logDebug('No recent TTS audio found');
      }
    })
    .catch(error => {
      console.error('Error loading recent TTS:', error);
      logDebug(`Error loading recent TTS: ${error.message}`);
    });
}

// Initialize with disabled stop button
if (stopButton) {
  stopButton.disabled = true;
}

// Load recent TTS audio when page loads
document.addEventListener('DOMContentLoaded', () => {
  logDebug('DOM content loaded');
  loadRecentTTS();
});

// Check browser media capabilities
logDebug(`UserMedia supported: ${navigator.mediaDevices && !!navigator.mediaDevices.getUserMedia}`);
if (navigator.mediaDevices && navigator.mediaDevices.getSupportedConstraints) {
  logDebug('Supported constraints:', JSON.stringify(navigator.mediaDevices.getSupportedConstraints()));
}

// Check if we're on HTTPS
logDebug(`Page protocol: ${window.location.protocol}`);
if (window.location.protocol !== 'https:' && window.location.hostname !== 'localhost') {
  console.warn('Media recording may require HTTPS in many browsers. Current protocol:', window.location.protocol);
}

// Log that the script has loaded correctly
logDebug('Voice recorder and TTS script loaded successfully');