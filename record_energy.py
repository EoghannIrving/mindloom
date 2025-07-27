"""CLI script to record daily energy and mood."""

import argparse
from energy import record_entry

parser = argparse.ArgumentParser(description="Record today's energy and mood")
parser.add_argument("energy", type=int, help="Energy level 1-10")
parser.add_argument("mood", type=int, help="Mood level 1-10")

args = parser.parse_args()

entry = record_entry(args.energy, args.mood)
print(f"Recorded: {entry}")
