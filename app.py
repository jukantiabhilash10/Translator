from flask import Flask, render_template, request, jsonify, send_file, make_response
import os
from deep_translator import GoogleTranslator
from gtts import gTTS
from PyPDF2 import PdfReader
import speech_recognition as sr
from pymongo import MongoClient
from datetime import datetime
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import traceback
import hashlib
import time
from io import BytesIO
from indic_transliteration.sanscript import transliterate, SCHEMES

app = Flask(__name__)

@app.after_request
def add_header(response):
    """
    Add headers to both force latest content and prevent caching.
    """
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# MongoDB setup

MONGO_URI = "mongodb+srv://Abhireddy:R#nTj!y$DJwf_B9@abhireddy.eatvcov.mongodb.net/?retryWrites=true&w=majority&appName=Abhireddy"
client = MongoClient(MONGO_URI)
db = client['translator_db']
history_collection = db['translation_history']

# Font configuration for PDF
class CustomPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.font_cache = {}

    def add_unicode_font(self, font_name, font_path):
        try:
            # Check file extension
            _, ext = os.path.splitext(font_path)
            if ext.lower() not in ['.ttf', '.otf']:
                print(f"[DEBUG] Unsupported font format for {font_name}: {ext}")
                self.font_cache[font_name] = False
                return

            # Try adding font without style parameter first
            try:
                self.add_font(font_name, fname=font_path)
            except Exception:
                # If that fails, try with empty string style
                self.add_font(font_name, '', font_path)
            
            print(f"[DEBUG] Successfully loaded font: {font_name}")
            self.font_cache[font_name] = True
        except Exception as e:
            print(f"[DEBUG] Failed to add font {font_name}: {str(e)}")
            self.font_cache[font_name] = False

    def setup_fonts(self, app_root):
        font_folder = os.path.join(app_root, 'static', 'fonts')
        font_files = {
            'DejaVu': 'DejaVuSans.ttf',
            'NotoSans': 'NotoSans-Regular.ttf',
            'NotoTelugu': 'NotoSansTelugu-Regular.ttf',
            'NotoGujarati': 'NotoSansGujarati-Regular.ttf',
            'NotoDevanagari': 'NotoSansDevanagari-Regular.ttf',
            'NotoBengali': 'NotoSansBengali-Regular.ttf',
            'NotoTamil': 'NotoSansTamil-Regular.ttf',
            'NotoMalayalam': 'NotoSansMalayalam-Regular.ttf',
            'NotoKannada': 'NotoSansKannada-Regular.ttf',
            'NotoPunjabi': 'NotoSansGurmukhi-Regular.ttf',
            'NotoUrdu': 'NotoSansArabic-Regular.ttf',
            'NotoArabic': 'NotoSansArabic-Regular.ttf',
            'NotoChinese': 'NotoSansSC-Regular.otf',
            'NotoJapanese': 'NotoSansJP-Regular.ttf',
            'NotoKorean': 'NotoSansKR-Regular.ttf',
            'NotoHebrew': 'NotoSansHebrew-Regular.ttf',
            'NotoGreek': 'NotoSansGreek-Regular.ttf',
            'NotoRussian': 'NotoSans-Regular.ttf',
            'NotoSansTC': 'NotoSansTC-Regular.ttf',  # Traditional Chinese
            'NotoSansThai': 'NotoSansThai-Regular.ttf', # Thai
        }
        for font_name, font_file in font_files.items():
            font_path = os.path.join(font_folder, font_file)
            if os.path.exists(font_path):
                self.add_unicode_font(font_name, font_path)
            else:
                print(f"[DEBUG] Font missing: {font_path}")
                # Download logic can be added here if needed

    def download_indic_font(self, font_name, font_path):
        # Using Google Fonts CDN for reliable downloads
        font_urls = {
            'NotoTelugu': 'https://fonts.google.com/download?family=Noto+Sans+Telugu',
            'NotoGujarati': 'https://fonts.google.com/download?family=Noto+Sans+Gujarati',
            'NotoDevanagari': 'https://fonts.google.com/download?family=Noto+Sans+Devanagari'
        }
        
        try:
            import requests
            import zipfile
            import io
            
            os.makedirs(os.path.dirname(font_path), exist_ok=True)
            print(f"[DEBUG] Downloading font {font_name} from {font_urls[font_name]}")
            
            response = requests.get(font_urls[font_name])
            response.raise_for_status()
            
            # Extract the regular font file from the zip
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                # Find the regular weight TTF file
                font_file = next(f for f in zip_ref.namelist() if f.endswith('-Regular.ttf'))
                with zip_ref.open(font_file) as font_data:
                    with open(font_path, 'wb') as f:
                        f.write(font_data.read())
            
            self.add_unicode_font(font_name, font_path)
        except Exception as e:
            print(f"[DEBUG] Failed to download {font_name}: {str(e)}")

    def download_cjk_font(self, font_name, font_path):
        # Using Google Fonts CDN for reliable downloads
        font_urls = {
            'NotoChinese': 'https://fonts.google.com/download?family=Noto+Sans+SC',
            'NotoJapanese': 'https://fonts.google.com/download?family=Noto+Sans+JP',
            'NotoKorean': 'https://fonts.google.com/download?family=Noto+Sans+KR'
        }
        
        try:
            import requests
            import zipfile
            import io
            
            os.makedirs(os.path.dirname(font_path), exist_ok=True)
            print(f"[DEBUG] Downloading font {font_name} from {font_urls[font_name]}")
            
            response = requests.get(font_urls[font_name])
            response.raise_for_status()
            
            # Extract the regular font file from the zip
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                # Find the regular weight TTF file
                font_file = next(f for f in zip_ref.namelist() if f.endswith('Regular.otf') or f.endswith('Regular.ttf'))
                with zip_ref.open(font_file) as font_data:
                    with open(font_path, 'wb') as f:
                        f.write(font_data.read())
            
            print(f"[DEBUG] Successfully downloaded font: {font_name}")
            self.add_unicode_font(font_name, font_path)
        except Exception as e:
            print(f"[DEBUG] Failed to download {font_name}: {str(e)}")

    def cell(self, w=0, h=0, txt='', border=0, ln=0, align='', fill=False, link=''):
        from fpdf.enums import XPos, YPos
        # Handle deprecated parameters
        text = txt  # txt renamed to text
        if ln == 0:
            new_x, new_y = XPos.RIGHT, YPos.TOP
        else:
            new_x, new_y = XPos.LMARGIN, YPos.NEXT
        
        try:
            super().cell(w=w, h=h, text=text, border=border, 
                        new_x=new_x, new_y=new_y, 
                        align=align, fill=fill, link=link)
        except UnicodeEncodeError:
            current_font = self.font_family
            if current_font != 'NotoSans' and self.font_cache.get('NotoSans', False):
                self.set_font('NotoSans')
                super().cell(w=w, h=h, text=text, border=border,
                           new_x=new_x, new_y=new_y,
                           align=align, fill=fill, link=link)
                self.set_font(current_font)
            else:
                self.set_font('DejaVu')
                super().cell(w=w, h=h, text=text, border=border,
                           new_x=new_x, new_y=new_y,
                           align=align, fill=fill, link=link)
                self.set_font(current_font)

    def multi_cell(self, w=0, h=0, txt='', border=0, align='', fill=False, split_only=False):
        # Handle deprecated txt parameter
        text = txt
        try:
            super().multi_cell(w=w, h=h, text=text, border=border,
                             align=align, fill=fill, split_only=split_only)
        except UnicodeEncodeError:
            current_font = self.font_family
            if current_font != 'NotoSans' and self.font_cache.get('NotoSans', False):
                self.set_font('NotoSans')
                super().multi_cell(w=w, h=h, text=text, border=border,
                                 align=align, fill=fill, split_only=split_only)
                self.set_font(current_font)
            else:
                self.set_font('DejaVu')
                super().multi_cell(w=w, h=h, text=text, border=border,
                                 align=align, fill=fill, split_only=split_only)
                self.set_font(current_font)

    def set_language_font(self, language_code, size=12):
        font_map = {
            'te': 'NotoTelugu', 'gu': 'NotoGujarati', 'hi': 'NotoDevanagari',
            'mr': 'NotoDevanagari', 'bn': 'NotoBengali', 'ta': 'NotoTamil',
            'ml': 'NotoMalayalam', 'kn': 'NotoKannada', 'pa': 'NotoPunjabi',
            'ur': 'NotoUrdu', 'ar': 'NotoArabic', 
            'zh-CN': 'NotoChinese', 'zh-TW': 'NotoSansTC', 'ja': 'NotoJapanese',
            'ko': 'NotoKorean', 'he': 'NotoHebrew', 'el': 'NotoGreek',
            'ru': 'NotoRussian', 'th': 'NotoSansThai',
        }
        font_name = font_map.get(language_code, 'NotoSans') 
        if self.font_cache.get(font_name, False):
            self.set_font(font_name, size=size)
        else:
            print(f"[DEBUG] Font {font_name} not available, falling back to DejaVu")
            self.set_font('DejaVu', size=size)

