from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory, jsonify
from werkzeug.utils import secure_filename
import os
from google.cloud import speech, texttospeech, language_v1
import logging

app = Flask(__name__)

# Configure upload folders
UPLOAD_FOLDER = 'uploads'
TTS_FOLDER = 'tts'
ALLOWED_EXTENSIONS = {'wav', 'txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['TTS_FOLDER'] = TTS_FOLDER

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TTS_FOLDER, exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Google Cloud Clients
try:
    speech_client = speech.SpeechClient()
    tts_client = texttospeech.TextToSpeechClient()
    language_client = language_v1.LanguageServiceClient()
    logger.info("Google Cloud clients initialized successfully")
except Exception as e:
    logger.error(f"Error initializing Google Cloud clients: {e}")
    # We'll handle this gracefully in the routes

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_files():
    files = []
    try:
        for filename in os.listdir(UPLOAD_FOLDER):
            files.append(filename)
        files.sort(reverse=True)
    except Exception as e:
        logger.error(f"Error listing files: {e}")
    return files

def get_tts_files():
    files = []
    try:
        for filename in os.listdir(TTS_FOLDER):
            files.append(filename)
        files.sort(reverse=True)
    except Exception as e:
        logger.error(f"Error listing TTS files: {e}")
    return files

def get_sentiment_data(files, folder):
    """Read sentiment data from files in the specified folder"""
    sentiments = {}
    
    for file in files:
        if file.endswith('-sentiment.txt'):
            try:
                file_path = os.path.join(folder, file)
                with open(file_path, 'r') as f:
                    classification = f.readline().strip()
                    sentiments[file] = classification
            except Exception as e:
                logger.error(f"Error reading sentiment file {file}: {e}")
                
    return sentiments

def analyze_sentiment(text):
    """
    Analyze sentiment of the given text using Google Cloud Language API
    Returns sentiment score, magnitude, and classification
    """
    try:
        document = language_v1.Document(
            content=text, 
            type_=language_v1.Document.Type.PLAIN_TEXT
        )
        sentiment = language_client.analyze_sentiment(request={'document': document}).document_sentiment
        
        # Determine sentiment classification based on score
        if sentiment.score > 0.25:
            classification = "Positive"
        elif sentiment.score < -0.25:
            classification = "Negative"
        else:
            classification = "Neutral"
            
        return {
            "score": sentiment.score,
            "magnitude": sentiment.magnitude,
            "classification": classification
        }
    except Exception as e:
        logger.error(f"Error analyzing sentiment: {e}")
        return {
            "score": 0,
            "magnitude": 0,
            "classification": "Error"
        }

@app.route('/')
def index():
    files = get_files()
    tts_files = get_tts_files()
    
    # Get sentiment data for both types of files
    file_sentiments = get_sentiment_data(files, UPLOAD_FOLDER)
    tts_sentiments = get_sentiment_data(tts_files, TTS_FOLDER)
    
    return render_template('index.html', 
                          files=files, 
                          tts_files=tts_files,
                          file_sentiments=file_sentiments,
                          tts_sentiments=tts_sentiments)

@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        logger.warning("No audio_data in request")
        return redirect(url_for('index'))
    
    file = request.files['audio_data']
    
    if file.filename == '':
        logger.warning("Empty filename")
        return redirect(url_for('index'))
    
    if file and allowed_file(file.filename):
        # Generate a timestamp-based filename
        filename = datetime.now().strftime("%Y%m%d-%H%M%S") + '.wav'
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        try:
            file.save(filepath)
            logger.info(f"Audio file saved as {filename}")
            
            # Convert speech to text
            try:
                with open(filepath, 'rb') as audio_file:
                    content = audio_file.read()
                
                audio = speech.RecognitionAudio(content=content)
                config = speech.RecognitionConfig(
                    language_code="en-US",
                    enable_word_time_offsets=True
                )
                
                response = speech_client.recognize(config=config, audio=audio)
                transcript = "\n".join([result.alternatives[0].transcript for result in response.results])
                
                # Analyze sentiment
                sentiment_result = analyze_sentiment(transcript)
                
                # Save transcript with sentiment analysis
                text_filename = filename.replace('.wav', '.txt')
                text_filepath = os.path.join(app.config['UPLOAD_FOLDER'], text_filename)
                
                with open(text_filepath, 'w') as text_file:
                    text_file.write(f"Transcript:\n{transcript}\n\n")
                    text_file.write(f"Sentiment Analysis:\n")
                    text_file.write(f"Classification: {sentiment_result['classification']}\n")
                    text_file.write(f"Score: {sentiment_result['score']}\n")
                    text_file.write(f"Magnitude: {sentiment_result['magnitude']}\n")
                
                # Save sentiment analysis separately for easy processing
                sentiment_filename = filename.replace('.wav', '-sentiment.txt')
                sentiment_filepath = os.path.join(app.config['UPLOAD_FOLDER'], sentiment_filename)
                
                with open(sentiment_filepath, 'w') as sentiment_file:
                    sentiment_file.write(f"{sentiment_result['classification']}\n")
                    sentiment_file.write(f"{sentiment_result['score']}\n")
                    sentiment_file.write(f"{sentiment_result['magnitude']}\n")
                
                logger.info(f"Transcription and sentiment analysis saved as {text_filename}")
            except Exception as e:
                logger.error(f"Error in speech-to-text processing: {e}")
                # Continue even if transcription fails
        
        except Exception as e:
            logger.error(f"Error saving audio file: {e}")
    
    return redirect(url_for('index'))

@app.route('/upload_text', methods=['POST'])
def upload_text():
    text = request.form.get('text', '')
    
    if not text:
        logger.warning("Empty text submitted")
        return redirect(url_for('index'))
    
    try:
        # Analyze sentiment
        sentiment_result = analyze_sentiment(text)
        
        # Convert text to speech
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16
        )
        
        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        # Generate a timestamp-based filename
        filename = "tts-" + datetime.now().strftime("%Y%m%d-%H%M%S") + '.wav'
        filepath = os.path.join(app.config['TTS_FOLDER'], filename)
        
        with open(filepath, 'wb') as out:
            out.write(response.audio_content)
        
        logger.info(f"TTS audio saved as {filename}")
        
        # Save the input text and sentiment analysis
        text_filename = filename.replace('.wav', '.txt')
        text_filepath = os.path.join(app.config['TTS_FOLDER'], text_filename)
        
        with open(text_filepath, 'w') as text_file:
            text_file.write(f"Text:\n{text}\n\n")
            text_file.write(f"Sentiment Analysis:\n")
            text_file.write(f"Classification: {sentiment_result['classification']}\n")
            text_file.write(f"Score: {sentiment_result['score']}\n")
            text_file.write(f"Magnitude: {sentiment_result['magnitude']}\n")
        
        # Save sentiment analysis separately
        sentiment_filename = filename.replace('.wav', '-sentiment.txt')
        sentiment_filepath = os.path.join(app.config['TTS_FOLDER'], sentiment_filename)
        
        with open(sentiment_filepath, 'w') as sentiment_file:
            sentiment_file.write(f"{sentiment_result['classification']}\n")
            sentiment_file.write(f"{sentiment_result['score']}\n")
            sentiment_file.write(f"{sentiment_result['magnitude']}\n")
        
        logger.info(f"TTS text and sentiment saved as {text_filename}")
        
        return redirect(url_for('index'))
        
    except Exception as e:
        logger.error(f"Error in text-to-speech processing: {e}")
        return redirect(url_for('index'))

@app.route('/latest_tts')
def latest_tts():
    """Get the most recent TTS file"""
    tts_files = get_tts_files()
    wav_files = [f for f in tts_files if f.endswith('.wav')]
    
    if wav_files:
        latest_file = wav_files[0]  # Files are sorted by date, newest first
        return jsonify({
            'found': True,
            'audioFile': latest_file,
            'url': url_for('generated_audio', filename=latest_file)
        })
    
    return jsonify({'found': False})

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/tts/<filename>')
def generated_audio(filename):
    return send_from_directory(app.config['TTS_FOLDER'], filename)

@app.route('/script.js', methods=['GET'])
def scripts_js():
    return send_file('./script.js')

@app.errorhandler(500)
def server_error(e):
    logger.error(f"Server error: {e}")
    return "Internal Server Error", 500

if __name__ == '__main__':
    app.run(debug=True)