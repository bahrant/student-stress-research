#!/usr/bin/env python3
"""Quick diagnostic to see what's actually in a FIT file"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'FitSDKRelease_21.171.00/py'))

from garmin_fit_sdk import Decoder, Stream

if len(sys.argv) < 2:
    print("Usage: python inspect_fit.py <fitfile.fit>")
    sys.exit(1)

fit_file = sys.argv[1]

print(f"\n{'='*60}")
print(f"Inspecting: {os.path.basename(fit_file)}")
print(f"{'='*60}\n")

stream = Stream.from_file(fit_file)
decoder = Decoder(stream)
messages, errors = decoder.read()

print("Message types found:")
for msg_type, msg_list in sorted(messages.items()):
    print(f"  {msg_type}: {len(msg_list)} messages")

    # Show first message structure
    if msg_list and len(msg_list) > 0:
        first_msg = msg_list[0]
        print(f"    Sample fields: {list(first_msg.keys())[:10]}")

        # Show field values for monitoring and unknown types
        if 'monitoring' in msg_type or msg_type.isdigit():
            print(f"    Sample values:")
            for key, value in list(first_msg.items())[:10]:
                print(f"      {key}: {value}")

print(f"\n{'='*60}\n")
