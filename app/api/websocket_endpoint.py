from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.gemini_client import GeminiClient
from app.services.tts_service import TTSService
import asyncio
import logging

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
                        while not text_queue.empty():
                            try:
                                text_queue.get_nowait()
                            except asyncio.QueueEmpty:
                                break
                        interrupt_event.clear()
                        
                        # Tell client to stop playing immediately
                        try:
                            await websocket.send_text('{"type": "interrupt"}')
                        except Exception as e:
                            logger.error(f"Failed to send interrupt signal: {e}")

                    try:
                        # Get text with timeout to allow checking interrupt_event regularly
                        try:
                            text_chunk = await asyncio.wait_for(text_queue.get(), timeout=0.1)
                        except asyncio.TimeoutError:
                            continue
                            
                        if text_chunk is None: # Sentinel for exit
                            break

                        logger.debug(f"TTS Loop: Received chunk: {text_chunk}")
                        buffer += text_chunk
                        
                        # Check interruption again before expensive TTS
                        if interrupt_event.is_set():
                            continue

                        # Sentence buffering logic
                        sentences = re.split(r'([.!?]+)', buffer)
                        if len(sentences) > 1:
                            for i in range(0, len(sentences) - 1, 2):
                                if interrupt_event.is_set(): break
                                
                                sentence = sentences[i] + sentences[i+1]
                                if sentence.strip():
                                    logger.info(f"Synthesizing: {sentence}")
                                    audio_data = await tts_service.synthesize(sentence)
                                    if audio_data and not interrupt_event.is_set():
                                        await websocket.send_bytes(audio_data)
                            
                            buffer = sentences[-1] if not interrupt_event.is_set() else ""

                    except Exception as e:
                        logger.error(f"Error in TTS loop: {e}")
                        await asyncio.sleep(0.1)

            async def receive_from_client():
                """Receives audio from WebSocket and sends to Gemini"""
                try:
                    logger.info("Starting receive_from_client loop")
                    while True:
                        try:
                            # We use receive() instead of receive_bytes() to handle both Text and Binary
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
                                await session.send(input={"data": data, "mime_type": "audio/pcm"}, end_of_turn=False)

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
                try:
                    logger.info("Starting send_to_client loop (Gemini -> Queue)")
                    while True:
                        try:
                            async for response in session.receive():
                                server_content = response.server_content
                                
                                # Debug: Log potential interruption signals
                                if server_content:
                                     if server_content.interrupted:
                                         logger.info("!! DETECTED INTERRUPTION FLAG !!")
                                
                                if server_content and server_content.interrupted:
                                    logger.info("Turn interrupted! Signaling TTS loop.")
                                    interrupt_event.set()
                                    continue

                                if server_content and server_content.model_turn:
                                    for part in server_content.model_turn.parts:
                                        if part.text:
                                            await text_queue.put(part.text)
                                
                                if server_content and server_content.turn_complete:
                                    # Force flush of remaining buffer in TTS loop could be handled here 
                                    # by sending a special token, or just implemented in TTS loop timeout logic
                                    # For now, we rely on the buffering logic directly.
                                    pass

                            logger.warning("Gemini receive iterator ended. Re-entering...")
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
