import time
import logging
import os
import pyaudio
import numpy as np
import openwakeword
from openwakeword.model import Model

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
MODEL_PATH = os.path.join(os.path.dirname(__file__), "../models/Motisma-v1.onnx")
CHUNK_SIZE = 1280
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

def main():
    if not os.path.exists(MODEL_PATH):
        logger.error(f"Model not found at: {MODEL_PATH}")
        return

    logger.info(f"Loading custom model: {MODEL_PATH}")
    
    try:
        model = Model(wakeword_models=[MODEL_PATH], inference_framework="onnx")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return

    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK_SIZE)

    logger.info("🎤 Listening... Say 'Motisma'!")
    logger.info("Press Ctrl+C to stop.")

    last_wake_time = 0

    try:
        while True:
            data = stream.read(CHUNK_SIZE)
            audio = np.frombuffer(data, dtype=np.int16)
            prediction = model.predict(audio)
            
            for mdl_name, score in prediction.items():
                if score > 0.5:
                    now = time.time()
                    if now - last_wake_time > 1.0: # 1.0s Debounce
                        last_wake_time = now
                        logger.info(f"✨ WAKE WORD DETECTED: {mdl_name} (Score: {score:.3f})")
                elif score > 0.1:
                     logger.info(f"🔍 Low Confidence: {mdl_name} (Score: {score:.3f})")

    except KeyboardInterrupt:
        logger.info("\nStopping...")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

if __name__ == "__main__":
    main()