# Language configuration (alphabetized, with Auto-Detect)
language_pairs = [
    ("Afrikaans", "af"),
    ("Albanian", "sq"),
    ("Amharic", "am"),
    ("Arabic", "ar"),
    ("Armenian", "hy"),
    ("Azerbaijani", "az"),
    ("Bengali", "bn"),
    ("Bulgarian", "bg"),
    ("Catalan", "ca"),
    ("Chinese (simplified)", "zh-CN"),
    ("Chinese (traditional)", "zh-TW"),
    ("Croatian", "hr"),
    ("Czech", "cs"),
    ("Danish", "da"),
    ("Dutch", "nl"),
    ("English", "en"),
    ("Estonian", "et"),
    ("Filipino", "tl"),
    ("Finnish", "fi"),
    ("French", "fr"),
    ("German", "de"),
    ("Greek", "el"),
    ("Gujarati", "gu"),
    ("Hebrew", "he"),
    ("Hindi", "hi"),
    ("Hungarian", "hu"),
    ("Indonesian", "id"),
    ("Italian", "it"),
    ("Japanese", "ja"),
    ("Kannada", "kn"),
    ("Korean", "ko"),
    ("Malay", "ms"),
    ("Malayalam", "ml"),
    ("Marathi", "mr"),
    ("Nepali", "ne"),
    ("Polish", "pl"),
    ("Portuguese", "pt"),
    ("Punjabi", "pa"),
    ("Romanian", "ro"),
    ("Russian", "ru"),
    ("Serbian", "sr"),
    ("Sinhala", "si"),
    ("Slovak", "sk"),
    ("Spanish", "es"),
    ("Swahili", "sw"),
    ("Swedish", "sv"),
    ("Tamil", "ta"),
    ("Telugu", "te"),
    ("Thai", "th"),
    ("Turkish", "tr"),
    ("Urdu", "ur"),
    ("Vietnamese", "vi"),
    ("Xhosa", "xh"),
    ("Zulu", "zu"),
]
# Sort alphabetically by language name
language_pairs.sort(key=lambda x: x[0])
languages = ["Auto-Detect"] + [name for name, code in language_pairs]
language_codes = ["auto"] + [code for name, code in language_pairs]

