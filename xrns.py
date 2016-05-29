#!/usr/bin/env python
# needs unzip, flac and sox at your shell

from xml.dom import minidom
from subprocess import call
import sys
import wave
import os


def get_instruments(song_xml_file):
    xml = minidom.parse(song_xml_file)
    for instrument in xml.getElementsByTagName("Instrument"):
        instrument_data = {"samples": [], "name": ""}
        for node in instrument.childNodes:
            if node.localName == "Name":
                instrument_data["name"] = node.firstChild.nodeValue
        for sample in instrument.getElementsByTagName("Sample"):
            sample_data = {}
            for node in sample.childNodes:
                if node.localName == "Name":
                    sample_data["name"] = node.firstChild.nodeValue
                if node.localName == "LoopMode":
                    sample_data["loop"] = node.firstChild.nodeValue
                if node.localName == "LoopStart":
                    sample_data["start"] = node.firstChild.nodeValue
                if node.localName == "LoopEnd":
                    sample_data["end"] = node.firstChild.nodeValue
            instrument_data["samples"].append(sample_data)
        yield instrument_data


def cut_wave(source_file, destination_file, start, end):
    source_wave = wave.open(source_file, 'r')
    source_wave.readframes(int(start))  # isn't it what setpos() should do ?
    destination_wave = wave.open(destination_file, 'w')
    destination_wave.setnchannels(source_wave.getnchannels())
    destination_wave.setsampwidth(source_wave.getsampwidth())
    destination_wave.setframerate(source_wave.getframerate())
    destination_wave.writeframes(source_wave.readframes(int(end) - int(start)))
    destination_wave.close()
    source_wave.close()


def sanitize_filename(file_name):
    """
    todo: actual implementation
    """
    return file_name.replace(":", "_")


def process_xrns(xrns_filepath):
    call(["unzip", xrns_filepath], stdout=open(os.devnull, 'wb'))
    call(["find", ".", "-name", "*.flac", "-exec", "flac", "-df", "{}", ";"], stdout=open(os.devnull, 'wb'),
         stderr=open(os.devnull, 'wb'))
    # python won't open waves from renoise, not sure why.
    # call(["find", ".", "-name", "*.wav", "-exec", "ffmpeg", "-y", "-i", "{}", "{}", ";"]) #ffmpeg craps the file
    call(["find", ".", "-name", "*.wav", "-exec", "sox", "{}", "-b", "16", "{}.sox.wav", ";"],
         stdout=open(os.devnull, 'wb'), stderr=open(os.devnull, 'wb'))

    instrument_index = 0
    for instrument in get_instruments("Song.xml"):
        sample_index = 0
        for sample in instrument["samples"]:
            if sample["loop"] != "Off":
                wave_path = sanitize_filename("SampleData/"
                                              + "Instrument{:02d} ({})".format(instrument_index, instrument["name"])
                                              + "/Sample{:02d} ({})".format(sample_index,
                                                                            sample["name"]) + ".wav.sox.wav")
                loop_path = sanitize_filename("SampleData/"
                                              + "Instrument{:02d} ({})".format(instrument_index, instrument["name"])
                                              + "/Sample{:02d} ({})-loop".format(sample_index, sample["name"]) + ".wav")
                cut_wave(wave_path, loop_path, sample["start"], sample["end"])
                print(loop_path)
            sample_index += 1
        instrument_index += 1

    call(["find", ".", "-name", "*.flac", "-exec", "rm", "{}", ";"], stdout=open(os.devnull, 'wb'),
         stderr=open(os.devnull, 'wb'))
    call(["find", ".", "-name", "*.sox.wav", "-exec", "rm", "{}", ";"], stdout=open(os.devnull, 'wb'),
         stderr=open(os.devnull, 'wb'))


if __name__ == "__main__":
    process_xrns(sys.argv[1])
