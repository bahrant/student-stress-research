#!/usr/bin/env python3
"""Deep inspection of monitoring messages"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'FitSDKRelease_21.171.00/py'))

from garmin_fit_sdk import Decoder, Stream

fit_file = sys.argv[1]

stream = Stream.from_file(fit_file)
decoder = Decoder(stream)
messages, errors = decoder.read()

print(f"\n=== Monitoring Messages (first 20) ===")
if 'monitoring_mesgs' in messages:
    for i, msg in enumerate(messages['monitoring_mesgs'][:20]):
        print(f"{i}: {msg}")

print(f"\n=== Message Type 233 (first 10) ===")
if '233' in messages:
    for i, msg in enumerate(messages['233'][:10]):
        print(f"{i}: {msg}")

print(f"\n=== Message Type 24 (first 5) ===")
if '24' in messages:
    for i, msg in enumerate(messages['24'][:5]):
        print(f"{i}: {msg}")