# Add this mapping after language_pairs and before routes
language_name_to_code = {name: code for name, code in language_pairs}

gtts_lang_map = {
    "Arabic": "ar",
    "Bengali": "bn",
    "Chinese": "zh-CN",
    "English": "en",
    "French": "fr",
    "German": "de",
    "Gujarati": "gu",
    "Hindi": "hi",
    "Italian": "it",
    "Japanese": "ja",
    "Kannada": "kn",
    "Korean": "ko",
    "Malayalam": "ml",
    "Marathi": "mr",
    "Portuguese": "pt",
    "Punjabi": "pa",
    "Russian": "ru",
    "Spanish": "es",
    "Tamil": "ta",
    "Telugu": "te",
    "Urdu": "ur",
    # Add more as needed
}

@app.route('/')
def index():
    # Fetch translation history from MongoDB, most recent first
    history_cursor = history_collection.find().sort('timestamp', -1)
    history = list(history_cursor)
    # Add a cache-busting timestamp
    cache_v = int(time.time())
    return render_template('index.html', languages=languages, history=history, cache_v=cache_v)

@app.route('/translate', methods=['POST'])
def translate():
    text = request.form['text']
    lang_from = request.form['lang_from']
    lang_to = request.form['lang_to']
    enable_transliteration = request.form.get('transliterate') == 'true'

    # Handle Auto-Detect
    if lang_from == "Auto-Detect":
        lang_from_code = "auto"
    else:
        lang_from_code = language_codes[languages.index(lang_from)]
    lang_to_code = language_codes[languages.index(lang_to)]
    print(f"[DEBUG] lang_from: {lang_from}, lang_from_code: {lang_from_code}")
    print(f"[DEBUG] lang_to: {lang_to}, lang_to_code: {lang_to_code}")
    print(f"[DEBUG] Transliteration enabled: {enable_transliteration}")

    try:
        text_to_translate = text
        if enable_transliteration:
            indic_script_map = {
                'te': 'telugu', 'hi': 'devanagari', 'gu': 'gujarati', 'bn': 'bengali',
                'ta': 'tamil', 'ml': 'malayalam', 'kn': 'kannada', 'pa': 'gurmukhi',
                'mr': 'devanagari', 'ne': 'devanagari', 'si': 'sinhala', 'ur': 'urdu'
            }
            
            target_script_lang = None
            # Prioritize explicitly selected source language
            if lang_from_code in indic_script_map:
                target_script_lang = lang_from_code
            # Handle Auto-Detect case by checking the target language
            elif lang_from_code == 'auto' and lang_to_code in indic_script_map:
                target_script_lang = lang_to_code

            if target_script_lang:
                try:
                    transliterated_text = transliterate(text, 'itrans', indic_script_map[target_script_lang])
                    # If transliteration produced a result, use it and update the source language
                    if transliterated_text and transliterated_text != text:
                        text_to_translate = transliterated_text
                        lang_from_code = target_script_lang
                        print(f"[DEBUG] Transliterated input to '{text_to_translate}' and set source lang to '{lang_from_code}'")
                except Exception as e:
                    print(f"[DEBUG] Transliteration failed: {e}")

        translated = GoogleTranslator(source=lang_from_code, target=lang_to_code).translate(text_to_translate)
        print(f"[DEBUG] Source text for translation: {text_to_translate}")
        print(f"[DEBUG] Source language for translation: {lang_from_code}")
        print(f"[DEBUG] Target language for translation: {lang_to_code}")
        print(f"[DEBUG] Translated text: {translated}")

        # Save translation to MongoDB with the correct language codes and names
        result = history_collection.insert_one({
            'source_text': text, # Always save the original user input
            'translated_text': translated,
            'source_lang': lang_from_code,
            'source_lang_name': lang_from,  # Save name for display
            'target_lang': lang_to_code,    # Save code
            'target_lang_name': lang_to,    # Save name for display
            'timestamp': datetime.utcnow().isoformat()
        })
        print(f"[DEBUG] Inserted translation history with id: {result.inserted_id}")

        return jsonify({'translated_text': translated})
    except Exception as e:
        return jsonify({'error': 'Translation failed', 'details': str(e)}), 500

