import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import math
import pyautogui
import threading
import webview
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import time
import os
import json
import urllib.parse

# --- Configuración de Inteligencia Artificial (MediaPipe) ---
base_options = python.BaseOptions(model_asset_path='face_landmarker.task')
options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    num_faces=1,
    min_face_detection_confidence=0.5,
    min_face_presence_confidence=0.5,
    min_tracking_confidence=0.5
)
detector = vision.FaceLandmarker.create_from_options(options)

hand_base_options = python.BaseOptions(model_asset_path='hand_landmarker.task')
hand_options = vision.HandLandmarkerOptions(
    base_options=hand_base_options,
    num_hands=1,
    min_hand_detection_confidence=0.5,
    min_hand_presence_confidence=0.5,
    min_tracking_confidence=0.5
)
hands_detector = vision.HandLandmarker.create_from_options(hand_options)

# --- Variables Globales ---
current_frame = None
current_mar = 0.0
current_nose_y = 0.0

mar_threshold = 0.05
nose_y_baseline = 0.0
calibrated = False
game_started = False
paused = False
running = True

space_pressed = False
down_pressed = False
hand_pressed = False
pyautogui.PAUSE = 0.0
pyautogui.FAILSAFE = False

# Colores Dinámicos de Fondo
current_bg_color = "#f7f7f7"
bg_color_bgr = (247, 247, 247)
text_color = (0, 0, 0)

# --- Manejadores del Archivo de Ranking ---
RANKING_FILE = 'ranking.json'

