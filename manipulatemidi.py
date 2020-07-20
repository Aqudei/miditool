import argparse
import mido
import logging
import os
import xml.etree.ElementTree as ET
import re

# logging.getLogger().setLevel(logging.INFO)
# Setup logger

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh = logging.FileHandler(filename='debug.log')
ch = logging.StreamHandler()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

fh.setFormatter(formatter)
ch.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(ch)


type_help = "Pass '--help' to show the help message."


def shift_tones(orig_midi, semitones):

    midfile = mido.MidiFile(orig_midi)
    newfile = mido.MidiFile()
    newfile.ticks_per_beat = midfile.ticks_per_beat
    print("Ticks per beat: {}".format(newfile.ticks_per_beat))
    print("Total tracks: {}".format(len(midfile.tracks)))
    for idx, track in enumerate(midfile.tracks):
        new_track = mido.MidiTrack()
        for msg in track:
            if msg.type in ['note_on', 'note_off']:
                new_note = msg.note + semitones
                if new_note < 0 or new_note > 127:
                    new_note = new_note - semitones
                    new_track.append(msg.copy(note=new_note, velocity=0))
                else:
                    new_track.append(msg.copy(note=new_note))
            else:
                new_track.append(msg.copy())
        newfile.tracks.append(new_track)

    # head, tail = os.path.split(args.file)

    # newfile.save(os.path.join(head, 'minus-2-semitones-{}'.format(tail)))

    return newfile


def find_midis(root_xml, root_dir):
    disk_midis = dict()
    for r, dirs, files in os.walk(os.path.join(root_dir, 'interchange')):
        for file in files:
            fn, ext = os.path.splitext(file)
            if not ext == '.mid':
                continue
            disk_midis[file] = (os.path.join(r, file))

    sources = dict()
    for source in root_xml.findall(".//Sources/Source"):
        if not source.attrib['type'] == 'midi':
            continue

        sources[source.attrib.get('id')] = source.attrib.get('name')

    for k in sources.keys():
        sources[k] = disk_midis.get(sources[k])

    return sources


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=str,
                        help='The directory where the .ardour file is locatedF')
    parser.add_argument('--shift-semis', type=int,
                        help='The number of semitones to shift')
    parser.add_argument('--regex', type=str,
                        help='Regex pattern to match the MIDI file.')

    args = parser.parse_args()

    if not args.regex:
        logger.error("Please supply a valid 'regex'. {}".format(type_help))
        exit()

    if not args.directory or not os.path.exists(args.directory):
        logger.error("Please supply a valid 'directory'. {}".format(type_help))
        exit()

    if not args.shift_semis:
        logger.error(
            "Please supply the number of semitones to shift. {}".format(type_help))
        exit()

    if args.shift_semis > 12 or args.shift_semis < -12:
        logger.error(
            "'--shift-semis' must a value between 12 and -12")
        exit()

    ardour_file = None

    logger.info("Looking for '.ardour' in {}".format(args.directory))
    for _file in os.listdir(args.directory):
        if _file.endswith(".ardour"):
            ardour_file = os.path.join(args.directory, _file)
            logger.info("Found: {}".format(ardour_file))
            break

    if not ardour_file:
        logger.error("No '.ardour' file found in {}".format(
            os.path.abspath(args.directory)))
        exit()

    regex = re.compile(r"{}".format(args.regex))
    root = ET.parse(ardour_file)

    midis = find_midis(root, args.directory)

    source_0s = set()

    for elem in root.findall('.//Playlists/Playlist'):
        # How to make decisions based on attributes even in 2.6:
        match = regex.match(elem.attrib.get('name'))
        if elem.attrib.get('name') and match:
            for region in elem:
                if region.tag == 'Region':
                    source_0 = region.attrib.get('source-0')
                    if not source_0:
                        logger.warning(
                            "Error, source-0 has no valid value in <Playlist><Region>..</Region></Playlist>. Skipping...")
                        continue
                    source_0s.add((match.group(0), source_0))

    for match, source0 in source_0s:
        logger.debug("Matched name: {}".format(match))

        midi_file = midis[source_0]
        if not midi_file or not os.path.exists(midi_file):
            logger.warning(
                "Cannot find the file source:0:{}, filename: {}! Skipping...".format(source_0, midi_file))
            continue

        logger.debug("Processing {}:{}, midifile: {}".format(
            match, source0, midi_file))
        new_midi = shift_tones(midi_file, args.shift_semis)
        if not new_midi:
            logger.error("Unable to produce shifted midi.")

        new_midi.save(midi_file)
