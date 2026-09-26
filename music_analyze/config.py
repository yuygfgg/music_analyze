from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
TMP_AUDIO_DIR = DATA_DIR / "tmp_audio"
DB_PATH = DATA_DIR / "music.db"
COOKIE_PATH = DATA_DIR / "cookies.json"
QR_PNG_PATH = DATA_DIR / "login_qr.png"
PLOT_PATH = DATA_DIR / "bpm_energy_distribution.png"
HTML_PATH = DATA_DIR / "bpm_energy_distribution.html"
CSV_PATH = DATA_DIR / "tracks.csv"
OVERRIDES_PATH = DATA_DIR / "bpm_overrides.csv"

API_DIR = ROOT / "api"
API_ENTRY = API_DIR / "node_modules" / "@neteasecloudmusicapienhanced" / "api" / "app.js"
API_BASE = "http://127.0.0.1:3000"
API_PORT = 3000
API_LOG = DATA_DIR / "ncm_api.log"
ENABLE_RANDOM_CN_IP = True

AUDIO_LEVEL = "standard"
URL_BATCH_SIZE = 50
DETAIL_BATCH_SIZE = 500
REQUEST_MIN_DELAY = 0.25
REQUEST_MAX_DELAY = 0.6
MAX_RETRIES = 4

SAMPLE_RATE = 44100

BPM_MIN = 40.0
BPM_MAX = 220.0
DOUBLE_LOWER_BOUND = 88.0
DOUBLE_UPPER_BOUND = 200.0
MIDPOINT_PROB_RATIO = 0.8
MIDPOINT_MIN_PROB = 0.35

ENERGY_WEIGHTS = {"onset": 0.35, "flux": 0.25, "centroid": 0.20, "zcr": 0.20}
ENERGY_MAPS = {
    "onset": (3.8, 0.8),
    "flux": (0.265, 0.025),
    "centroid": (11.63, 0.45),
    "zcr": (0.072, 0.02),
}
ENERGY_ANCHORS = [
    (0.00, 0.00),
    (0.05, 0.20),
    (0.15, 0.32),
    (0.30, 0.46),
    (0.50, 0.60),
    (0.70, 0.77),
    (0.855, 0.92),
    (1.00, 1.00),
]

BPM_AXIS = (40.0, 220.0)
ENERGY_AXIS = (0.0, 1.0)
BPM_GUIDES = [85.0, 128.0, 174.0]
