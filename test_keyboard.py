import msvcrt
import time

print("Testing keyboard input! Press any key, or 'q' to quit.")
print("="*50)

while True:
    if msvcrt.kbhit():
        key_bytes = msvcrt.getch()
        print(f"Got key: {key_bytes!r}")
        try:
            key = key_bytes.decode('ascii', errors='ignore')
            print(f"Decoded: {key!r}")
            if key.lower() == 'q':
                break
        except Exception as e:
            print(f"Decode error: {e}")
    time.sleep(0.01)

print("\nTest complete!")
