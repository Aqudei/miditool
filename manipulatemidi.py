import argparse
import mido
import logging
import os
import xml.etree.ElementTree as ET
import re
import glob
import music21

# logging.getLogger().setLevel(logging.INFO)
# Setup logger

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
formatter2 = logging.Formatter('%(message)s')
fh = logging.FileHandler(filename='debug.log')
ch = logging.StreamHandler()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

fh.setFormatter(formatter)
ch.setFormatter(formatter2)
logger.addHandler(fh)
logger.addHandler(ch)

type_help = "Pass '--help' to show the help message."


def tone_name(tone_num):
    noteString = ["C", "C#", "D", "D#", "E",
                  "F", "F#", "G", "G#", "A", "A#", "B"]

    octave = int(tone_num / 12) - 1
    noteIndex = (tone_num % 12)
    return "{}{}".format(noteString[noteIndex], octave)


def display_notes(orig_midi, new_midi, semitones):
    limit = 10
    done = set()
    logger.info(
        "Showing first {} notes before and after shifting {:+d} semitones...".format(limit, semitones))
    count = 0
    for orig_track, new_track in zip(orig_midi.tracks, new_midi.tracks):
        for orig_msg, new_msg in zip(orig_track, new_track):
            if orig_msg.type in ['note_on', 'note_off'] and new_msg.velocity > 0 and not orig_msg.note in done:
                logger.info("\tNote#: {}, Name: {} ---> Note#: {}, Name: {}".format(orig_msg.note,
                                                                                    tone_name(orig_msg.note), new_msg.note, tone_name(new_msg.note)))
                count = count + 1
                done.add(orig_msg.note)
                if count >= limit:
                    break


def shift_tones2(orig_midi, semitones):
    score = music21.converter.parse(orig_midi)
    key = score.analyze('key')
    print(f"Old Key Tonic name:{key.tonic.name}")

    newscore = score.transpose(semitones)
    key = newscore.analyze('key')
    print(f"New Key Tonic name:{key.tonic.name}")
    return newscore


def shift_tones(orig_midi, semitones):

    midfile = mido.MidiFile(orig_midi)
    newfile = mido.MidiFile()
    newfile.ticks_per_beat = midfile.ticks_per_beat
    logger.debug("Midi Information: {}".format(orig_midi))
    logger.debug("\tTicks per beat: {}".format(newfile.ticks_per_beat))
    logger.debug("\tTotal tracks: {}".format(len(midfile.tracks)))
    logger.debug("\tMidi Type: {}".format(midfile.type))

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
    display_notes(midfile, newfile, semitones)
    return newfile


def find_midis(root_xml, root_dir):
    disk_midis = dict()
    sources = dict()

    for source in root_xml.findall(".//Sources/Source"):
        if not source.attrib['type'] == 'midi':
            continue

        source_id = source.attrib.get('id')
        source_name = source.attrib.get('name')
        sources[source_id] = source_name

    for r, dirs, files in os.walk(os.path.join(root_dir, 'interchange')):
        for file in files:
            fn, ext = os.path.splitext(file)
            if not ext == '.mid':
                continue

            for source_k in sources.keys():
                if sources[source_k] == file:
                    sources[source_k] = os.path.join(r, file)
                    break
    return sources


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=str,
                        help='The directory where the .ardour file is locatedF')
    parser.add_argument('--shift-semis', type=int,
                        help='The number of semitones to shift')
    parser.add_argument('--regex', type=str,
                        help='Regex pattern to match the MIDI file.')
    parser.add_argument('--no-regex', type=str,
                        help='Regex pattern to match the MIDI file.')
    args = parser.parse_args()

    if not args.regex and not args.no_regex:
        logger.error("Please supply a valid value for --regex or --no-regex")
        exit()

    if args.regex and args.no_regex:
        logger.error(
            "You cannot set values for --regex and --no-regex at the same time")
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
            logger.info("Found: {}\n".format(ardour_file))
            logger.info("="*40)

            break

    if not ardour_file:
        logger.error("No '.ardour' file found in {}".format(
            os.path.abspath(args.directory)))
        exit()

    regex = re.compile(r"{}".format(args.regex or args.no_regex))
    root = ET.parse(ardour_file)

    source_0s = dict()

    # for elem in root.findall('.//Playlists/Playlist'):
    #     # How to make decisions based on attributes even in 2.6:
    #     playlist_name = elem.attrib.get('name')
    #     match = regex.match(
    #         playlist_name) if args.regex else not regex.match(playlist_name)

    #     if not match:
    #         logger.info(
    #             f"Playlist with name {playlist_name} does not match regex {args.regex}")
    #         continue

    #     for region in elem:
    #         if region.tag == 'Region':
    #             source_0 = region.attrib.get('source-0')
    #             if not source_0:
    #                 logger.warning(
    #                     "Error, source-0 has no valid value in <Playlist><Region>..</Region></Playlist>. Skipping...")
    #                 continue
    #             source_0s[playlist_name.strip()] = source_0

    logger.info("Looking up routes...")
    routes = list(root.findall('.//Routes/Route'))
    for route in routes:
        # How to make decisions based on attributes even in 2.6:
        route_name = route.attrib.get('name')
        match = regex.match(
            route_name) if args.regex else not regex.match(route_name)

        if not match:
            continue

        logger.info("Yes! A route with name '{}' matched regex '{}'".format(
            route_name, args.regex))
        midi_id = route.attrib.get("midi-playlist")

        logger.info("Looking up playlists...")
        for playlist in root.findall('.//Playlists/Playlist'):
            if not playlist.attrib.get("id") == midi_id:
                continue

            logger.info("Yes! Playlist(name={},id={}) matched <midi_id>='{}'".format(
                playlist.attrib.get("name"), playlist.attrib.get("id"), midi_id))

            logger.info("Looking up regions...")
            for region in playlist:
                if not region.tag == 'Region':
                    continue

                source_0 = region.attrib.get('source-0')
                if not source_0:
                    logger.warning(
                        "Error, source-0 has no valid value in <Playlist><Region>..</Region></Playlist>. Skipping...")
                    continue
                source_0s[route_name.strip()] = source_0
                break

    if not source_0s:
        logger.error("Did not find any 'midi' file to process!")
        exit()

    logger.info("Looking for midi files in folder.")

    midis = find_midis(root, args.directory)
    logger.info("Found a total of {} midi files.".format(len(midis)))
    logger.info("="*40)
    total_processed = 0

    for route_name in source_0s.keys():
        source0_id = source_0s[route_name]

        logger.debug("Processing for {}='{}'".format(
            "--regex" if args.regex else "--no-regex", regex.pattern))

        logger.debug(
            "Number of semitones to shift: {:+d}".format(args.shift_semis))
        logger.debug(
            "Regex '{}' {} Route 'name': {}".format(args.regex or args.no_regex, 'matched' if args.regex else 'no matched', route_name))

        midi_file = midis[source0_id]

        if not midi_file or not os.path.exists(midi_file):
            logger.warning(
                "Cannot find the file source:0:{}, filename: {}! Skipping...".format(source_0, midi_file))
            continue

        logger.debug("Processing name:'{}', source-0{},\n\tmidifile: {}".format(
            route_name, source0_id, midi_file))
        new_midi = shift_tones2(midi_file, args.shift_semis)
        if not new_midi:
            logger.error("Unable to produce shifted midi.")
            continue

        new_midi.write('midi', midi_file)
        total_processed = total_processed + 1
        logger.info("="*40)
    logger.debug("Total # of midis modified: {}".format(total_processed))
