import asyncio
import websockets
import pyaudio
import msvcrt # Windows-specific library for keypresses

async def stream_mic():
    uri = "ws://127.0.0.1:8080/ws/stream"
    p = pyaudio.PyAudio()
    
    try:
        # Change this line in client.py:
        async with websockets.connect(uri, ping_interval=None, ping_timeout=None) as websocket:
            print("\n--- VOICE SCAM DETECTION CLIENT ---")
            
            while True:
                print("\nOptions: [y] Start Recording | [q] Quit")
                # Wait for initial input
                cmd = input(">> ").lower()
                
                if cmd == 'q': 
                    break
                if cmd != 'y': 
                    continue

                stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, 
                                input=True, frames_per_buffer=8000)
                
                print("🔴 RECORDING... Press 'n' to stop and analyze.")
                frames = []
                
                while True:
                    # Read audio data
                    data = stream.read(8000, exception_on_overflow=False)
                    frames.append(data)
                    
                    # WINDOWS FIX: Check if a key is pressed without blocking
                    if msvcrt.kbhit():
                        key = msvcrt.getch().decode('utf-8').lower()
                        if key == 'n':
                            break

                print("🛑 STOPPED. Sending to agents...")
                stream.stop_stream()
                stream.close()

                # Send the complete audio buffer
                await websocket.send(b''.join(frames))
                
                # Receive and print the verdict
                print("⏳ Agents are analyzing...")
                response = await websocket.recv()
                print(f"\n📢 VERDICT RECEIVED:\n{response}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        p.terminate()
        print("Resources released.")

if __name__ == "__main__":
    asyncio.run(stream_mic())