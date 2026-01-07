from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.gemini_client import GeminiClient
from app.services.tts_service import TTSService
import asyncio
import logging
import os
import time
import numpy as np
from openwakeword.model import Model

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws/audio")
async def audio_websocket(websocket: WebSocket):
    await websocket.accept()
    logger.info("Satellite connected")
    
    gemini_client = GeminiClient()
    tts_service = TTSService()
    
    try:
        async with gemini_client.start_session() as session:
            logger.info("Gemini Session Active")
            
            # Create a queue for text chunks and an event for interruption
            text_queue = asyncio.Queue()
            interrupt_event = asyncio.Event()

            # Wake Word State
            is_awake = False
            last_wake_time = 0
            
            # Load model locally for the session
            model_path = os.path.join(os.getcwd(), "models", "Motisma-v1.onnx")
            wakeword_model = Model(wakeword_models=[model_path], inference_framework="onnx")

            async def tts_processing_loop():
                """Consumes text from queue, buffers sentences, and streams audio"""
                import re
                buffer = ""
                
                logger.info("Starting TTS processing loop")
                while True:
                    # Check interruption
                    if interrupt_event.is_set():
                        logger.info("TTS Loop: Clearing buffer due to interruption")
                        buffer = ""
                        # Drain queue
                        # Drain queue immediately
                        while not text_queue.empty():
                            try: text_queue.get_nowait()
                            except asyncio.QueueEmpty: break
                        interrupt_event.clear()
                        # Tell client to stop audio (optional, client already stops roughly)
                        try: await websocket.send_text('{"type": "interrupt"}')
                        except Exception as e:
                            logger.error(f"Failed to send interrupt signal: {e}")

                    try:
                        try:
                            # 0.1s timeout allows checking interrupt_event frequently
                            text_chunk = await asyncio.wait_for(text_queue.get(), timeout=0.1)
                        except asyncio.TimeoutError:
                            continue
                            
                        if text_chunk is None: # Sentinel for exit
                            break
                        
                        logger.debug(f"TTS Loop: Received chunk: {text_chunk}")

                        # GATEKEEPER: If we went back to sleep, discard everything
                        if not is_awake: 
                            logger.info(f"TTS Loop: Discarding chunk '{text_chunk}' because system is asleep.")
                            continue 

                        buffer += text_chunk
                        
                        # Check interruption again before expensive TTS
                        if interrupt_event.is_set():
                            continue

                        # Sentence buffering logic
                        sentences = re.split(r'([.!?]+)', buffer)
                        if len(sentences) > 1:
                            for i in range(0, len(sentences) - 1, 2):
                                # Check interruption/sleep inside the loop
                                if interrupt_event.is_set() or not is_awake: 
                                    logger.info("TTS Loop: Breaking sentence processing due to interruption or sleep.")
                                    break
                                
                                sentence = sentences[i] + sentences[i+1]
                                if sentence.strip():
                                    logger.info(f"Synthesizing: {sentence}")
                                    audio_data = await tts_service.synthesize(sentence)
                                    # Final Check before sending
                                    if audio_data and not (interrupt_event.is_set() or not is_awake):
                                        await websocket.send_bytes(audio_data)
                                    else:
                                        logger.info("TTS Loop: Not sending audio due to interruption or sleep.")
                            
                            buffer = sentences[-1] if not (interrupt_event.is_set() or not is_awake) else ""
                    except Exception as e:
                        logger.error(f"Error in TTS loop: {e}")
                        await asyncio.sleep(0.1)

            async def receive_from_client():
                """Receives audio from WebSocket and sends to Gemini"""
                nonlocal is_awake, last_wake_time
                try:
                    logger.info("Starting receive_from_client loop")
                    while True:
                        try:
                            message = await websocket.receive()
                            if "text" in message:
                                # Start of a control message
                                import json
                                try:
                                    data = json.loads(message["text"])
                                    if data.get("type") == "interrupt":
                                        logger.info("Received CLIENT INTERRUPTION signal")
                                        interrupt_event.set()
                                        # Also notify Gemini that we are interrupting? 
                                        # Not strictly necessary if we stop playing, but good practice.
                                        # await session.send(input="[INTERRUPTION]", end_of_turn=True) 
                                except Exception as e:
                                    logger.error(f"Error parsing control message: {e}")

                            elif "bytes" in message:
                                # Audio Data
                                data = message["bytes"]
                                audio_np = np.frombuffer(data, dtype=np.int16)
                                prediction = wakeword_model.predict(audio_np)
                                
                                for mdl_name, score in prediction.items():
                                    if score >= 0.5:
                                        now = time.time()
                                        if now - last_wake_time > 1.0: # 1.0s Debounce logic
                                            last_wake_time = now
                                            
                                            if not is_awake:
                                                logger.info(f"✨ REVEIL: {mdl_name} (Score: {score:.3f})")
                                                is_awake = True
                                            else:
                                                # WAKE WORD INTERRUPTION -> SLEEP
                                                logger.info(f"🔄 INTERRUPTION (Wake Word) -> SLEEPING (Score: {score:.3f})")
                                                interrupt_event.set()
                                                # Go back to sleep immediately
                                                is_awake = False
                                    elif score > 0.1:
                                        # Low confidence logging as requested
                                        logger.debug(f"🔍 Low Confidence: {mdl_name} (Score: {score:.3f})")
                                
                                # GATEKEEPER: Only send to Gemini if Awake
                                if is_awake:
                                    await session.send(input={"data": data, "mime_type": "audio/pcm"}, end_of_turn=False)
                                else:
                                    logger.debug("Discarding audio input, system is asleep.")

                        except RuntimeError as e:
                             # Starlette/FastAPI specific disconnect error sometimes
                             logger.warning(f"RuntimeError in receive: {e}")
                             break
                             
                except WebSocketDisconnect:
                    logger.info("Client disconnected (WebSocket)")
                except Exception as e:
                    logger.error(f"Error in receive_from_client: {e}")
                finally:
                    logger.info("Exiting receive_from_client loop")

            async def send_to_client():
                """Receives TEXT -> Pushes to Queue"""
                nonlocal is_awake
                try:
                    logger.info("Starting send_to_client loop (Gemini -> Queue)")
                    while True:
                        try:
                            async for response in session.receive():
                                server_content = response.server_content
                                
                                if server_content:
                                    if server_content.interrupted:
                                        logger.info("🛑 Gemini Interrupted -> Silence")
                                        interrupt_event.set()
                                        is_awake = False # STRICT SILENCE: Sleep immediately
                                        continue
                                    
                                    if server_content.model_turn and is_awake:
                                        for part in server_content.model_turn.parts:
                                            if part.text: 
                                                logger.debug(f"Gemini -> Queue: {part.text}")
                                                await text_queue.put(part.text)
                                await asyncio.sleep(0.1)

                        except Exception as inner_e:
                            logger.error(f"Error inside receive loop: {inner_e}")
                            break
                except Exception as e:
                    logger.error(f"Error in send_to_client: {e}")
                finally:
                    logger.info("Exiting send_to_client loop")
                    await text_queue.put(None) # Signal exit

            # Run tasks
            # We need 3 tasks now: Mic Input, Gemini Output, TTS Processing
            await asyncio.gather(
                receive_from_client(), 
                send_to_client(),
                tts_processing_loop()
            )

    except Exception as e:
        logger.error(f"Session error: {e}")
        # Close connection if not already closed
        try:
            await websocket.close()
        except:
            pass