@app.route('/transliterate', methods=['POST'])
def transliterate_text():
    try:
        text = request.form['text']
        lang_to = request.form['lang_to'] # The target language for transliteration
        
        lang_to_code = language_name_to_code.get(lang_to)
        if not lang_to_code:
            return jsonify({'error': 'Invalid target language for transliteration.'}), 400

        indic_script_map = {
            'te': 'telugu', 'hi': 'devanagari', 'gu': 'gujarati', 'bn': 'bengali',
            'ta': 'tamil', 'ml': 'malayalam', 'kn': 'kannada', 'pa': 'gurmukhi',
            'mr': 'devanagari', 'ne': 'devanagari', 'si': 'sinhala', 'ur': 'urdu'
        }

        target_script = indic_script_map.get(lang_to_code)
        if not target_script:
            return jsonify({'error': f'Transliteration not supported for {lang_to}.'}), 400

        # Using 'itrans' for Romanized input
        transliterated_text = transliterate(text, 'itrans', target_script)
        
        return jsonify({'transliterated_text': transliterated_text})

    except Exception as e:
        print(f"[DEBUG] Error in /transliterate: {str(e)}")
        return jsonify({'error': 'Transliteration failed', 'details': str(e)}), 500

@app.route('/download_history_pdf', methods=['GET'])
def download_history_pdf():
    try:
        pdf = CustomPDF()
        pdf.setup_fonts(app.root_path)
        pdf.add_page()

        # Set up title
        pdf.set_language_font('en', size=16)
        pdf.cell(w=0, h=10, txt="Translation History", align='C')
        pdf.ln(h=10)

        history_cursor = history_collection.find().sort('timestamp', -1)
        entries = list(history_cursor)

        if not entries:
            pdf.set_language_font('en', size=12)
            pdf.cell(w=0, h=10, txt="No translation history found.", align='C')
        else:
            for entry in entries:
                timestamp = datetime.fromisoformat(entry['timestamp']).strftime('%Y-%m-%d %H:%M:%S')

                # Header for each entry
                pdf.set_language_font('en', size=10)
                pdf.cell(w=0, h=6, txt=f"Date: {timestamp}")
                pdf.ln(h=6)
                # Use language name if available, else code
                lang_from_display = entry.get('source_lang_name', entry['source_lang'])
                lang_to_display = entry.get('target_lang_name', entry['target_lang'])
                pdf.cell(w=0, h=6, txt=f"Languages: {lang_from_display} -> {lang_to_display}")
                pdf.ln(h=6)

                # Source text
                pdf.set_language_font(entry['source_lang'], size=11)
                pdf.cell(w=0, h=6, txt="Source Text:")
                pdf.ln(h=6)
                pdf.multi_cell(w=0, h=6, txt=entry['source_text'])
                pdf.ln(h=4)

                # Translated text
                pdf.set_language_font(entry['target_lang'], size=11)
                pdf.cell(w=0, h=6, txt="Translated Text:")
                pdf.ln(h=6)
                pdf.multi_cell(w=0, h=6, txt=entry['translated_text'])
                pdf.ln(h=8)

                # Separator line
                pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
                pdf.ln(h=8)

        try:
            # Generate PDF directly without encoding
            pdf_bytes = bytes(pdf.output())
            if not pdf_bytes:
                raise ValueError("Generated PDF is empty")

            response = make_response(pdf_bytes)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = 'attachment; filename=translation_history.pdf'
            return response
        except Exception as e:
            print(f"[DEBUG] Error in PDF generation: {str(e)}")
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            return jsonify({'error': 'Failed to generate PDF', 'details': str(e)}), 500

    except Exception as e:
        print(f"[DEBUG] Critical error: {str(e)}")
        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Failed to generate PDF', 'details': str(e)}), 500