def load_ranking():
    if os.path.exists(RANKING_FILE):
        try:
            with open(RANKING_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_ranking(scores):
    with open(RANKING_FILE, 'w', encoding='utf-8') as f:
        json.dump(scores, f, ensure_ascii=False, indent=4)

def get_distance(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

# --- Servidor HTTP (Archivos Web y Transmisión MJPEG) ---
class CamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Servir assets del juego local (t-rex-runner) para no depender de internet y evitar CORS
        if self.path.startswith('/t-rex-runner/'):
            try:
                req_path = self.path.split('?')[0]
                rel_path = req_path[len('/t-rex-runner/'):]
                filepath = os.path.join(os.getcwd(), 't-rex-runner', rel_path.replace('/', os.sep))
                if os.path.exists(filepath) and os.path.isfile(filepath):
                    with open(filepath, 'rb') as f:
                        self.send_response(200)
                        if filepath.endswith('.css'): self.send_header('Content-type', 'text/css')
                        elif filepath.endswith('.js'): self.send_header('Content-type', 'application/javascript')
                        elif filepath.endswith('.png'): self.send_header('Content-type', 'image/png')
                        elif filepath.endswith('.html'): self.send_header('Content-type', 'text/html')
                        elif filepath.endswith('.wav'): self.send_header('Content-type', 'audio/wav')
                        self.end_headers()
                        self.wfile.write(f.read())
                else:
                    self.send_response(404)
                    self.end_headers()
            except Exception as e:
                self.send_response(500)
                self.end_headers()
            return

        if self.path.endswith('.mjpg'):
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=--jpgboundary')
            self.end_headers()
            while True:
                if current_frame is not None:
                    ret, jpeg = cv2.imencode('.jpg', current_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                    if ret:
                        try:
                            self.wfile.write(b'--jpgboundary\r\n')
                            self.send_header('Content-type', 'image/jpeg')
                            self.send_header('Content-length', str(len(jpeg)))
                            self.end_headers()
                            self.wfile.write(jpeg.tobytes())
                        except:
                            break
                time.sleep(0.05)
        elif self.path == '/calibrate':
            global calibrated, mar_threshold, nose_y_baseline
            mar_threshold = current_mar * 1.5 if current_mar > 0.01 else 0.05
            nose_y_baseline = current_nose_y
            calibrated = True
            self.send_response(200)
            self.end_headers()
        elif self.path.startswith('/pause'):
            global paused
            state = self.path.split('=')[1] if '=' in self.path else '0'
            paused = (state == '1')
            self.send_response(200)
            self.end_headers()
        elif self.path.startswith('/ranking'):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            scores = load_ranking()
            
            if 'reset' in query:
                scores = []
                save_ranking(scores)
            elif 'add_name' in query and 'add_score' in query:
                name = query['add_name'][0]
                institution = query.get('add_inst', [''])[0]
                try:
                    score = int(query['add_score'][0])
                except:
                    score = 0
                
                existing = next((s for s in scores if s['name'].lower() == name.lower()), None)
                if existing:
                    if score > existing['score']:
                        existing['score'] = score
                        if institution:
                            existing['institution'] = institution
                else:
                    scores.append({'name': name, 'institution': institution, 'score': score})
                
                scores.sort(key=lambda x: x['score'], reverse=True)
                save_ranking(scores)

            try:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(scores).encode('utf-8'))
            except Exception:
                pass
        elif self.path == '/reset':
            global game_started
            calibrated = False
            game_started = False
            paused = False
            self.send_response(200)
            self.end_headers()
        elif self.path.startswith('/set_dark_mode'):
            global current_bg_color, bg_color_bgr, text_color
            state = self.path.split('=')[1] if '=' in self.path else '0'
            if state == '1':
                current_bg_color = "#202124"
                bg_color_bgr = (36, 33, 32)
                text_color = (255, 255, 255)
            else:
                current_bg_color = "#f7f7f7"
                bg_color_bgr = (247, 247, 247)
                text_color = (0, 0, 0)
            self.send_response(200)
            self.end_headers()
        elif self.path == '/close':
            self.send_response(200)
            self.end_headers()
            import webview
            if webview.windows:
                webview.windows[0].destroy()
        elif self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            html = """<!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body, html { zoom: 0.972; margin: 0; padding: 0; height: 100%; overflow: hidden; background: #f7f7f7; font-family: Arial, sans-serif; }
                    
                    /* Transiciones suaves para el modo noche */
                    body, html, #game-container, #bottom-cover, #pip, #leaderboard-container, #instructions-container, #developer-footer { 
                        transition: background-color 0.5s ease, color 0.5s ease;
                    }
                    
                    #game-container { 
                        width: 100%; 
                        height: 100%; 
                        position: relative;
                        background: #f7f7f7;
                    }
                    
                    /* Iframe local: No hay problemas de CORS */
                    iframe { 
                        width: 835px; 
                        height: 260px; /* Altura restringida para que el canvas se centre correctamente */
                        border: none; 
                        position: absolute;
                        top: 0px; 
                        left: 20px; 
                        z-index: 1;
                    }
                    
                    #bottom-cover {
                        position: absolute;
                        top: 260px; 
                        left: 0;
                        width: 100%;
                        height: 400px;
                        background-color: #f7f7f7;
                        z-index: 10; 
                    }
                    
                    /* Feed de la cámara PiP */
                    #pip {
                        position: absolute;
                        top: 10px; 
                        right: 20px;
                        width: 320px;
                        border: 3px solid #e0e0e0;
                        border-radius: 12px;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                        z-index: 100;
                        background: #f7f7f7;
                        cursor: pointer;
                    }

                    #focus-trap {
                        position: absolute;
                        top: 0; left: 0; width: 100%; height: 100%;
                        z-index: 50; 
                        background: transparent;
                    }
                    
                    body.dark-mode input {
                        background-color: #333 !important;
                        color: #fff !important;
                        border-color: #555 !important;
                    }
                    body.dark-mode input::placeholder {
                        color: #bbb !important;
                    }
                    
                    /* Layout Inferior */
                    #bottom-flex {
                        position: absolute;
                        top: 295px;
                        left: 0;
                        width: 100%;
                        display: flex;
                        justify-content: center;
                        align-items: stretch;
                        gap: 40px;
                        z-index: 100;
                    }
                    /* Controles */
                    #controls-container {
                        width: 250px; 
                        display: flex;
                        flex-direction: column;
                        gap: 15px;
                        justify-content: center;
                    }
                    #controls-container .btn {
                        padding: 15px 5px;
                        font-size: 14px;
                    }
                    #controls {
                        display: flex;
                        gap: 8px;
                    }
                    .btn {
                        flex: 1;
                        padding: 12px 5px;
                        font-family: Arial, sans-serif;
                        font-size: 13px;
                        font-weight: bold;
                        border-radius: 8px;
                        border: 2px solid;
                        background: white;
                        cursor: pointer;
                        text-align: center;
                        transition: 0.2s;
                    }
                    .btn:hover { background: #f0f0f0; }
                    .btn-pause { border-color: #ff9800; color: #e65100; }
                    .btn-reset { border-color: #2196f3; color: #0d47a1; }
                    .btn-practice { border-color: #9c27b0; color: #7b1fa2; }
                    .btn-calibrate { border-color: #4CAF50; color: white; background: #4CAF50; }
                    .btn-calibrate:hover { background: #388E3C !important; }
                    .btn-close { border-color: #d32f2f; color: white; background: #f44336; }
                    .btn-close:hover { background: #c62828 !important; }

                    /* Leaderboard Top 3 */
                    #leaderboard-container {
                        position: absolute;
                        top: 295px; 
                        left: 20px;
                        width: 320px;
                        background: #f7f7f7;
                        border: 3px solid #e0e0e0;
                        border-radius: 12px;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                        padding: 8px 10px;
                        z-index: 100;
                    }
                    .rank-item { 
                        display: flex; 
                        justify-content: space-between; 
                        font-size: 14px; 
                        margin: 4px 0; 
                        font-weight: bold; 
                        padding: 4px;
                        border-radius: 6px;
                    }
                    .gold { color: #d4af37; background: rgba(255, 215, 0, 0.1); border-left: 4px solid #d4af37; }
                    .silver { color: #9e9e9e; background: rgba(192, 192, 192, 0.1); border-left: 4px solid #9e9e9e; }
                    .bronze { color: #cd7f32; background: rgba(205, 127, 50, 0.1); border-left: 4px solid #cd7f32; }
                    
                    /* Instrucciones de Juego */
                    #instructions-container {
                        width: 450px;
                        box-sizing: border-box;
                        background: #f7f7f7;
                        border: 3px solid #e0e0e0;
                        border-radius: 12px;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                        padding: 15px 20px;
                        font-family: Arial, sans-serif;
                        font-size: 14px;
                        line-height: 1.5;
                        display: flex;
                        flex-direction: column;
                        justify-content: center;
                    }
                    #instructions-container h3 {
                        margin: 0 0 5px 0; 
                        text-align: center; 
                        border-bottom: 2px solid #ddd; 
                        padding-bottom: 3px;
                        color: #2196f3;
                    }
                    #instructions-container ol {
                        margin: 0;
                        padding-left: 20px;
                        font-size: 13.5px;
                        line-height: 1.6;
                    }
                    #instructions-container li { margin-bottom: 5px; }
                    .instr-highlight { font-weight: bold; color: #ff9800; }
                    
                    .btn-reset-rank {
                        width: 100%; 
                        margin-top: 10px; 
                        background: transparent; 
                        border: 1px solid #d32f2f; 
                        color: #d32f2f; 
                        padding: 6px; 
                        border-radius: 4px; 
                        cursor: pointer; 
                        font-size: 11px; 
                        font-weight: bold;
                        transition: 0.2s;
                    }
                    .btn-reset-rank:hover { background: #ffebee; }
                    
                    /* Historial Modal */
                    .btn-history {
                        width: 100%; margin-top: 5px; background: #e0e0e0; color: #333;
                        border: none; padding: 6px; border-radius: 4px; cursor: pointer;
                        font-size: 11px; font-weight: bold; transition: 0.2s;
                    }
                    .btn-history:hover { background: #bdbdbd; }
                    
                    #modal-overlay {
                        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                        background: rgba(0,0,0,0.5); z-index: 1000; display: none;
                        align-items: center; justify-content: center;
                    }
                    #modal-history {
                        background: #f7f7f7; width: 400px; max-height: 80%; border-radius: 12px;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.3); padding: 20px;
                        display: flex; flex-direction: column; position: relative;
                    }
                    #modal-history h3 { margin-top: 0; border-bottom: 2px solid #ddd; padding-bottom: 10px; text-align: center; color: #2196f3; }
                    #modal-close { position: absolute; top: 15px; right: 20px; cursor: pointer; font-weight: bold; color: #666; font-size: 18px; }
                    #modal-content { max-height: 300px; overflow-y: auto; flex: 1; padding-right: 5px; }
                    #modal-content::-webkit-scrollbar { width: 8px; }
                    #modal-content::-webkit-scrollbar-track { background: #eee; border-radius: 4px; }
                    #modal-content::-webkit-scrollbar-thumb { background: #bbb; border-radius: 4px; }
                    .hist-item { display: flex; justify-content: space-between; padding: 8px; border-bottom: 1px solid #eee; font-size: 14px; }
                    .hist-name { font-weight: bold; color: #555; }
                    .hist-score { color: #2196f3; font-weight: bold; }
                    
                    /* Game Over Overlay */
                    #game-over-overlay {
                        position: absolute; top: 0px; left: 437px; transform: translateX(-50%); 
                        width: max-content; padding: 0 5px; height: 260px;
                        z-index: 2; display: none; align-items: center; justify-content: center;
                        flex-direction: column; background: var(--bg-color, #f7f7f7);
                    }
                    .go-title { font-size: 32px; font-weight: bold; margin-bottom: 5px; text-align: center; text-transform: uppercase; }
                    .go-subtitle { font-size: 16px; color: #666; text-align: center; }
                    .go-record { font-size: 36px; font-weight: bold; color: #ffeb3b; text-shadow: 0px 2px 4px rgba(0,0,0,0.3); margin-top: 0px; }
                    .go-retry { font-size: 16px; margin-top: 10px; color: #2196f3; font-weight: bold; animation: blink 1.5s infinite; }
                    @keyframes blink { 0% {opacity: 1;} 50% {opacity: 0.4;} 100% {opacity: 1;} }
                    
                    /* Título Principal */
                    #main-title {
                        position: absolute; top: 20px; left: 20px; width: 835px; text-align: center;
                        z-index: 20; pointer-events: none; transition: opacity 0.5s ease, top 0.5s ease, transform 0.5s ease, background 0.5s ease, border-radius 0.5s ease;
                        transform-origin: top center;
                        background: var(--bg-color, #f7f7f7);
                        padding: 15px 0;
                        border-radius: 12px;
                    }
                    #main-title.small-mode {
                        top: 225px; transform: scale(0.5); background: transparent; padding: 0;
                    }
                    #main-title.small-mode h2 { opacity: 0; }
                    #main-title h1 {
                        background: linear-gradient(to right, #2E7D32, #81C784);
                        -webkit-background-clip: text; color: transparent;
                        font-size: 56px; margin: 0; font-weight: 900; text-transform: uppercase;
                        text-shadow: 2px 2px 4px rgba(0,0,0,0.15); letter-spacing: 2px;
                    }
                    #main-title h2 {
                        font-size: 20px; color: #666; margin: 5px 0 0 0; font-weight: bold; letter-spacing: 1px;
                        text-transform: uppercase; transition: opacity 0.3s ease;
                    }
                    
                    /* Custom Tooltip */
                    .hist-item { position: relative; }
                    .hist-item[data-fullname]:hover::after {
                        content: attr(data-fullname); position: absolute; top: 2px; left: 20px;
                        background: #222; color: #fff; padding: 4px 10px;
                        border-radius: 4px; font-size: 14px; white-space: nowrap; z-index: 2000;
                        pointer-events: none;
                        box-shadow: 0 4px 10px rgba(0,0,0,0.3); font-weight: normal;
                    }
                    
                    /* Custom Toast */
                    #custom-toast {
                        visibility: hidden; min-width: 250px; margin-left: -125px;
                        background-color: #2196f3; color: #fff; text-align: center;
                        border-radius: 8px; padding: 16px; position: fixed; z-index: 3000;
                        left: 50%; top: 20px; font-size: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.4);
                        opacity: 0; transition: opacity 0.3s, top 0.3s; font-weight: bold; white-space: pre-wrap;
                    }
                    #custom-toast.show { visibility: visible; opacity: 1; top: 40px; }
                    
                    /* Password Modal */
                    #password-overlay {
                        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                        background: rgba(0,0,0,0.6); z-index: 4000; display: none;
                        align-items: center; justify-content: center;
                        backdrop-filter: blur(5px);
                    }
                    #password-modal {
                        background: var(--bg-color, #f7f7f7); width: 350px; border-radius: 12px;
                        box-shadow: 0 10px 40px rgba(0,0,0,0.5); padding: 30px;
                        display: flex; flex-direction: column; align-items: center;
                        border: 2px solid #2196f3;
                    }
                    #password-modal h3 { margin: 0 0 15px 0; color: #2196f3; font-size: 22px; text-transform: uppercase; text-align: center; }
                    #password-container {
                        position: relative;
                        width: 100%;
                        margin-bottom: 25px;
                    }
                    #password-input { 
                        width: 100%; padding: 12px; padding-right: 40px; border: 2px solid #ccc; border-radius: 8px; box-sizing: border-box;
                        font-size: 16px; text-align: center; font-weight: bold;
                        outline: none; transition: border-color 0.3s;
                    }
                    #password-input::-ms-reveal { display: none; }
                    #toggle-password {
                        position: absolute;
                        right: 12px;
                        top: 50%;
                        transform: translateY(-50%);
                        cursor: pointer;
                        font-size: 18px;
                        user-select: none;
                        color: #666;
                        transition: 0.2s;
                    }
                    #toggle-password:hover { color: #2196f3; transform: translateY(-50%) scale(1.1); }
                    #password-input:focus { border-color: #2196f3; }
                    .pass-btn-group { display: flex; gap: 15px; width: 100%; justify-content: center; }
                    .pass-btn { 
                        flex: 1; padding: 12px; border: none; border-radius: 8px; font-weight: bold; 
                        cursor: pointer; font-size: 14px; text-transform: uppercase; transition: transform 0.2s, opacity 0.2s; 
                    }
                    .pass-btn:active { transform: scale(0.95); }
                    .pass-btn-ok { background: #2196f3; color: white; }
                    .pass-btn-cancel { background: #9e9e9e; color: white; }
                    .pass-btn:hover { opacity: 0.9; }

                    /* Botón de Silenciar Música */
                    #mute-btn {
                        position: absolute; top: 220px; left: 20px;
                        background: rgba(255, 255, 255, 0.9); border: 2px solid #ccc; border-radius: 50%;
                        width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;
                        font-size: 16px; cursor: pointer; z-index: 150; transition: all 0.2s;
                        box-shadow: 0 4px 10px rgba(0,0,0,0.2);
                    }
                    #mute-btn:hover { background: #fff; transform: scale(1.1); }
                    .dark-mode #mute-btn { background: rgba(32, 33, 36, 0.9); border-color: #555; }
                    .dark-mode #mute-btn:hover { background: #333; }

                    .eye-icon {
                        width: 20px;
                        height: 20px;
                        display: block;
                    }

                    /* Footer del Desarrollador */
                    #developer-footer {
                        position: absolute;
                        bottom: 0;
                        left: 0;
                        width: 100%;
                        text-align: center;
                        padding: 4px 0;
                        font-size: 13px;
                        font-weight: bold;
                        z-index: 5000;
                        background: #f7f7f7;
                        border-top: 2px solid #e0e0e0;
                        letter-spacing: 0.5px;
                        color: #333;
                    }
                    .dark-mode #developer-footer {
                        border-color: #555;
                        color: #fff;
                    }
                </style>
                <script>
                    let currentPlayerName = "";
                    let currentPlayerInstitution = "";
                    let currentPlayerMaxScore = 0;
                    let isPlayerRegistered = false;
                    let isPracticeMode = false;
                    let globalScores = [];
                    let hasGameStartedUI = false;
                    let isGameOver = false;
                    let bgMusic = new Audio('/t-rex-runner/assets/bg_music.wav');
                    bgMusic.loop = true;
                    bgMusic.volume = 0.3;

                    // Sistema de Toast
                    function showToast(msg) {
                        let toast = document.getElementById('custom-toast');
                        toast.innerText = msg;
                        toast.classList.add('show');
                        setTimeout(() => { toast.classList.remove('show'); }, 3000);
                    }

                    // Lógica del Ranking vía Servidor Python
                    function loadScores() {
                        fetch('/ranking')
                            .then(r => r.json())
                            .then(data => renderScores(data));
                    }

                    function saveScore(name, inst, score) {
                        if (!name) return;
                        fetch(`/ranking?add_name=${encodeURIComponent(name)}&add_score=${score}&add_inst=${encodeURIComponent(inst)}`)
                            .then(r => r.json())
                            .then(data => renderScores(data));
                    }

                    function resetRanking() {
                        let overlay = document.getElementById('password-overlay');
                        let input = document.getElementById('password-input');
                        input.value = '';
                        input.type = 'password';
                        document.getElementById('toggle-password').innerHTML = eyeClosedSVG;
                        overlay.style.display = 'flex';
                        input.focus();
                    }
                    
                    function submitPassword() {
                        let input = document.getElementById('password-input');
                        let pass = input.value;
                        if (pass === "admin") {
                            fetch('/ranking?reset=1')
                                .then(r => r.json())
                                .then(data => {
                                    renderScores(data);
                                    closePasswordModal();
                                    showToast("Ranking restablecido exitosamente.");
                                });
                        } else {
                            showToast("Contraseña incorrecta.");
                            input.value = '';
                            input.focus();
                        }
                    }
                    
                    function closePasswordModal() {
                        document.getElementById('password-overlay').style.display = 'none';
                    }

                    const eyeOpenSVG = `<svg class="eye-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
                    const eyeClosedSVG = `<svg class="eye-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>`;

                    function togglePassword() {
                        let input = document.getElementById('password-input');
                        let btn = document.getElementById('toggle-password');
                        if (input.type === "password") {
                            input.type = "text";
                            btn.innerHTML = eyeOpenSVG;
                        } else {
                            input.type = "password";
                            btn.innerHTML = eyeClosedSVG;
                        }
                    }

                    function toggleMute() {
                        let btn = document.getElementById('mute-btn');
                        if (bgMusic.muted) {
                            bgMusic.muted = false;
                            btn.innerText = "🔊";
                        } else {
                            bgMusic.muted = true;
                            btn.innerText = "🔇";
                        }
                        let iframe = document.querySelector('iframe');
                        if (iframe) iframe.focus();
                    }

                    function renderScores(scores) {
                        if (!scores) return;
                        globalScores = scores;
                        
                        let badge = document.getElementById('history-badge');
                        if (badge) {
                            if (scores.length > 0) {
                                badge.innerText = scores.length;
                                badge.style.display = 'block';
                            } else {
                                badge.style.display = 'none';
                            }
                        }
                        
                        let html = '';
                        let medals = ['🥇', '🥈', '🥉'];
                        let classes = ['gold', 'silver', 'bronze'];
                        
                        let isDark = document.body.style.backgroundColor === 'rgb(32, 33, 36)' || document.body.style.backgroundColor === '#202124';
                        let scoreColor = isDark ? '#fff' : '#333';

                        for(let i=0; i<3; i++) {
                            if (!scores[i]) continue;
                            let fullName = scores[i].name;
                            let displayName = scores[i].name;
                            if (scores[i].institution) {
                                let inst = scores[i].institution;
                                fullName += ` [${inst}]`;
                                if (inst.length > 15) inst = inst.substring(0, 15) + '...';
                                displayName += ` [${inst}]`;
                            }
                            let score = scores[i].score;
                            html += `<div class="rank-item ${classes[i]}">
                                <span>${medals[i]} ${i+1}. ${displayName}</span> 
                                <span style="color:${scoreColor}">${score}</span>
                            </div>`;
                        }
                        if(html === '') html = '<div style="text-align:center;color:#888;font-size:12px;">Sin registros</div>';
                        document.getElementById('top3-list').innerHTML = html;
                        renderHistoryModal();
                    }

                    function renderHistoryModal() {
                        let content = document.getElementById('modal-content');
                        if (!content) return;
                        if (globalScores.length === 0) {
                            content.innerHTML = '<div style="text-align:center;color:#888;padding:20px;">No hay registros históricos.</div>';
                            return;
                        }
                        let html = '';
                        let medals = ['🥇', '🥈', '🥉'];
                        for(let i=0; i<globalScores.length; i++) {
                            let fullName = globalScores[i].name;
                            let displayName = globalScores[i].name;
                            if (globalScores[i].institution) {
                                let inst = globalScores[i].institution;
                                fullName += ` [${inst}]`;
                                if (inst.length > 15) inst = inst.substring(0, 15) + '...';
                                displayName += ` [${inst}]`;
                            }
                            let score = globalScores[i].score;
                            let prefix = i < 3 ? medals[i] + ' ' : '';
                            
                            let scoreColor = '#2196f3';
                            if(i === 0) scoreColor = '#d4af37';
                            else if(i === 1) scoreColor = '#9e9e9e';
                            else if(i === 2) scoreColor = '#cd7f32';
                            
                            html += `<div class="hist-item" data-fullname="${fullName}">
                                <span class="hist-name">${prefix}${i+1}. ${displayName}</span>
                                <span class="hist-score" style="color: ${scoreColor}">${score}</span>
                            </div>`;
                        }
                        content.innerHTML = html;
                    }

                    function toggleModal() {
                        let modal = document.getElementById('modal-overlay');
                        if(modal.style.display === 'flex') {
                            modal.style.display = 'none';
                        } else {
                            renderHistoryModal();
                            modal.style.display = 'flex';
                        }
                    }

                    function addPlayer() {
                        let nameInput = document.getElementById('player-name');
                        let instInput = document.getElementById('player-institution');
                        let name = nameInput.value.trim();
                        let inst = instInput ? instInput.value.trim() : "";
                        
                        if (name.length < 3) {
                            showToast("El nombre debe tener al menos 3 letras.");
                            return;
                        }
                        
                        currentPlayerName = name;
                        currentPlayerInstitution = inst;
                        currentPlayerMaxScore = 0;
                        isPlayerRegistered = true;
                        
                        nameInput.disabled = true;
                        if(instInput) instInput.disabled = true;
                        document.getElementById('btn-add-player').disabled = true;
                        
                        let calBtn = document.getElementById('btn-calibrate');
                        calBtn.disabled = false;
                        calBtn.style.opacity = "1";
                        
                        showToast(`Nombre agregado exitosamente: ${name}\n\n¡Ya puedes CALIBRAR y jugar!`);
                    }

                    function doCalibrate() {
                        fetch('/calibrate');
                        var trap = document.getElementById('focus-trap');
                        if (trap) trap.style.display = 'none';
                        document.querySelector('iframe').focus();
                    }

                    function togglePause() {
                        var btn = document.getElementById('btn-pause');
                        
                        let iframe = document.querySelector('iframe');
                        let runner = iframe.contentWindow && iframe.contentWindow.Runner ? iframe.contentWindow.Runner.instance_ : null;

                        if (btn.innerText === "PAUSAR") {
                            btn.innerText = "REANUDAR";
                            fetch('/pause?state=1');
                            
                            if (runner && runner.playing) {
                                runner.stop();
                            }
                        } else {
                            btn.innerText = "PAUSAR";
                            fetch('/pause?state=0');
                            
                            if (runner && !runner.playing && !runner.crashed) {
                                runner.play();
                            }
                        }
                        iframe.focus();
                    }

                    function togglePractice() {
                        if (!isPracticeMode) {
                            isPracticeMode = true;
                            let btn = document.getElementById('btn-practice');
                            let nameInput = document.getElementById('player-name');
                            let instInput = document.getElementById('player-institution');
                            let btnAdd = document.getElementById('btn-add-player');
                            let calBtn = document.getElementById('btn-calibrate');

                            btn.innerText = "PRÁCTICA EN CURSO";
                            btn.style.background = "#e1bee7";
                            nameInput.disabled = true;
                            if(instInput) instInput.disabled = true;
                            btnAdd.disabled = true;
                            
                            calBtn.disabled = false;
                            calBtn.style.opacity = "1";
                            
                            isPlayerRegistered = true;
                            showToast("Modo práctica activado. Puntajes no se guardarán.");
                            document.querySelector('iframe').focus();
                        } else {
                            doReset();
                            showToast("Modo práctica desactivado. Por favor, ingresá un nombre para jugar.");
                        }
                    }

                    function doReset() {
                        document.getElementById('game-over-overlay').style.display = 'none';
                        
                        hasGameStartedUI = false;
                        isGameOver = false;
                        bgMusic.pause();
                        bgMusic.currentTime = 0;
                        
                        let mt = document.getElementById('main-title');
                        mt.classList.remove('small-mode');
                        mt.style.opacity = '1';

                        let iframe = document.querySelector('iframe');
                        if (iframe.contentWindow) {
                            iframe.contentWindow.Runner = null;
                        }
                        iframe.src = iframe.src;

                        fetch('/reset');
                        var trap = document.getElementById('focus-trap');
                        if (trap) trap.style.display = 'block';
                        
                        var btn = document.getElementById('btn-pause');
                        btn.innerText = "PAUSAR";
                    }

                    function doClose() {
                        fetch('/close');
                    }

                    window.addEventListener('keydown', function(e) {
                        if (e.key === 'Enter') {
                            let iframe = document.querySelector('iframe');
                            if (iframe && iframe.contentWindow && iframe.contentWindow.Runner) {
                                let runner = iframe.contentWindow.Runner.instance_;
                                if (runner && runner.crashed) {
                                    let now = Date.now();
                                    if (window.lastBlinkTime && now - window.lastBlinkTime < 1000) return;
                                    window.lastBlinkTime = now;
                                    runner.restart();
                                }
                            }
                        }
                        if (e.key.toLowerCase() === 'c') {
                            doCalibrate();
                        }
                    });
                    
                    window.onload = function() {
                        window.focus();
                        loadScores();

                        setInterval(function() {
                            let iframe = document.querySelector('iframe');
                            if (!iframe.contentWindow || !iframe.contentWindow.Runner) return;
                            
                            let runner = iframe.contentWindow.Runner.instance_;
                            if (!runner) return;

                            let isDark = iframe.contentWindow.document.body.classList.contains('inverted');
                            let color = isDark ? '#202124' : '#f7f7f7';
                            let textColor = isDark ? '#ffffff' : '#000000';
                            
                            if (document.body.style.backgroundColor !== color) {
                                document.body.style.setProperty('--bg-color', color);
                                document.body.style.backgroundColor = color;
                                document.getElementById('game-container').style.backgroundColor = color;
                                document.getElementById('bottom-cover').style.backgroundColor = color;
                                document.getElementById('pip').style.backgroundColor = color;
                                document.getElementById('instructions-container').style.backgroundColor = color;
                                document.getElementById('instructions-container').style.color = textColor;
                                document.getElementById('game-over-overlay').style.backgroundColor = color;
                                document.getElementById('game-over-overlay').style.color = textColor;
                                document.getElementById('main-subtitle').style.color = textColor;
                                document.getElementById('developer-footer').style.backgroundColor = color;
                                document.getElementById('developer-footer').style.color = textColor;
                                
                                if (isDark) {
                                    document.body.classList.add('dark-mode');
                                } else {
                                    document.body.classList.remove('dark-mode');
                                }
                                
                                fetch('/set_dark_mode?state=' + (isDark ? '1' : '0'));
                                loadScores();
                            }
                            
                            if (runner.playing && !runner.crashed) {
                                if (bgMusic.paused) {
                                    bgMusic.play().catch(e => console.log("Audio play prevented"));
                                }
                            } else {
                                if (!bgMusic.paused) {
                                    bgMusic.pause();
                                }
                            }
                            
                            if (runner.playing && !hasGameStartedUI) {
                                hasGameStartedUI = true;
                                document.getElementById('main-title').style.opacity = '0';
                            }

                            if (runner.gameOverPanel && !runner.gameOverPanel._hijacked) {
                                runner.gameOverPanel.draw = function() {};
                                runner.gameOverPanel._hijacked = true;
                            }

                            if (!runner._hijackedEvents) {
                                let originalPlay = runner.play;
                                runner.play = function() {
                                    let btnPause = document.getElementById('btn-pause');
                                    if (btnPause && btnPause.innerText === "REANUDAR") {
                                        return; // No reanudar si está pausado manualmente
                                    }
                                    originalPlay.call(this);
                                };

                                iframe.contentWindow.addEventListener('keydown', function(e) {
                                    let btnPause = document.getElementById('btn-pause');
                                    if (btnPause && btnPause.innerText === "REANUDAR") {
                                        e.stopPropagation();
                                        e.preventDefault();
                                        return;
                                    }
                                    if (runner.crashed) {
                                        if (e.keyCode === 13) {
                                            e.stopPropagation();
                                            e.preventDefault();
                                            let now = Date.now();
                                            if (window.lastBlinkTime && now - window.lastBlinkTime < 1000) return;
                                            window.lastBlinkTime = now;
                                            
                                            if (!e.repeat) {
                                                runner.restart();
                                            }
                                        } else if (e.keyCode === 32 || e.keyCode === 38) {
                                            // Bloquear boca para que no reinicie el juego
                                            e.stopPropagation();
                                            e.preventDefault();
                                        }
                                    }
                                }, true); // true = capture phase
                                
                                iframe.contentWindow.addEventListener('keyup', function(e) {
                                    let btnPause = document.getElementById('btn-pause');
                                    if (btnPause && btnPause.innerText === "REANUDAR") {
                                        e.stopPropagation();
                                        e.preventDefault();
                                        return;
                                    }
                                    if (runner.crashed) {
                                        if (e.keyCode === 32 || e.keyCode === 38 || e.keyCode === 13) {
                                            e.stopPropagation();
                                            e.preventDefault();
                                        }
                                    }
                                }, true);
                                
                                runner._hijackedEvents = true;
                            }

                            if (runner.crashed && !isGameOver) {
                                isGameOver = true;
                                window.restartPressCount = 0;
                                
                                document.getElementById('bottom-cover').style.top = '240px';
                                
                                let distance = runner.distanceRan;
                                let coef = runner.distanceMeter ? runner.distanceMeter.config.COEFFICIENT : 0.025;
                                let score = Math.round(distance * coef);
                                
                                let goOverlay = document.getElementById('game-over-overlay');
                                let goTitle = document.getElementById('go-title');
                                let goRecord = document.getElementById('go-record');
                                goOverlay.style.display = 'flex';
                                goRecord.innerText = score;
                                document.querySelector('.go-retry').innerText = "¡MOSTRÁ LA PALMA ABIERTA PARA REINTENTAR!";
                                
                                let msgs = ["¡A PRACTICAR! 🏃", "¡DALE, OTRA VEZ! 💪", "¡UF, CASI! 😅", "¡NADA MAL! 👍", "¡VAS MEJORANDO! 🚀", "¡BUEN INTENTO! 👏", "¡EXCELENTE! 🔥", "¡CASI EXPERTO! 🌟", "¡MUY BUENA! 😲"];
                                goTitle.innerText = msgs[Math.floor(Math.random() * msgs.length)];
                                
                                let mt = document.getElementById('main-title');
                                mt.classList.add('small-mode');
                                mt.style.opacity = '1';
                                
                            } else if (!runner.crashed && isGameOver) {
                                isGameOver = false;
                                document.getElementById('bottom-cover').style.top = '260px';
                                document.getElementById('game-over-overlay').style.display = 'none';
                                document.getElementById('main-title').style.opacity = '0';
                            }
                        }, 500);
                    }
                </script>
                <style>
                    #main-title { z-index: 20; }
                </style>
            </head>
            <body>
                <div id="main-title">
                    <h1>Arcade Dino</h1>
                    <h2 id="main-subtitle">Controlá el juego con tu cara</h2>
                </div>
                <div id="game-container">
                    <iframe src="/t-rex-runner/index.html" scrolling="no"></iframe>
                    <div id="bottom-cover"></div>
                    <div id="focus-trap" onclick="window.focus();"></div>
                    
                    <div id="game-over-overlay">
                        <div class="go-title" id="go-title">¡BUEN INTENTO!</div>
                        <div class="go-subtitle" id="go-subtitle">Puntaje</div>
                        <div class="go-record" id="go-record">0</div>
                        <div class="go-retry">¡MOSTRÁ LA PALMA ABIERTA PARA REINTENTAR!</div>
                    </div>
                </div>
                

                
                <div id="custom-toast"></div>
                
                <img id="pip" src="/cam.mjpg" onclick="doCalibrate()" title="Clica aquí o presiona C para calibrar" />
                <button id="mute-btn" onclick="toggleMute()" title="Activar/Desactivar Música">🔊</button>
                
                <div id="bottom-flex">
                    <div id="instructions-container">
                        <h3>🎮 CÓMO JUGAR 🎮</h3>
                        <ol>
                            <li>Mirar derecho a la cámara y <span class="instr-highlight">cerrar la boca</span>.</li>
                            <li>Presiona el botón verde <b>CALIBRAR</b> (o la letra <span class="instr-highlight">C</span>).</li>
                            <li>Para <b>SALTAR</b>: <span class="instr-highlight">Abre la boca</span>.</li>
                            <li>Para <b>AGACHARTE</b>: <span class="instr-highlight">Baja un poco la cabeza</span>.</li>
                            <li>Para <b>JUGAR DE NUEVO</b>: <span class="instr-highlight">Muestra la palma</span>.</li>
                            <li>¡Diviértete!</li>
                            <li>Al terminar, pulsa <b>NUEVO JUGADOR</b> para que otro intente, o <b>FINALIZAR JUEGO</b>.</li>
                        </ol>
                    </div>
                    <div id="controls-container">
                        <button id="btn-calibrate" class="btn btn-calibrate" onclick="doCalibrate()">CALIBRAR (Letra 'C')</button>
                        <button id="btn-pause" class="btn btn-pause" onclick="togglePause()">PAUSAR</button>
                        <button id="btn-reset" class="btn btn-reset" onclick="doReset()">NUEVO JUGADOR</button>
                        <button class="btn-close btn" onclick="doClose()">FINALIZAR JUEGO</button>
                    </div>
                </div>


                
                <div id="developer-footer">
                    Desarrollado por Nicolás Cardinaux - 2026 | Juegos interactivos para alumnos
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode('utf-8'))
            
    def log_message(self, format, *args):
        pass

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass

def start_server():
    server = ThreadedHTTPServer(('localhost', 8080), CamHandler)
    server.serve_forever()

# --- Bucle Principal de Video y Detección Facial (OpenCV) ---
def video_loop():
    global current_frame, calibrated, mar_threshold, nose_y_baseline
    global space_pressed, down_pressed, hand_pressed, current_mar, current_nose_y, game_started, paused, running
    
    cap = cv2.VideoCapture(0)
    
    while running:
        success, frame = cap.read()
        if not success:
            continue
            
        frame = cv2.flip(frame, 1)
        h_cam, w_cam, _ = frame.shape
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        results = detector.detect(mp_image)
        
        display_frame = frame.copy()
        
        # Deteccion de Mano (Reiniciar partida)
        hand_results = hands_detector.detect(mp_image)
        is_hand_open = False
        if hand_results.hand_landmarks:
            for hand_landmarks in hand_results.hand_landmarks:
                tips = [8, 12, 16, 20]
                pips = [6, 10, 14, 18]
                wrist = hand_landmarks[0]
                open_fingers = 0
                for tip, pip in zip(tips, pips):
                    dist_tip = get_distance((hand_landmarks[tip].x, hand_landmarks[tip].y), (wrist.x, wrist.y))
                    dist_pip = get_distance((hand_landmarks[pip].x, hand_landmarks[pip].y), (wrist.x, wrist.y))
                    if dist_tip > dist_pip:
                        open_fingers += 1
                if open_fingers >= 3:
                    is_hand_open = True
                    
                if len(hand_landmarks) > 9:
                    lm = hand_landmarks[9]
                    cv2.circle(display_frame, (int(lm.x * w_cam), int(lm.y * h_cam)), 10, (0, 255, 255), -1)
        
        if results.face_landmarks:
            face = results.face_landmarks[0]
            landmarks = [(int(lm.x * w_cam), int(lm.y * h_cam)) for lm in face]
            
            p_top, p_bottom, p_left, p_right = landmarks[13], landmarks[14], landmarks[78], landmarks[308]
            v_dist = get_distance(p_top, p_bottom)
            h_dist = get_distance(p_left, p_right)
            current_mar = v_dist / h_dist if h_dist > 0 else 0
            
            current_nose_y = landmarks[1][1]
            f_top, f_bottom, f_left, f_right = landmarks[10], landmarks[152], landmarks[234], landmarks[454]
            face_height = get_distance(f_top, f_bottom)
            
            if not calibrated:
                cv2.rectangle(display_frame, (f_left[0], f_top[1]), (f_right[0], f_bottom[1]), (200, 255, 200), 2)
                cv2.circle(display_frame, landmarks[1], 6, (255, 0, 0), -1) # Nariz azul
                
                cv2.rectangle(display_frame, (0, h_cam - 90), (w_cam, h_cam), bg_color_bgr, -1)
                cv2.putText(display_frame, "CALIBRACION: Boca CERRADA", (15, h_cam - 60), cv2.FONT_HERSHEY_DUPLEX, 0.7, text_color, 2)
                cv2.putText(display_frame, "Presiona 'C' para iniciar", (15, h_cam - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            else:
                cv2.rectangle(display_frame, (f_left[0], f_top[1]), (f_right[0], f_bottom[1]), (0, 255, 0), 2)
                cv2.circle(display_frame, landmarks[1], 6, (255, 0, 0), -1) # Nariz azul
                cv2.circle(display_frame, p_top, 5, (0, 0, 255), -1) # Boca rojo
                cv2.circle(display_frame, p_bottom, 5, (0, 0, 255), -1)
                
                is_mouth_open = current_mar > mar_threshold
                is_face_close = (current_nose_y - nose_y_baseline) > (face_height * 0.12)
                
                if paused:
                    cv2.putText(display_frame, "PAUSADO", (w_cam//2 - 90, h_cam//2), cv2.FONT_HERSHEY_DUPLEX, 1.2, (0, 165, 255), 3)
                    if space_pressed:
                        pyautogui.keyUp('space')
                        space_pressed = False
                    if down_pressed:
                        pyautogui.keyUp('down')
                        down_pressed = False
                else:
                    if is_mouth_open and not space_pressed:
                        if not game_started:
                            game_started = True
                        pyautogui.keyDown('space')
                        space_pressed = True
                    elif not is_mouth_open and space_pressed:
                        pyautogui.keyUp('space')
                        space_pressed = False
                        
                    if is_hand_open:
                        if not hand_pressed:
                            pyautogui.press('enter')
                            hand_pressed = True
                    else:
                        hand_pressed = False
                        
                    if is_face_close and not down_pressed:
                        pyautogui.keyDown('down')
                        down_pressed = True
                    elif not is_face_close and down_pressed:
                        pyautogui.keyUp('down')
                        down_pressed = False
                    
                color_m = (0, 255, 0) if is_mouth_open else (0, 0, 255)
                color_p = (0, 255, 0) if is_face_close else (0, 0, 255)
                
                overlay = display_frame.copy()
                cv2.rectangle(overlay, (0, h_cam - 80), (w_cam, h_cam), bg_color_bgr, -1)
                cv2.addWeighted(overlay, 0.7, display_frame, 0.3, 0, display_frame)
                
                cv2.putText(display_frame, f"Boca: {'ABIERTA' if is_mouth_open else 'Cerrada'}", (10, h_cam - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_m, 2)
                cv2.putText(display_frame, f"Cabeza: {'ABAJO' if is_face_close else 'Normal'}", (10, h_cam - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_p, 2)
        else:
            cv2.rectangle(display_frame, (0, 0), (w_cam, h_cam), bg_color_bgr, -1)
            cv2.putText(display_frame, "Rostro NO detectado", (w_cam//2 - 120, h_cam//2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            
        current_frame = display_frame

    cap.release()

if __name__ == '__main__':
    video_thread = threading.Thread(target=video_loop)
    video_thread.start()
    
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    time.sleep(1)
    window = webview.create_window('Dino de Chrome - Integrado Definitivo', 'http://localhost:8080', width=1200, height=650, resizable=False)
    webview.start()

    # Graceful shutdown to prevent MediaPipe __del__ errors
    running = False
    if video_thread.is_alive():
        video_thread.join()
        
    try:
        detector.close()
    except Exception:
        pass
        
    try:
        hands_detector.close()
    except Exception:
        pass
