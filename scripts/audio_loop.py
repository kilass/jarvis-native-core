import asyncio
import websockets
import pyaudio
import sys

# Audio configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
INPUT_RATE = 16000  # Standard for consistent mic capture
OUTPUT_RATE = 24000 # High quality for Gemini Aoede voice
CHUNK = 1024

async def microphone_client():
    uri = "ws://localhost:8000/ws/audio"
    p = pyaudio.PyAudio()

    # List available devices
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    print("\n--- Audio Devices ---")
    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(0, i).get('maxOutputChannels')) > 0:
            print(f"Output Device id {i} - {p.get_device_info_by_host_api_device_index(0, i).get('name')}")
    print("---------------------\n")
    
    # Device Selection Logic
    try:
        selection = input(f"Select Output Device ID (0-{numdevices-1}) [Default]: ")
        output_device_index = int(selection) if selection.strip() else None
    except ValueError:
        print("Invalid input, using default.")
        output_device_index = None
    
    print(f"Opening streams... Input: {INPUT_RATE}Hz, Output: {OUTPUT_RATE}Hz on device {output_device_index}")

    # Input Stream (Microphone)
    input_stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=INPUT_RATE,
                        input=True,
                        frames_per_buffer=CHUNK)

    # Output Stream (Speaker)
    output_stream = p.open(format=FORMAT,
                         channels=CHANNELS,
                         rate=OUTPUT_RATE,
                         output=True,
                         output_device_index=output_device_index)

    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected! Talk to Jarvis (Ctrl+C to stop)")
            
            # Async Queue for audio chunks
            audio_queue = asyncio.Queue()

            async def send_audio():
                import struct
                import math
                import os
                from dotenv import load_dotenv
                
                load_dotenv() # Load .env file
                
                # Parameters for VAD
                try:
                    RMS_THRESHOLD = int(os.getenv("VAD_RMS_THRESHOLD", 1000))
                except ValueError:
                    RMS_THRESHOLD = 1000
                
                print(f"[VAD] Listening for interruption (Threshold: {RMS_THRESHOLD})...");

                try:
                    while True:
                        data = await asyncio.to_thread(input_stream.read, CHUNK, exception_on_overflow=False)
                        
                        # Calculate Volume (RMS) manually to avoid audioop deprecation warning
                        count = len(data) // 2
                        if count > 0:
                            shorts = struct.unpack(f"{count}h", data)
                            sum_squares = sum(s**2 for s in shorts)
                            rms = math.sqrt(sum_squares / count)
                        else:
                            rms = 0
                        
                        # Simple "Barge-in" detection
                        # Only interrupt if volume is loud enough AND we are currently playing audio (optional)
                        # For now, just loud enough.
                        if rms > RMS_THRESHOLD:
                            # Send interrupt signal if we haven't sent one recently (debounce)
                            import time
                            if time.time() - last_interrupt_time > 1.0:
                                print(f"\n[VAD] User Speaking (RMS: {rms}) - SENT INTERRUPTION", flush=True)
                                await websocket.send('{"type": "interrupt"}')
                                last_interrupt_time = time.time()
                        
                        await websocket.send(data)
                        await asyncio.sleep(0.01) # Yield control
                except Exception as e:
                    print(f"Send error: {e}")

            async def play_audio():
                """Consumes audio from queue and plays it"""
                try:
                    while True:
                        data = await audio_queue.get()
                        if data is None: break
                        # Run blocking write in thread to not block event loop
                        await asyncio.to_thread(output_stream.write, data)
                        audio_queue.task_done()
                except Exception as e:
                    print(f"Player error: {e}")

            async def receive_audio():
                """Reads from WebSocket and routing data"""
                try:
                    while True:
                        msg = await websocket.recv()
                        
                        if isinstance(msg, str):
                            # Handle Control Message
                            import json
                            try:
                                data = json.loads(msg)
                                if data.get("type") == "interrupt":
                                    print("\n[DEBUG] CLIENT RECEIVED INTERRUPT SIGNAL")
                                    print(f"[DEBUG] Queue size before flush: {audio_queue.qsize()}")
                                    
                                    # 1. Clear the Python queue (undelivered audio)
                                    flush_count = 0
                                    while not audio_queue.empty():
                                        try:
                                            audio_queue.get_nowait()
                                            audio_queue.task_done()
                                            flush_count += 1
                                        except asyncio.QueueEmpty:
                                            break
                                    print(f"[DEBUG] Flushed {flush_count} chunks from queue")
                                    
                                    # 2. Stop/Restart stream is CAUSING CRASHES on Windows/PyAudio
                                    # We skip hardware buffer clearing for stability.
                                    # The delay will be slightly higher (buffer size), but it won't crash.
                                    # output_stream.stop_stream()
                                    # output_stream.start_stream()
                                    print("[DEBUG] Audio Queue Cleared (Hardware buffer skipped for stability)")
                            except Exception as e:
                                print(f"JSON Error: {e}")
                        else:
                            # Handle Audio Bytes - Push to queue
                            await audio_queue.put(msg)
                            
                except Exception as e:
                    print(f"Receive error: {e}")
                finally:
                    await audio_queue.put(None) # Kill player

            # Run tasks
            await asyncio.gather(send_audio(), receive_audio(), play_audio())
            
    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print(f"Connection error: {e}")
    finally:
        input_stream.stop_stream()
        input_stream.close()
        output_stream.stop_stream()
        output_stream.close()
        p.terminate()

if __name__ == "__main__":
    try:
        if sys.platform == 'win32':
             asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(microphone_client())
    except KeyboardInterrupt:
        pass