@app.route('/download_translated_pdf', methods=['POST'])
def download_translated_pdf():
    try:
        text = request.form.get('text', '')
        translated_text = request.form.get('translated_text', '')
        source_lang = request.form.get('source_lang', 'en')
        target_lang = request.form.get('target_lang', 'en')

        # Map language names to codes for font selection
        source_lang_code = language_name_to_code.get(source_lang, source_lang)
        target_lang_code = language_name_to_code.get(target_lang, target_lang)

        pdf = CustomPDF()
        pdf.setup_fonts(app.root_path)
        pdf.add_page()

        from datetime import datetime
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        pdf.set_language_font('en', size=10)
        pdf.cell(w=0, h=8, txt=f"Date: {now_str}")
        pdf.ln(h=8)
        pdf.cell(w=0, h=8, txt=f"Languages: {source_lang} -> {target_lang}")
        pdf.ln(h=8)

        pdf.set_language_font('en', size=16)
        pdf.cell(w=0, h=10, txt="Translated Text", align='C')
        pdf.ln(h=10)

        pdf.set_language_font(source_lang_code, size=12)
        pdf.cell(w=0, h=8, txt="Source Text:")
        pdf.ln(h=8)
        pdf.multi_cell(w=0, h=8, txt=text)
        pdf.ln(h=6)

        pdf.set_language_font(target_lang_code, size=12)
        pdf.cell(w=0, h=8, txt="Translated Text:")
        pdf.ln(h=8)
        pdf.multi_cell(w=0, h=8, txt=translated_text)

        pdf_bytes = bytes(pdf.output())
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'attachment; filename=translated_text.pdf'
        return response
    except Exception as e:
        print(f"[DEBUG] Error in /download_translated_pdf: {str(e)}")
        return jsonify({'error': 'Failed to generate PDF', 'details': str(e)}), 500

