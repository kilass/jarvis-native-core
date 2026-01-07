import openwakeword.utils
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("Downloading openWakeWord models...")
    # This downloads the default models including melspectrogram.onnx and embedding models
    openwakeword.utils.download_models()
    logger.info("Download complete.")

if __name__ == "__main__":
    main()
