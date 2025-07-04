# S3ModelCache – Hugging Face ↔️ HCP S3 Bridge

Die Funktion "S3ModelCache" gestattet das Herunterladen (oder On-Demand-Herstellen) umfangreicher KI-Modelle von der Plattform "Hugging Face Hub" (https://huggingface.co) sowie das darauffolgende Ablegen bzw. Zwischenspeichern in einem HCP-Namespace über dessen S3-kompatible API.
Hierdurch wird die Möglichkeit geschaffen, Modelle in HCP zu hinterlegen und sie anschließend von *vLLM*-Inference-Pods (oder anderen Diensten) direkt aus dem HCP-Storage zu laden, ohne dabei die Hub-Rate-Limits zu überschreiten.

---

## Verzeichnisstruktur (klassisches `src/`-Layout)
```
├── src/
│   └── s3modelcache/
│       ├── __init__.py          # Public API
│       ├── model_cache.py       # S3ModelCache Implementierung
│       ├── logger.py            # HCPLogger / LoggedHCPCache
│       └── upload_large.py      # Multipart-Upload Helper (optional)
├── tests/                       # PyTest-Suite
├── requirements.txt
├── .env                         # Zugangsdaten + Endpunkte
└── README.md
```

## Voraussetzungen
* Python ≥ 3.10
* Abhängigkeiten aus `requirements.txt`:
  * `boto3`  (Zugriff auf HCP-S3)
  * `huggingface_hub`  (Modelldownload)
  * `vllm`  (optionales Laden & Prüfen der Modelle)
  * `botocore`

Installieren:
```bash
pip install -r requirements.txt
```

## Tests
Die Unittests befinden sich im Verzeichnis `tests/` und werden mit `pytest` ausgeführt:

```bash
python -m pytest -q          # alle Tests ausführen
# oder mit Coverage-Bericht
pytest --cov=s3modelcache --cov-report=term-missing
```


## Konfiguration
Die Verbindung zu einem beliebigen S3-kompatiblen Storage (z. B. HCP, MinIO, Ceph) erfolgt über Umgebungsvariablen oder eine `.env`-Datei (siehe Beispiel):

```env
S3_ENDPOINT="https://your-s3-endpoint.com"
S3_ACCESS_KEY_ID="your-s3-access-key"
S3_SECRET_ACCESS_KEY="your-s3-secret-key"
S3_BUCKET="my-model-bucket"
# Optional: überschreibt den Standardpfad ./model_cache
MODEL_CACHE_DIR="/mnt/cache/models"
```

## Schnellstart
```python
from s3modelcache import S3ModelCache

# Cache-Objekt initialisieren
cache = S3ModelCache(
    bucket_name="my-model-bucket",
    s3_endpoint="https://s3.your-cloud.com",
    aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
)

# Modell in den Cache holen (lädt von HF falls nicht vorhanden)
local_path = cache.get_or_download("meta-llama/Llama-3-8B-Instruct")
print(f"Modell liegt lokal unter: {local_path}")
```

## API-Referenz (Auszug)
| Methode                         | Beschreibung |
|---------------------------------|--------------|
| `get_or_download(repo_id)`      | Prüft, ob das Modell bereits im HCP-Bucket liegt. Falls nicht: download von HF → Upload nach HCP. Gibt lokalen Pfad zurück. |
| `download_from_hf(repo_id)`     | Nutzt `huggingface_hub.snapshot_download` um Artefakte abzurufen. |
| `upload_to_s3(folder)`          | Lädt ein gesamtes Verzeichnis rekursiv in den definierten Bucket/Prefix hoch. |
| `download_from_s3(repo_id)`     | Holt Artefakte aus HCP zurück in den lokalen Cache. |
| `list_cached_models(source)`    | Listet alle im lokalen Cache **oder** im S3-Bucket vorhandenen Modelle. |
| `delete_cached_model(id, ...)`  | Löscht ein Modell wahlweise lokal, in S3 oder in beiden Caches. |

## Erweiterungen

### HCPLogger – zentrales Logging
`HCPLogger.py` erweitert den Cache um strukturierte Log-Ausgaben (Datei **hcp_model_cache.log** + Console).  Nutze die Klasse `LoggedHCPCache`, die von `S3ModelCache` erbt und nach jedem Upload/Download automatisch einen Log-Eintrag schreibt.

```python
from s3modelcache.logger import LoggedHCPCache

cache = LoggedHCPCache(
    bucket_name="my-model-bucket",
    s3_endpoint=os.getenv("S3_ENDPOINT"),
    aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
)

# Modell cachen + Logging
cache.cache_model_to_s3("meta-llama/Llama-3-8B-Instruct")
```

### UploadLargeModel – Multipart-Upload
`UploadLargeModel.py` zeigt, wie sehr große Modelle (>5 GB) in mehreren Chunks parallel zu S3/HCP hochgeladen werden.  Der Helfer nutzt `boto3`-Multipart-Upload mit anpassbarer Chunk-Größe.

```python
from s3modelcache.upload_large import upload_large_model_to_hcp
from s3modelcache import S3ModelCache

cache = S3ModelCache(...)

# 500 MB-Chunks für schnelleren Upload
success = upload_large_model_to_hcp(cache, "mistral-7b-instruct", chunk_size=500*1024*1024)
print("Upload ok" if success else "Upload failed")
```

## Root-CA mit OpenSSL exportieren
Wenn dein S3-Endpoint ein selbstsigniertes Zertifikat nutzt, kannst du das Root-CA
mit OpenSSL aus der TLS-Kette extrahieren und anschließend per
`root_ca_path` an *S3ModelCache* übergeben:

```bash
# Beispiel: Zertifikat von https://s3.my-hcp.local extrahieren
openssl s_client -showcerts -connect s3.my-hcp.local:443 </dev/null \
  | openssl x509 -outform PEM -out root-ca.pem

# Optional: mehrere Zertifikate extrahieren (wenn Kette >1)
# und in eine Bundle-Datei zusammenführen.
```

Verwende anschließend:

```python
cache = S3ModelCache(
    ...,
    root_ca_path="/path/to/root-ca.pem",
)
```

---

## Tipps & Tricks
* **SSL Zertifikat:** Bei selbstsignierten HCP-Zertifikaten kann entweder `verify_ssl=False` gesetzt **oder** ein eigenes Root-CA-Bundle per Parameter `root_ca_path="/path/to/ca.pem"` übergeben werden.
* **Versionierung:** Nutze den `s3_prefix`-Parameter, um verschiedene Modellversionen getrennt abzulegen, z. B. `models/v1/`.
* **Große Modelle (>5 GB):** HCP unterstützt *Multipart Uploads* – `boto3` erledigt das automatisch.

---

© 2025  Your Name / Company – MIT License