@app.route('/download_translated_text', methods=['POST'])
def download_translated_text():
    try:
        translated_text = request.form.get('translated_text', '')
        if not translated_text.strip():
            return jsonify({'error': 'No translated text provided'}), 400
        # Create a text file in memory
        from io import BytesIO
        file_stream = BytesIO()
        file_stream.write(translated_text.encode('utf-8'))
        file_stream.seek(0)
        response = send_file(
            file_stream,
            as_attachment=True,
            download_name='translated_text.txt',
            mimetype='text/plain'
        )
        return response
    except Exception as e:
        print(f"[DEBUG] Error in /download_translated_text: {str(e)}")
        return jsonify({'error': 'Failed to generate text file', 'details': str(e)}), 500

@app.route('/history', methods=['GET'])
def history():
    try:
        history_cursor = history_collection.find().sort('timestamp', -1)
        history_list = []
        for entry in history_cursor:
            history_list.append({
                'source_text': entry.get('source_text', ''),
                'translated_text': entry.get('translated_text', ''),
                'source_lang': entry.get('source_lang', ''),
                'target_lang': entry.get('target_lang', ''),
                'timestamp': entry.get('timestamp', '')
            })
        return jsonify(history_list)
    except Exception as e:
        return jsonify({'error': 'Failed to fetch history', 'details': str(e)}), 500

@app.route('/import_pdf', methods=['POST'])
def import_pdf():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        try:
            reader = PdfReader(file)
            content = ""
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    content += text + "\n"
            if not content.strip():
                return jsonify({'error': 'No extractable text found in PDF'}), 400
            return jsonify({'content': content})
        except Exception as e:
            print(f"[DEBUG] PDF import error: {str(e)}")
            return jsonify({'error': 'Failed to read PDF', 'details': str(e)}), 500
    except Exception as e:
        print(f"[DEBUG] Critical PDF import error: {str(e)}")
        return jsonify({'error': 'Failed to import PDF', 'details': str(e)}), 500

@app.route('/import_txt', methods=['POST'])
def import_txt():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        try:
            content = file.read().decode('utf-8', errors='replace')
            if not content.strip():
                return jsonify({'error': 'Text file is empty'}), 400
            return jsonify({'content': content})
        except Exception as e:
            print(f"[DEBUG] TXT import error: {str(e)}")
            return jsonify({'error': 'Failed to read text file', 'details': str(e)}), 500
    except Exception as e:
        print(f"[DEBUG] Critical TXT import error: {str(e)}")
        return jsonify({'error': 'Failed to import text file', 'details': str(e)}), 500

@app.route('/test_backend')
def test_backend():
    return 'Backend is reachable'

@app.route('/speak', methods=['POST'])
def speak():
    try:
        text = request.form.get('text', '')
        lang = request.form.get('lang_to', 'en')
        lang_code = gtts_lang_map.get(lang, 'en')
        if not text.strip():
            return jsonify({'error': 'No text provided'}), 400
        tts = gTTS(text=text, lang=lang_code)
        mp3_fp = BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        return send_file(mp3_fp, mimetype='audio/mpeg', as_attachment=False, download_name='speech.mp3')
    except Exception as e:
        print(f"[DEBUG] Error in /speak: {str(e)}")
        return jsonify({'error': 'Speech generation failed', 'details': str(e)}), 500

if __name__ == '__main__':
    # Running with debug=True enables the debugger, but use_reloader=False prevents the OSError on Windows
    app.run(debug=True, use_reloader=False)