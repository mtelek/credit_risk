from pathlib import Path

from kaggle.api.kaggle_api_extended import KaggleApi

DATASET = "wordsforthewise/lending-club"
TARGET_DIR = Path("/app/data/raw")

def dataset_already_downloaded(path: Path):
    return any(path.glob("*.csv"))

def main():
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    if dataset_already_downloaded(TARGET_DIR):
        print(f"Dataset already present in {TARGET_DIR}. Skipping download.")
        return

    api = KaggleApi()
    api.authenticate()
    api.dataset_download_files(DATASET, path=str(TARGET_DIR), unzip=True)

    print(f"Downloaded and extracted '{DATASET}' to {TARGET_DIR}")

if __name__ == "__main__":
    main()
