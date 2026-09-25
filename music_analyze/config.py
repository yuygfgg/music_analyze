from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
TMP_AUDIO_DIR = DATA_DIR / "tmp_audio"
DB_PATH = DATA_DIR / "music.db"
COOKIE_PATH = DATA_DIR / "cookies.json"
QR_PNG_PATH = DATA_DIR / "login_qr.png"
PLOT_PATH = DATA_DIR / "bpm_energy_distribution.png"
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

ENERGY_WEIGHTS = {"loudness": 0.5, "onset": 0.2, "flux": 0.2, "centroid": 0.1}
LOUDNESS_RANGE = (-30.0, -4.0)
ONSET_RATE_MAX = 8.0
FLUX_MAX = 0.6
CENTROID_RANGE_HZ = (200.0, 5000.0)

BPM_AXIS = (40.0, 220.0)
ENERGY_AXIS = (0.0, 1.0)
BPM_GUIDES = [85.0, 128.0, 174.0]
